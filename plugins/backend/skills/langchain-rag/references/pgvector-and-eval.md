# pgvector con langchain-postgres, retrieval tool y evaluación

Verifica la versión de `langchain-postgres` instalada; esta referencia usa la API `PGEngine` + `PGVectorStore`.

## 1. Setup de Postgres
```sql
CREATE EXTENSION IF NOT EXISTS vector;   -- en una migración (Alembic/Prisma/TypeORM)
```
Instala: `uv add langchain-postgres asyncpg` (o `psycopg[binary]` si usas `postgresql+psycopg`).

## 2. Tabla con columnas de metadata filtrables
Los filtros de `PGVectorStore` **solo aplican a `metadata_columns`**, no a la columna JSON. Declara como columna todo lo que vayas a filtrar (tenant, tipo de documento, idioma).
```python
from langchain_postgres import Column, PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWIndex

TABLE = "doc_chunks"

async def init_table(engine: PGEngine, vector_size: int) -> None:
    await engine.ainit_vectorstore_table(
        table_name=TABLE,
        vector_size=vector_size,
        metadata_columns=[
            Column("tenant_id", "TEXT"),
            Column("source_id", "TEXT"),
            Column("doc_type", "TEXT"),
        ],
        id_column=Column("chunk_id", "TEXT"),
        metadata_json_column="metadata",     # resto de metadata (title, url, page...)
    )

async def build_store(engine: PGEngine, embeddings) -> PGVectorStore:
    return await PGVectorStore.create(
        engine=engine,
        table_name=TABLE,
        embedding_service=embeddings,
        id_column="chunk_id",
        metadata_columns=["tenant_id", "source_id", "doc_type"],
        metadata_json_column="metadata",
    )

async def ensure_index(store: PGVectorStore) -> None:
    await store.aapply_vector_index(HNSWIndex(name="ix_doc_chunks_embedding_hnsw"))
```
- Crea tabla e índice en un paso de despliegue/migración, no en cada arranque.
- Índices B-tree en `tenant_id` y `source_id` (SQL directo en migración) para filtros y borrados.
- HNSW: mejor recall/latencia, más memoria y build más lento; IVFFlat: build rápido, requiere datos previos para entrenar listas.

## 3. Ingesta idempotente
```python
import hashlib

def chunk_id(source_id: str, idx: int, content: str) -> str:
    h = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"{source_id}:{idx}:{h}"

async def ingest_document(store, source_id: str, tenant_id: str, docs) -> int:
    chunks = splitter.split_documents(docs)
    for i, c in enumerate(chunks):
        c.metadata.update(tenant_id=tenant_id, source_id=source_id,
                          chunk_id=chunk_id(source_id, i, c.page_content))
    await delete_source(store, source_id)          # re-ingesta limpia del documento
    await store.aadd_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
    return len(chunks)
```
Para borrar por `source_id`, guarda los ids por documento (tabla propia de documentos) y usa `await store.adelete(ids)`, o ejecuta un `DELETE ... WHERE source_id = :id` en SQL sobre la tabla.

## 4. Búsqueda con filtros
```python
docs = await store.asimilarity_search(
    query,
    k=6,
    filter={"$and": [{"tenant_id": {"$eq": tenant_id}}, {"doc_type": {"$in": ["manual", "faq"]}}]},
)
```
Operadores: `$eq, $ne, $lt, $lte, $gt, $gte, $in, $nin, $between, $exists, $like, $ilike, $and, $or`.

Búsqueda híbrida: combina con full-text de Postgres (`tsvector` + `ts_rank`) en una consulta propia y fusiona con Reciprocal Rank Fusion; verifica si tu versión de `langchain-postgres` ofrece configuración híbrida integrada antes de implementarla a mano.

## 5. Retrieval como tool (RAG agéntico)
```python
from langchain.tools import tool, ToolRuntime

@tool(response_format="content_and_artifact")
async def search_docs(query: str, runtime: ToolRuntime[Context]):
    """Busca en la documentación interna. Usa consultas concretas con términos clave."""
    docs = await store.asimilarity_search(query, k=5, filter={"tenant_id": {"$eq": runtime.context.tenant_id}})
    content = "\n\n".join(f"[{d.metadata['source_id']}] {d.page_content}" for d in docs)
    return content, docs          # (texto para el modelo, artifact con los Document)

agent = create_agent(model, tools=[search_docs], context_schema=Context,
                     system_prompt="Responde citando [source_id]. Si no encuentras la respuesta, dilo.")
```
Recupera los artifacts desde los `ToolMessage` (`msg.artifact`) para construir la lista de fuentes que devuelve la API.

## 6. Validación de citas
```python
def validate_citations(answer: Answer, retrieved: list[Document]) -> Answer:
    by_id = {d.metadata["source_id"]: d.page_content for d in retrieved}
    valid = [c for c in answer.citations
             if c.source_id in by_id and c.quote.strip()[:80] in by_id[c.source_id]]
    return answer.model_copy(update={"citations": valid})
```
Si una respuesta `found=True` queda sin citas válidas, trátala como no fundamentada (reintenta o responde "no encontrado").

## 7. Evaluación con LangSmith
Dataset: `inputs={"question": ...}`, `outputs={"answer": ..., "source_ids": [...]}`.

```python
from langsmith import aevaluate
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT

async def target(inputs: dict) -> dict:
    docs = await retrieve(inputs["question"], tenant_id="eval")
    ans = await answer_chain.ainvoke({"context": format_docs(docs), "question": inputs["question"]})
    return {"answer": ans.answer, "source_ids": [d.metadata["source_id"] for d in docs],
            "context": format_docs(docs)}

def retrieval_hit(outputs: dict, reference_outputs: dict) -> dict:
    expected = set(reference_outputs["source_ids"])
    hit = bool(expected & set(outputs["source_ids"]))
    return {"key": "retrieval_hit", "score": hit}

correctness_judge = create_llm_as_judge(prompt=CORRECTNESS_PROMPT, model="openai:gpt-5.4-mini",
                                        feedback_key="correctness")

def correctness(inputs: dict, outputs: dict, reference_outputs: dict):
    return correctness_judge(inputs=inputs, outputs=outputs, reference_outputs=reference_outputs)

await aevaluate(target, data="rag-faq-v1", evaluators=[retrieval_hit, correctness],
                experiment_prefix="rag-chunk1000-k6", max_concurrency=4,
                metadata={"chunk_size": 1000, "k": 6, "embeddings": settings.embeddings_model})
```
- Añade un evaluador de groundedness (respuesta respaldada por `context`) con un prompt de `openevals` para RAG (p. ej. `RAG_GROUNDEDNESS_PROMPT`; verifica el nombre en la versión instalada) o con una rúbrica propia.
- Usa como juez el modelo configurado en el proyecto; el id anterior es solo ilustrativo.
- Compara experimentos cambiando una sola variable a la vez (chunk size, k, reranker, prompt).

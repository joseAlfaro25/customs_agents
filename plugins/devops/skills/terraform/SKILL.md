---
name: terraform
description: "Terraform/OpenTofu: estructura de módulos y entornos, remote state con locking, variables y outputs, versiones de providers, fmt/validate/plan, tflint y checkov, naming y tags, workspaces vs directorios. Usar al escribir, revisar o refactorizar infraestructura como código."
---

# terraform

## Objetivo
Infraestructura reproducible y revisable: módulos pequeños y reutilizables, un directorio por entorno con su propio estado remoto bloqueado, versiones fijadas y cambios que siempre pasan por `plan` revisado antes de `apply`.

## Cuándo aplicarla
- Crear infraestructura nueva (red, cluster, base de datos, buckets, IAM, OIDC de GitHub) o un módulo.
- Añadir un entorno o migrar de workspaces/estado local a estado remoto.
- Revisar un PR de Terraform, un plan con destrucciones inesperadas o drift.

Carga antes `core:project-context`; revisa `infra/`, `terraform/`, `*.tf`, `.terraform.lock.hcl`, `.tflint.hcl` y la configuración del backend. Para decisiones de arquitectura (cuenta, región, servicio gestionado), consulta con `devops:cloud-architect`.

## Estructura
```
infra/
├── bootstrap/            # bucket de estado y rol de CI; se aplica una vez, estado local o propio
├── modules/
│   └── <modulo>/
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       ├── versions.tf   # required_providers sin bloque provider
│       └── README.md     # generado con terraform-docs
└── envs/
    ├── staging/
    │   ├── backend.tf
    │   ├── providers.tf
    │   ├── versions.tf
    │   ├── main.tf       # llama a módulos
    │   ├── variables.tf
    │   ├── outputs.tf
    │   └── terraform.tfvars   # valores no sensibles del entorno
    └── production/
```
- Un estado por entorno y por dominio con distinto ciclo de vida (p. ej. `network`, `data`, `apps`) cuando el estado crece o el blast radius es alto. Conecta estados con outputs + `terraform_remote_state` o, mejor, data sources/SSM Parameters.
- Módulos: una responsabilidad, sin `provider` propio, sin valores de entorno hardcodeados, recibiendo `tags`/`labels` como variable.
- Plantillas completas (backend, providers, módulo, OIDC para GitHub) en [references/layout.md](references/layout.md).

## Workspaces vs directorios
- **Directorios por entorno (por defecto)**: backends, cuentas y versiones de módulos pueden diferir; el entorno es explícito en la ruta; imposible aplicar staging en production por olvidar `workspace select`.
- **Workspaces CLI**: solo para copias efímeras idénticas de un mismo entorno (preview por PR, sandboxes). Usa `terraform.workspace` únicamente en nombres, no en lógica condicional.
- HCP Terraform/Terraform Enterprise llaman "workspace" a otra cosa (un estado + variables + permisos); equivale a un directorio de entorno.

## Pasos
1. Leer estado actual: `terraform init` (con backend, si hay credenciales de lectura) y `terraform plan` para confirmar que no hay drift antes de cambiar nada.
2. Escribir o modificar código siguiendo las convenciones.
3. `terraform fmt -recursive`, `terraform validate`, `tflint --recursive`, `checkov -d .` (o `trivy config .`). Atajo: `scripts/tf-check.sh <dir>`.
4. `terraform plan -out=tfplan` y revisar: cualquier `destroy` o `-/+` (replace) debe estar justificado y comunicado.
5. **`terraform apply`, `destroy`, `import`, `state rm/mv` o `force-unlock` solo con confirmación explícita del usuario**, y preferentemente desde el pipeline (`devops:github-actions`, sección Terraform de `references/cd.md`).

## Convenciones

### Versiones
- `required_version = "~> 1.16"` (o el minor en uso) en cada raíz; `required_providers` con `source` y restricción pesimista por major: `aws ~> 6.0`, `google ~> 8.0`, `azurerm ~> 5.0` (majors estables a septiembre de 2026; verifica en el Registry).
- Versiona `.terraform.lock.hcl`; actualiza providers de forma deliberada con `terraform init -upgrade` en un PR propio. Para CI multiplataforma: `terraform providers lock -platform=linux_amd64 -platform=darwin_arm64`.
- Módulos del Registry con versión exacta (`version = "6.2.0"`); módulos git con `?ref=<tag o SHA>`.
- OpenTofu (`tofu`) es compatible para la mayoría de casos; no mezcles binarios sobre el mismo estado.

### Estado remoto y locking
- AWS: backend `s3` con `use_lockfile = true` (locking nativo en S3, Terraform ≥ 1.10; el locking con DynamoDB está deprecado), `encrypt = true`, bucket con versioning, bloqueo de acceso público y cifrado KMS.
- GCP: backend `gcs` (locking incluido), bucket con versioning y `uniform_bucket_level_access`.
- Azure: backend `azurerm` (lease de blob como lock), autenticado con `use_oidc = true` en CI.
- El `key`/`prefix` incluye entorno y componente: `envs/production/apps.tfstate`.
- Nunca estado local compartido ni en git; nunca editar el estado a mano. Usa bloques `moved`, `import` y `removed` en lugar de `state mv`/`import` imperativos.

### Variables y outputs
- Toda variable con `type` y `description`; `validation` para formatos (CIDR, entornos permitidos); sin `default` en valores que deben variar por entorno.
- `sensitive = true` en variables/outputs sensibles (no los cifra en el estado; solo los oculta en la salida).
- Secretos: no en `.tfvars` versionados. Léelos del gestor de secretos (data source) o, mejor, usa argumentos write-only (`*_wo`, Terraform ≥ 1.11) y recursos `ephemeral` para que no lleguen al estado; o deja que el servicio los genere (p. ej. `manage_master_user_password` en RDS).
- Outputs con `description`, solo lo que otros consumen (IDs, ARNs, endpoints).
- `locals` para nombres y tags calculados; evita lógica compleja en `count`; prefiere `for_each` con mapas de claves estables.

### Naming y tags
- Nombres HCL en `snake_case`, sin repetir el tipo (`aws_s3_bucket.assets`, no `aws_s3_bucket.assets_bucket`); `this` para el recurso principal de un módulo.
- Nombres cloud: `<proyecto>-<entorno>-<componente>` (p. ej. `acme-prod-api`), en minúsculas con guiones, calculados en `locals`.
- Tags obligatorios: `project`, `environment`, `owner`/`team`, `managed_by = "terraform"`, `repo`. En AWS con `default_tags` del provider; en GCP con `default_labels`; en Azure pásalos como variable a cada recurso.

### Seguridad
- IAM mínimo: políticas por recurso con `aws_iam_policy_document`, nada de `*` en `Action` y `Resource` juntos.
- CI con OIDC (rol de solo lectura para `plan`, rol separado para `apply` limitado a la rama/entorno), sin llaves estáticas.
- `lifecycle { prevent_destroy = true }` en datos críticos (bases de datos, buckets de estado, KMS) y `deletion_protection` donde exista.
- Buckets privados, cifrado en reposo, logs de acceso, sin `0.0.0.0/0` en security groups salvo el balanceador público 443.

### Testing
- `terraform test` (archivos `*.tftest.hcl`) para módulos, con `command = plan` para no crear recursos o con `mock_provider`.
- Checks de política con checkov/trivy en CI; excepciones documentadas en línea (`#checkov:skip=CKV_AWS_XXX: motivo`).

### Comandos habituales (seguros)
```bash
terraform fmt -recursive                 # formatea (el hook del plugin lo hace al editar .tf)
terraform init -backend=false            # valida sin tocar el estado remoto
terraform validate
tflint --init && tflint --recursive
checkov -d . --framework terraform --quiet
terraform plan -input=false -out=tfplan  # requiere credenciales de lectura
terraform show -json tfplan | jq '[.resource_changes[] | select(.change.actions | index("delete"))] | length'
terraform state list                     # solo lectura
terraform output -json                   # cuidado: puede mostrar valores sensibles
```
Todo lo que modifica estado o infraestructura (`apply`, `destroy`, `import`, `state mv/rm`, `force-unlock`, `taint`) requiere confirmación explícita del usuario.

## Antipatrones
- Un solo estado gigante para toda la organización; o un directorio por recurso.
- Workspaces para separar staging y production en cuentas distintas.
- `provider` dentro de módulos reutilizables; `version` sin restricción o `>=` abierto.
- `terraform apply -auto-approve` local contra producción; `-target` como flujo habitual.
- Secretos en `.tfvars`, en `default` de variables o en outputs sin `sensitive`.
- `count = var.enabled ? 1 : 0` sobre listas que cambian de orden (recrea recursos); usa `for_each`.
- Copiar/pegar entornos en lugar de parametrizar un módulo.
- Ignorar `.terraform.lock.hcl` en `.gitignore`.

## Checklist final
- [ ] `fmt`, `validate`, `tflint` y `checkov` sin errores (o excepciones justificadas).
- [ ] `required_version` y providers con restricción por major; lockfile versionado.
- [ ] Backend remoto cifrado con locking; key por entorno/componente.
- [ ] Variables tipadas, descritas y validadas; sin secretos en archivos.
- [ ] Naming consistente y tags obligatorios aplicados.
- [ ] Plan revisado: sin destrucciones ni reemplazos no explicados.
- [ ] `prevent_destroy`/`deletion_protection` en recursos con datos.
- [ ] Ningún `apply` ejecutado sin confirmación explícita.

## Recursos
- [references/layout.md](references/layout.md): `.gitignore`, bootstrap del estado, backend/providers por nube, módulo de ejemplo, entorno que lo consume, OIDC de GitHub en AWS y `.tflint.hcl`. Léelo al crear una raíz o un módulo nuevo.
- `scripts/tf-check.sh [dir]`: ejecuta `fmt -check`, `init -backend=false`, `validate`, y `tflint`/`checkov`/`trivy` si están instalados. No toca el estado ni la nube. Uso: `"<carpeta de la skill terraform>/scripts/tf-check.sh" infra/envs/staging`.
- Skills relacionadas: `devops:github-actions` (plan en PR, apply con environment), `devops:kubernetes`, `core:architecture-principles`, `core:documentation-standards` (README de módulos).

# Cliente HTTP tipado para APIs NestJS / FastAPI

Léelo al crear o modificar el cliente HTTP, al integrar un endpoint nuevo o al manejar auth con refresh de token. Si el proyecto ya tiene cliente (axios, ky, openapi-fetch), adapta estas ideas a él en vez de reemplazarlo.

## 1. Tipos desde el contrato
Preferencia, de mejor a peor:
1. **Generar tipos desde OpenAPI**: NestJS con `@nestjs/swagger` expone el JSON (ruta configurada en `SwaggerModule.setup`, a menudo `/api-json`); FastAPI expone `/openapi.json`. Herramientas: `openapi-typescript` (+ `openapi-fetch`), `orval` o `@hey-api/openapi-ts`. Añade un script `api:types` en `package.json`.
2. **Zod schemas en el cliente** que validan las respuestas en el borde (útil aunque haya tipos generados si el backend no es fiable).
3. Tipos escritos a mano (último recurso; mantenlos junto a la feature).

Convenciones de naming: FastAPI suele devolver `snake_case`; NestJS `camelCase`. Decide **una** estrategia: tipos tal cual del backend, o transformación en el borde (Zod `.transform`). No mezcles.

## 2. Errores
Formatos habituales:
```jsonc
// NestJS (HttpException / ValidationPipe)
{ "statusCode": 400, "message": ["email must be an email"], "error": "Bad Request" }
// FastAPI (HTTPException)
{ "detail": "Not found" }
// FastAPI (422 validación)
{ "detail": [{ "loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error" }] }
```

```ts
// src/lib/api/errors.ts
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly fieldErrors: Record<string, string> = {},
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class NetworkError extends Error {
  name = 'NetworkError';
}

export function parseErrorBody(status: number, body: unknown): ApiError {
  const b = body as Record<string, unknown> | undefined;
  // NestJS
  if (b && 'statusCode' in b) {
    const msg = Array.isArray(b.message) ? b.message.join('\n') : String(b.message ?? 'Error');
    return new ApiError(status, msg, {}, body);
  }
  // FastAPI
  if (b && 'detail' in b) {
    if (Array.isArray(b.detail)) {
      const fieldErrors: Record<string, string> = {};
      for (const e of b.detail as { loc: (string | number)[]; msg: string }[]) {
        fieldErrors[String(e.loc.at(-1))] = e.msg;
      }
      return new ApiError(status, 'Datos inválidos', fieldErrors, body);
    }
    return new ApiError(status, String(b.detail), {}, body);
  }
  return new ApiError(status, `HTTP ${status}`, {}, body);
}
```

## 3. Cliente con fetch
```ts
// src/lib/api/client.ts
import { z } from 'zod';
import { env } from '@/lib/env';
import { tokenStorage } from '@/lib/storage';
import { ApiError, NetworkError, parseErrorBody } from './errors';

type RequestOptions<T> = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  schema?: z.ZodType<T>;
  signal?: AbortSignal;
  auth?: boolean;
};

export async function apiRequest<T>(path: string, opts: RequestOptions<T> = {}): Promise<T> {
  const { method = 'GET', body, query, schema, signal, auth = true } = opts;
  const url = new URL(path, env.EXPO_PUBLIC_API_URL);
  for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined) url.searchParams.set(k, String(v));

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth) {
    const token = await tokenStorage.getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(url.toString(), { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined, signal });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new NetworkError('Sin conexión con el servidor');
  }

  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => undefined);
  if (!res.ok) throw parseErrorBody(res.status, data);
  return schema ? schema.parse(data) : (data as T);
}
```
- TanStack Query pasa `signal` a `queryFn`: propágalo para cancelar al desmontar.
- Timeouts: `AbortSignal.timeout(ms)` si el runtime lo soporta; si no, `AbortController` + `setTimeout`.
- `expo/fetch` ofrece una implementación compatible con WinterCG (streaming); úsala solo si necesitas esas capacidades.

## 4. Funciones por feature
```ts
// src/features/orders/api/orders.schemas.ts
export const orderSchema = z.object({
  id: z.string(),
  code: z.string(),
  status: z.enum(['pending', 'paid', 'shipped']),
  total: z.number(),
  createdAt: z.string(),
});
export type Order = z.infer<typeof orderSchema>;
export const orderPageSchema = z.object({ items: z.array(orderSchema), total: z.number(), page: z.number(), size: z.number() });

// src/features/orders/api/orders.api.ts
export const getOrder = (id: string, signal?: AbortSignal) =>
  apiRequest(`/orders/${encodeURIComponent(id)}`, { schema: orderSchema, signal });

export const getOrders = (params: { page: number; size: number }, signal?: AbortSignal) =>
  apiRequest('/orders', { query: params, schema: orderPageSchema, signal });

export const createOrder = (input: CreateOrderInput) =>
  apiRequest('/orders', { method: 'POST', body: input, schema: orderSchema });
```
Ajusta la forma de paginación a la real del backend (offset/limit, page/size, cursor).

## 5. Paginación infinita
```ts
export function useOrdersInfinite(size = 20) {
  return useInfiniteQuery({
    queryKey: [...orderKeys.all, 'infinite', size],
    queryFn: ({ pageParam, signal }) => getOrders({ page: pageParam, size }, signal),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * last.size < last.total ? last.page + 1 : undefined),
    select: (d) => d.pages.flatMap((p) => p.items),
  });
}
```
En la lista: `onEndReached={() => hasNextPage && !isFetchingNextPage && fetchNextPage()}`.

## 6. Auth: tokens y refresh
```ts
// src/lib/storage.ts
import * as SecureStore from 'expo-secure-store';

const ACCESS = 'auth.accessToken';
const REFRESH = 'auth.refreshToken';

export const tokenStorage = {
  getAccessToken: () => SecureStore.getItemAsync(ACCESS),
  getRefreshToken: () => SecureStore.getItemAsync(REFRESH),
  async setTokens(access: string, refresh?: string) {
    await SecureStore.setItemAsync(ACCESS, access);
    if (refresh) await SecureStore.setItemAsync(REFRESH, refresh);
  },
  async clear() {
    await Promise.all([SecureStore.deleteItemAsync(ACCESS), SecureStore.deleteItemAsync(REFRESH)]);
  },
};
```
Refresh ante 401 (una sola vez, con lock para peticiones concurrentes):
```ts
let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  refreshing ??= (async () => {
    const refresh = await tokenStorage.getRefreshToken();
    if (!refresh) return null;
    try {
      const res = await apiRequest('/auth/refresh', { method: 'POST', body: { refreshToken: refresh }, auth: false, schema: tokensSchema });
      await tokenStorage.setTokens(res.accessToken, res.refreshToken);
      return res.accessToken;
    } catch {
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}
```
- En `apiRequest`, si `status === 401` y `auth`, llama `refreshAccessToken()` y reintenta **una vez**; si devuelve `null`, `tokenStorage.clear()`, limpia el store de sesión y `queryClient.clear()` → el guard de Expo Router lleva a login.
- El endpoint y el formato de refresh dependen del backend: confírmalo en el código NestJS (`AuthController`) o FastAPI (`/auth/...`, `OAuth2PasswordBearer`). FastAPI con `OAuth2PasswordRequestForm` espera `application/x-www-form-urlencoded` en el login (`username`, `password`), no JSON.
- No registres tokens en logs ni en herramientas de crash reporting.

## 7. Subida de archivos
```ts
const form = new FormData();
form.append('file', { uri: asset.uri, name: asset.fileName ?? 'photo.jpg', type: asset.mimeType ?? 'image/jpeg' } as unknown as Blob);
await fetch(url, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form }); // sin Content-Type manual
```
- No fijes `Content-Type` a mano con `FormData` (se pierde el boundary).
- Para archivos grandes o en segundo plano, considera `expo-file-system` (API de uploads) según la versión del SDK.

## 8. Tests
- Mockea `apiRequest` o la capa de red con MSW (`msw/native`) o `jest.fn()` sobre `global.fetch`; ver `mobile:mobile-testing`.
- Crea un `QueryClient` nuevo por test con `retry: false`.

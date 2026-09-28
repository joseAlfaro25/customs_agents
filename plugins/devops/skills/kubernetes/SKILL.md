---
name: kubernetes
description: "Manifiestos Kubernetes listos para producción: Deployment, Service, Ingress/Gateway API, ConfigMap, Secret y External Secrets, probes, requests/limits, HPA, PDB, namespaces, Kustomize/Helm y estrategias de rollout. Usar al desplegar o revisar servicios en Kubernetes."
---

# kubernetes

## Objetivo
Desplegar los servicios del stack (Next.js, NestJS, FastAPI, LangGraph) con manifiestos declarativos, seguros por defecto, autoescalables y con rollouts sin downtime, organizados con Kustomize (o Helm cuando el chart se distribuye).

## Cuándo aplicarla
- Crear los manifiestos de un servicio nuevo o su chart de Helm.
- Añadir un entorno (overlay), escalar, exponer por Ingress/Gateway o gestionar secretos.
- Revisar un despliegue con reinicios, OOMKilled, downtime en rollouts o sin límites.

Carga antes `core:project-context` y revisa si ya existe `deploy/`, `k8s/`, `charts/` o un repo GitOps. Para la imagen, `devops:docker`; para el pipeline, `devops:github-actions`.

## Estructura recomendada (Kustomize)
```
deploy/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── hpa.yaml
│   ├── pdb.yaml
│   └── serviceaccount.yaml
└── overlays/
    ├── staging/
    │   ├── kustomization.yaml     # namespace, imagen por digest, réplicas, patches
    │   ├── configmap.env
    │   ├── externalsecret.yaml
    │   └── httproute.yaml         # o ingress.yaml
    └── production/
        └── ...
```
- Un namespace por servicio y entorno (`api-staging`, `api-production`) o por equipo; nunca `default`.
- Helm cuando el paquete se reutiliza entre equipos o se publica; Kustomize para apps propias. No mezcles ambos en el mismo servicio salvo `helmCharts` de terceros.
- Plantillas completas en [references/manifests.md](references/manifests.md).

## Pasos
1. Identificar puerto, endpoints de health (`/health` liveness, `/ready` readiness), variables de entorno y secretos que necesita la app.
2. Escribir `base/` con Deployment, Service, ServiceAccount, HPA y PDB.
3. Crear overlays por entorno: namespace, imagen por digest, réplicas/recursos, config y exposición.
4. Secretos vía External Secrets Operator (o Sealed Secrets/SOPS si no hay gestor de secretos). Nunca `Secret` con valores en el repo.
5. Validar sin tocar el cluster: `kustomize build overlays/staging | kubeconform -strict -summary`, luego `kubectl apply --dry-run=server` y `kubectl diff -k` si hay acceso de lectura.
6. **Aplicar solo con confirmación explícita del usuario** y contra el contexto correcto (`kubectl config current-context`). Nunca `kubectl delete` de namespaces o recursos sin confirmación.

## Convenciones

### Etiquetas y metadatos
- Labels recomendadas: `app.kubernetes.io/name`, `app.kubernetes.io/instance`, `app.kubernetes.io/version`, `app.kubernetes.io/component`, `app.kubernetes.io/part-of`, `app.kubernetes.io/managed-by`.
- `spec.selector.matchLabels` es inmutable: usa solo `name` + `instance`, nunca `version`.
- Kustomize: `labels` con `includeSelectors: false` para no alterar selectores al añadir etiquetas.

### Imagen
- Referencia por digest en overlays (`images: - name: app, newName: ghcr.io/org/api, digest: sha256:...`). Nada de `:latest`; `imagePullPolicy` por defecto.

### Seguridad del Pod (alineado con Pod Security Standards `restricted`)
```yaml
securityContext:              # a nivel Pod
  runAsNonRoot: true
  runAsUser: 10001            # coincide con el USER de la imagen (node = 1000, distroless nonroot = 65532)
  fsGroup: 10001
  seccompProfile:
    type: RuntimeDefault
containers:
  - securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
```
- Con `readOnlyRootFilesystem`, monta `emptyDir` en rutas escribibles (`/tmp`, `/app/.next/cache`).
- Etiqueta el namespace con `pod-security.kubernetes.io/enforce: restricted`.
- `automountServiceAccountToken: false` salvo que la app hable con la API de Kubernetes; ServiceAccount propio por app (necesario para IRSA/EKS Pod Identity/Workload Identity).

### Probes
- `startupProbe` para arranques lentos (Next.js, modelos/embeddings cargados al inicio): protege de reinicios mientras arranca.
- `readinessProbe` → `/ready` (dependencias OK): saca el pod del Service sin reiniciarlo.
- `livenessProbe` → `/health` barato y sin dependencias externas; si la db cae, no reinicies todos los pods.
- Valores de partida: `periodSeconds: 10`, `timeoutSeconds: 3`, `failureThreshold: 3`; startup con `failureThreshold` × `periodSeconds` ≥ tiempo máximo de arranque.

### Recursos
- Siempre `requests` de CPU y memoria (el scheduler y el HPA dependen de ellos).
- Memoria: `limits.memory` = `requests.memory` para evitar OOM por sobrecompromiso.
- CPU: define `requests`; evita `limits.cpu` bajos en servicios sensibles a latencia (throttling). Si la política exige límite, déjalo holgado.
- Node: fija `NODE_OPTIONS=--max-old-space-size` a ~75 % del límite de memoria. Python: una sola réplica de uvicorn por pod.
- Mide con `kubectl top` / métricas reales y ajusta; no copies números de otro servicio.

### Configuración y secretos
- ConfigMap para configuración no sensible (generado con `configMapGenerator` para que el hash en el nombre fuerce rollout al cambiar).
- Secretos desde el gestor (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, Vault) con External Secrets Operator, API `external-secrets.io/v1`, y un `SecretStore`/`ClusterSecretStore` autenticado por identidad de workload, no por llaves.
- Inyecta con `envFrom`/`valueFrom.secretKeyRef`; para rotación sin redeploy, monta como volumen.

### Exposición
- `Service` tipo `ClusterIP`; el tráfico externo entra por Gateway API (`HTTPRoute`, `gateway.networking.k8s.io/v1`) o `Ingress` (`networking.k8s.io/v1`) con `ingressClassName` explícito.
- Para clusters nuevos prefiere Gateway API. El proyecto ingress-nginx de Kubernetes fue retirado en 2026 (verifica el estado y el controlador que use el cluster antes de proponer `Ingress` con anotaciones `nginx.ingress.kubernetes.io/*`).
- TLS con cert-manager (`cert-manager.io/cluster-issuer`) o el certificado gestionado del proveedor.
- SSE/streaming de LangGraph: aumenta timeouts de lectura del gateway/ingress y desactiva buffering.

### Escalado y disponibilidad
- `HorizontalPodAutoscaler` `autoscaling/v2` por CPU (70 %) y/o memoria; `minReplicas ≥ 2` en producción. Para colas/eventos, KEDA.
- No declares `spec.replicas` en el Deployment si hay HPA (Kustomize/GitOps lo pisarían).
- `PodDisruptionBudget` con `maxUnavailable: 1` (o `minAvailable`) para drenados de nodos.
- `topologySpreadConstraints` por zona (`topology.kubernetes.io/zone`) con `whenUnsatisfiable: ScheduleAnyway`.

### Rollouts
- `RollingUpdate` con `maxUnavailable: 0` y `maxSurge: 25%` (o 1): nunca baja la capacidad.
- Apagado limpio: la app maneja `SIGTERM`; `terminationGracePeriodSeconds` > tiempo de drenado; un `preStop` corto (`sleep` de 5 s) da tiempo a que el endpoint salga del balanceador. La acción nativa `lifecycle.preStop.sleep` evita depender de `sh` en imágenes distroless (verifica que tu versión de Kubernetes la soporte).
- `minReadySeconds: 10` y `progressDeadlineSeconds` para detectar rollouts atascados; `kubectl rollout status` en el pipeline y `kubectl rollout undo` como rollback.
- Canary / blue-green: Argo Rollouts o Flagger, o pesos en `HTTPRoute`. Migraciones de base de datos en un `Job` (o hook de Helm/Argo) antes del rollout y compatibles hacia atrás (expand/contract).

### Helm
- Chart en `charts/<app>/` con `values.yaml` documentado, `values.schema.json` y valores por entorno en `values-<env>.yaml`.
- `helm lint`, `helm template ... | kubeconform`, y `helm upgrade --install --atomic --wait --timeout 5m` (solo con confirmación). Helm 4 es la versión estable actual; verifica compatibilidad de plugins y CI.
- No metas secretos en `values`; usa ExternalSecret dentro del chart.

## Antipatrones
- Pods sueltos o `ReplicaSet` manual en vez de Deployment.
- Sin `requests`/`limits`, o `limits.cpu: 100m` en una API Node.
- Liveness que consulta la base de datos (reinicios en cascada).
- `Secret` en YAML versionado (base64 no es cifrado); `stringData` con valores reales en git.
- `:latest`, `imagePullPolicy: Always` para compensarlo.
- `hostPath`, `privileged: true`, `hostNetwork` en apps.
- Service `LoadBalancer` por cada microservicio en lugar de un Gateway/Ingress compartido.
- `kubectl apply` manual en producción fuera del pipeline/GitOps; `kubectl edit` en caliente.
- `replicas` fijo junto con HPA.

## Checklist final
- [ ] Namespace propio con Pod Security `restricted`.
- [ ] Labels `app.kubernetes.io/*` y selector estable.
- [ ] Imagen por digest; securityContext no root, read-only, `drop: [ALL]`, seccomp.
- [ ] startup/readiness/liveness diferenciadas.
- [ ] requests en todos los contenedores; memoria limit = request.
- [ ] HPA + PDB + topology spread (minReplicas ≥ 2 en prod).
- [ ] Rolling update sin pérdida de capacidad y apagado limpio.
- [ ] Config en ConfigMap con hash; secretos vía ExternalSecret.
- [ ] Exposición por Gateway/Ingress con TLS.
- [ ] `kustomize build | kubeconform -strict` y `kubectl apply --dry-run=server` sin errores.

## Recursos
- [references/manifests.md](references/manifests.md): base Kustomize completa (Deployment, Service, HPA, PDB, ServiceAccount), overlays por entorno, HTTPRoute e Ingress, ExternalSecret y Job de migraciones. Léelo al crear manifiestos.
- Validación: `kubeconform`, `kube-linter lint`, `checkov -d deploy/`, `kubectl diff`.
- Skills relacionadas: `devops:docker`, `devops:github-actions` (deploy por environment), `devops:terraform` (cluster, IAM de workloads), `core:architecture-principles`.

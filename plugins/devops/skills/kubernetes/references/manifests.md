# Manifiestos de referencia (Kustomize)

Ejemplo para un servicio `api` (NestJS o FastAPI) en el puerto 8000. Cambia nombre, puerto, rutas de health, uid y recursos. APIs estables a Kubernetes 1.3x: `apps/v1`, `v1`, `autoscaling/v2`, `policy/v1`, `networking.k8s.io/v1`, `gateway.networking.k8s.io/v1`, `external-secrets.io/v1`. Verifica con `kubectl api-resources` en el cluster destino.

## base/kustomization.yaml
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - serviceaccount.yaml
  - deployment.yaml
  - service.yaml
  - hpa.yaml
  - pdb.yaml
labels:
  - pairs:
      app.kubernetes.io/part-of: myproduct
      app.kubernetes.io/managed-by: kustomize
    includeSelectors: false
```

## base/serviceaccount.yaml
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: api
  labels:
    app.kubernetes.io/name: api
automountServiceAccountToken: false
```

## base/deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  labels:
    app.kubernetes.io/name: api
    app.kubernetes.io/component: backend
spec:
  # Sin replicas: las gestiona el HPA
  revisionHistoryLimit: 5
  minReadySeconds: 10
  progressDeadlineSeconds: 600
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 25%
  selector:
    matchLabels:
      app.kubernetes.io/name: api
      app.kubernetes.io/instance: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api
        app.kubernetes.io/instance: api
    spec:
      serviceAccountName: api
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: topology.kubernetes.io/zone
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: api
      containers:
        - name: api
          image: app            # reemplazada por digest en el overlay
          ports:
            - name: http
              containerPort: 8000
          envFrom:
            - configMapRef:
                name: api-config
            - secretRef:
                name: api-secrets
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              memory: 512Mi
          startupProbe:
            httpGet: { path: /health, port: http }
            periodSeconds: 5
            failureThreshold: 24     # hasta 2 min para arrancar
          readinessProbe:
            httpGet: { path: /ready, port: http }
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          livenessProbe:
            httpGet: { path: /health, port: http }
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          lifecycle:
            preStop:
              sleep:
                seconds: 5           # acción nativa; en clusters antiguos usa exec: ["sh","-c","sleep 5"]
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
```
Next.js: puerto 3000, `runAsUser: 1000` (usuario `node`), health `/api/health` y un `emptyDir` extra en `/app/.next/cache`. Node: añade `NODE_OPTIONS=--max-old-space-size=384` para 512Mi.

## base/service.yaml
```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  labels:
    app.kubernetes.io/name: api
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: api
    app.kubernetes.io/instance: api
  ports:
    - name: http
      port: 80
      targetPort: http
```

## base/hpa.yaml
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
```

## base/pdb.yaml
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: api
      app.kubernetes.io/instance: api
```

## overlays/production/kustomization.yaml
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: api-production
resources:
  - namespace.yaml
  - ../../base
  - externalsecret.yaml
  - httproute.yaml
images:
  - name: app
    newName: ghcr.io/mi-org/api
    digest: sha256:0000000000000000000000000000000000000000000000000000000000000000  # lo actualiza el pipeline
configMapGenerator:
  - name: api-config
    envs:
      - configmap.env
patches:
  - target:
      kind: HorizontalPodAutoscaler
      name: api
    patch: |-
      - op: replace
        path: /spec/minReplicas
        value: 3
  - target:
      kind: Deployment
      name: api
    patch: |-
      - op: replace
        path: /spec/template/spec/containers/0/resources
        value:
          requests: { cpu: 500m, memory: 1Gi }
          limits: { memory: 1Gi }
```

`overlays/production/namespace.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: api-production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
```

`overlays/production/configmap.env` (sin secretos):
```
LOG_LEVEL=info
APP_ENV=production
CORS_ORIGINS=https://app.example.com
```

## ExternalSecret (External Secrets Operator)
```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: api-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: aws-secrets-manager      # definido por plataforma, autenticado con IRSA/Pod Identity
  target:
    name: api-secrets
    creationPolicy: Owner
  dataFrom:
    - extract:
        key: production/api        # secreto JSON: DATABASE_URL, REDIS_URL, OPENAI_API_KEY...
```
Sin gestor de secretos: Sealed Secrets (`kubeseal`) o SOPS con age/KMS (integrado en Flux/Argo CD vía plugin). Nunca `kind: Secret` con valores en git.

## Exposición con Gateway API (preferido)
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api
spec:
  parentRefs:
    - name: public-gateway         # Gateway compartido gestionado por plataforma
      namespace: gateway-system
  hostnames:
    - api.example.com
  rules:
    - matches:
        - path: { type: PathPrefix, value: / }
      backendRefs:
        - name: api
          port: 80
      timeouts:
        request: 300s              # streaming/SSE de LangGraph; verifica soporte del controlador
```
Canary por pesos: dos `backendRefs` (`api-stable` weight 90, `api-canary` weight 10).

## Alternativa con Ingress
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: alb             # o la clase del controlador instalado (traefik, nginx de F5, gce...)
  tls:
    - hosts: [api.example.com]
      secretName: api-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  name: http
```
Las anotaciones son específicas de cada controlador: no copies anotaciones de ingress-nginx (retirado en marzo de 2026) a otro controlador.

## Job de migraciones (antes del rollout)
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  generateName: api-migrate-
spec:
  backoffLimit: 1
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: api
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile: { type: RuntimeDefault }
      containers:
        - name: migrate
          image: ghcr.io/mi-org/api@sha256:...   # mismo digest que se va a desplegar
          command: ["alembic", "upgrade", "head"] # NestJS/Prisma: ["npx", "prisma", "migrate", "deploy"]
          envFrom:
            - secretRef: { name: api-secrets }
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: ["ALL"] }
```
Con `generateName` se crea con `kubectl create -f`, no con `apply`; en Argo CD usa el hook `argocd.argoproj.io/hook: PreSync`, en Helm `helm.sh/hook: pre-upgrade`.

## Validación local
```bash
kustomize build deploy/overlays/production > /tmp/rendered.yaml
kubeconform -strict -summary -ignore-missing-schemas /tmp/rendered.yaml
kube-linter lint /tmp/rendered.yaml
kubectl apply --dry-run=server -f /tmp/rendered.yaml   # requiere acceso de lectura; no cambia nada
kubectl diff -f /tmp/rendered.yaml
```
`-ignore-missing-schemas` evita fallos por CRDs (ExternalSecret, HTTPRoute); para validarlos, añade el catálogo de schemas de CRDs (`-schema-location`).

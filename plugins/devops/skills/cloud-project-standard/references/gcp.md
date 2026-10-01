# Google Cloud — referencia del estándar cloud

Complementa `SKILL.md`. Cada sección responde a la del mismo número allí. Verifica nombres de servicios, límites y precios en la documentación de Google Cloud: cambian.

## 2. Organización, folders y proyectos
- **Organization → Folders (`prod`, `nonprod`) → Proyectos** por entorno y servicio (`acme-api-prod`, `acme-api-staging`). Producción en proyecto propio. Proyectos aparte para `logging` (sinks centralizados) y `tooling` (estado de Terraform, registro compartido).
- **Organization Policies** (guardas), como mínimo:
  - `iam.disableServiceAccountKeyCreation` (sin llaves JSON);
  - `iam.allowedPolicyMemberDomains` (solo identidades de tu dominio);
  - `storage.publicAccessPrevention` (sin buckets públicos);
  - `compute.vmExternalIpAccess` (sin IP pública en VMs) y `gcp.resourceLocations` (regiones permitidas);
  - `iam.automaticIamGrantsForDefaultServiceAccounts` (las service accounts por defecto no reciben el rol Editor).
- Personas: **Cloud Identity / Google Workspace** con SSO y verificación en dos pasos; permisos a **grupos**, no a usuarios sueltos.

## 3. IAM
- Una **service account por workload** (`sa-<servicio>-<entorno>`), creada en IaC. No uses la service account por defecto de Compute/App Engine.
- Roles **predefinidos o personalizados** y mínimos; nunca los básicos (`owner`, `editor`, `viewer`) en workloads. Concede a nivel del recurso (bucket, secreto, tópico) antes que a nivel de proyecto. Usa **IAM Conditions** cuando ayude.
- Sin llaves de service accounts:
  - Cloud Run / Functions / VMs: service account **adjunta**;
  - GKE: **Workload Identity** (vincula la KSA con la GSA, `devops:kubernetes`);
  - CI: **Workload Identity Federation** con GitHub.
- Permisos sensibles (`roles/iam.serviceAccountTokenCreator`, `serviceAccountUser`, `iam.securityAdmin`) solo cuando sean imprescindibles y sobre la service account concreta.
- Revisa con **Policy Analyzer** y el **IAM Recommender**.

Workload Identity Federation para GitHub (restringido al repositorio):

```hcl
resource "google_iam_workload_identity_pool" "ci" {
  workload_identity_pool_id = "github-ci"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.ci.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  # Obligatorio en la práctica: sin condición, cualquier repo de GitHub podría autenticarse
  attribute_condition = "assertion.repository == 'acme/mi-repo'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Solo ese repo puede actuar como la service account de despliegue
resource "google_service_account_iam_member" "ci_wif" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.ci.name}/attribute.repository/acme/mi-repo"
}
```

Para producción, usa service accounts distintas para `plan` (solo lectura) y `deploy`, y limita su uso al environment protegido.

## 4. Secretos
- **Secret Manager**: un secreto por valor, con **versiones**; el workload accede con `roles/secretmanager.secretAccessor` **sobre ese secreto**, no sobre el proyecto.
- Cloud Run / Functions: monta el secreto como variable o volumen por referencia; GKE: CSI driver de Secret Manager o External Secrets.
- Rotación con notificaciones (Pub/Sub) y **Cloud KMS** (CMEK) para datos o secretos que lo exijan.
- No pongas valores de secretos en variables de Terraform ni en `*.tfvars`; referencia el secreto.

## 5. Red
- VPC en **modo personalizado** (nunca la red `default`), subredes regionales con **Private Google Access** para llegar a las APIs sin IP pública.
- Egreso con **Cloud NAT**. Cloud SQL y otros servicios gestionados por **IP privada** (private services access / Private Service Connect).
- **Reglas de firewall** mínimas por etiqueta o service account; ningún `0.0.0.0/0` salvo 80/443 en el balanceador. Acceso administrativo por **IAP TCP forwarding** u **OS Login**, sin SSH abierto.
- Exposición pública por **Load Balancer externo** con certificado gestionado y **Cloud Armor**. Cloud Run privado: ingress `internal` o `internal-and-cloud-load-balancing`.
- Datos regulados: valora **VPC Service Controls**.
- **VPC Flow Logs** en subredes de producción.

## 6. Cómputo
- **Cloud Run** / Cloud Functions por defecto; GKE (Autopilot) solo si se justifica.
- **Artifact Registry** con análisis de vulnerabilidades (Artifact Analysis), tags inmutables cuando sea posible y despliegue **por digest**; políticas de limpieza para imágenes viejas.
- Cloud Run: define `min`/`max` de instancias, concurrencia, CPU/memoria y **timeout** de solicitud (revísalo para streaming); el servicio **no** se abre a `allUsers` salvo requisito (sin `--allow-unauthenticated`). La service account del servicio es una dedicada.
- Despliegues con revisiones y **tráfico gradual** / rollback a la revisión anterior.

## 7. Datos
- **Cloud SQL**: disponibilidad **regional (HA)** en producción, backups automáticos con **PITR**, `deletion_protection`, **IP privada**, sin redes autorizadas abiertas. Conexión con el **Cloud SQL Connector / Auth Proxy** y **autenticación IAM** de base de datos cuando el motor la soporte.
- **Cloud Storage**: *uniform bucket-level access*, **public access prevention** forzado, **versionado** y *lifecycle rules*; acceso externo por **signed URLs** de corta duración o CDN. CMEK si hay requisito.
- **Firestore / Spanner / BigQuery**: backups o exportaciones programadas, permisos por dataset/colección, no a nivel de proyecto.

## 8. Terraform en Google Cloud
- Provider `google` con `project` y `region` explícitos y `default_labels` (plantilla en `devops:terraform` → `references/layout.md`). Las labels solo admiten minúsculas, dígitos, `_` y `-`.
- Backend `gcs` en el proyecto `tooling`, con **versionado** del bucket y acceso solo para la service account de Terraform.
- Habilita las APIs en IaC:

```hcl
resource "google_project_service" "apis" {
  for_each = toset(["run.googleapis.com", "secretmanager.googleapis.com", "artifactregistry.googleapis.com"])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}
```

## 11. Observabilidad y auditoría
- **Cloud Audit Logs**: *Admin Activity* siempre activo; habilita **Data Access** en los servicios sensibles. Sink organizacional hacia el proyecto `logging` con retención definida.
- **Cloud Logging**: buckets de logs con retención explícita; logs estructurados (JSON) sin PII ni secretos.
- **Cloud Monitoring**: políticas de alerta (errores, latencia, saturación) con canal de notificación de guardia; trazas con **Cloud Trace** / OpenTelemetry y **Error Reporting**.
- **Security Command Center** en producción cuando la organización lo incluya.

## 12. Costos
- **Billing budgets** por proyecto con alertas al 80 % y 100 % (real y pronóstico) hacia un canal o tópico de Pub/Sub; exportación de billing a BigQuery para analizar.
- Labels de asignación de costos (`project`, `environment`, `owner`, `cost_center`).
- Drivers típicos: egreso de red, Cloud NAT, ingesta de Cloud Logging, instancias mínimas siempre encendidas, Cloud SQL sobredimensionado o ocioso.

## 13. Preflight de CLI (solo lectura)

```bash
gcloud config list                              # proyecto, cuenta y región efectivos
gcloud config get-value project                 # ¿en qué proyecto estoy?
gcloud auth list                                # cuenta activa (sin mostrar tokens)
gcloud projects describe "$(gcloud config get-value project)"
```

Confirma proyecto, región y entorno **antes** de proponer cualquier cambio. Los comandos que crean, modifican o borran (`create`, `delete`, `update`, `deploy`, `add-iam-policy-binding`, `services enable`, `gcloud storage rm|mv|rsync`...) requieren confirmación explícita; nunca imprimas tokens (`gcloud auth print-access-token`) ni guardes llaves.

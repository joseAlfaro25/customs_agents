# AWS — referencia del estándar cloud

Complementa `SKILL.md`. Cada sección responde a la del mismo número allí. Verifica nombres de servicios, límites y precios en la documentación de AWS: cambian.

## 2. Cuentas y guardas
- **AWS Organizations** con una OU por tipo de carga (`workloads-prod`, `workloads-nonprod`) y cuentas separadas `dev`, `staging`, `production`. Cuentas aparte para `log-archive` y `security` si la organización las tiene.
- **SCP** (guardas a nivel de OU), como mínimo: denegar apagar o modificar CloudTrail, denegar salir de la organización, limitar a las regiones permitidas, denegar la creación de access keys de IAM users y de acceso público a S3 donde se pueda.
- Personas: **IAM Identity Center** (SSO + MFA). Sin IAM users para humanos. El root solo para las pocas tareas que lo exigen, con MFA y sin access keys.

## 3. IAM
- Un rol por workload:
  - ECS: **task role** (permisos de la app) distinto del **execution role** (permisos para sacar la imagen y escribir logs).
  - Lambda: rol de ejecución propio por función.
  - EKS: IRSA o EKS Pod Identity por service account (`devops:kubernetes`).
  - EC2: instance profile propio.
- Políticas con ARNs concretos y condiciones (`aws:SourceArn`, `aws:PrincipalOrgID`, etiquetas) en lugar de `*`. Usa **permission boundaries** si delegas la creación de roles.
- Revisa con **IAM Access Analyzer** (accesos externos y permisos no usados).
- **OIDC de GitHub** (proveedor `token.actions.githubusercontent.com`); confía solo en tu repositorio y, en producción, en el environment. La plantilla completa está en `devops:terraform` → `references/layout.md`. Lo esencial de la política de confianza:

```hcl
data "aws_iam_policy_document" "gha_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:acme/mi-repo:environment:production"]   # nunca "repo:acme/*" ni "*"
    }
  }
}
```

- Roles distintos para `plan` (solo lectura, asumible desde PRs) y `apply` (escritura, solo desde el environment protegido).

## 4. Secretos
- **Secrets Manager** para credenciales con rotación (bases de datos, API keys de terceros); **SSM Parameter Store `SecureString`** para configuración sensible sin rotación.
- ECS: `secrets` con `valueFrom` (ARN) en la task definition; Lambda: lectura en la inicialización con caché; EKS: External Secrets o CSI Secrets Store.
- Política de recurso/identidad: el rol del workload accede solo a `secret:<su-prefijo>/*`.
- Llave **KMS** gestionada por el cliente para los secretos y datos críticos; política de la llave con mínimo privilegio.

## 5. Red
- VPC con subredes **privadas** (cómputo y datos) y **públicas** solo para ALB/NLB y NAT. Al menos 2 AZ (3 en producción cuando se justifique).
- **Endpoints**: gateway endpoints (S3, DynamoDB) y de interfaz (ECR, Secrets Manager, CloudWatch Logs, SSM, STS) para no pasar por NAT.
- Security groups que se referencian entre sí (`source_security_group_id`), sin CIDR abiertos salvo 80/443 en el balanceador público. **WAF** en ALB/CloudFront.
- Administración por **SSM Session Manager** (sin puerto 22, sin bastion).
- **VPC Flow Logs** en producción hacia CloudWatch o S3.

## 6. Cómputo
- Lambda / **ECS Fargate** / App Runner por defecto; EKS solo si se justifica.
- **ECR**: `scan_on_push`, tags **inmutables**, política de ciclo de vida para limpiar imágenes viejas, replicación solo si hace falta. Se despliega por digest.
- ECS: `deployment_circuit_breaker { enable = true, rollback = true }`, health checks del target group alineados con la app y `stopTimeout` suficiente para el cierre ordenado.
- ALB: el `idle_timeout` (60 s por defecto) corta streams largos; súbelo o usa keep-alive/heartbeats para SSE/LLM.
- Lambda: memoria y timeout explícitos, DLQ o destinos de error, `reserved_concurrency` cuando proteja a una base de datos.

## 7. Datos
- **RDS/Aurora**: `multi_az` (o clúster Aurora con réplicas) en producción, `storage_encrypted = true`, `backup_retention_period` > 0 con PITR, `deletion_protection = true`, subredes privadas, `publicly_accessible = false`. Autenticación **IAM** a la base (token de ~15 minutos) cuando el motor la soporte.
- **S3**: *Block Public Access* a nivel de **cuenta**, cifrado por defecto (SSE-S3 o SSE-KMS), **versionado**, reglas de ciclo de vida y política de bucket que **deniegue** `aws:SecureTransport = false`. Acceso externo por URLs prefirmadas de corta duración o CloudFront con OAC.
- **DynamoDB**: PITR y cifrado activos; capacidad bajo demanda salvo carga predecible.

## 8. Terraform en AWS
- Provider con `allowed_account_ids` y `default_tags` (plantilla en `devops:terraform` → `references/layout.md`).
- Backend S3 con `encrypt = true` y bloqueo nativo (`use_lockfile`; verifica que tu versión de Terraform lo soporte); el bucket de estado en la cuenta de herramientas, versionado y con acceso público bloqueado.

## 11. Observabilidad y auditoría
- **CloudTrail** organizacional, multirregión, con validación de archivos de log, hacia un bucket de la cuenta `log-archive`.
- **CloudWatch Logs**: `retention_in_days` siempre definido; alarmas a SNS → canal de guardia. Trazas con OpenTelemetry/X-Ray.
- **GuardDuty**, **Security Hub** y **AWS Config** en producción cuando la organización los incluya.

## 12. Costos
- **AWS Budgets** por cuenta con alertas al 80 % y 100 % (real y pronóstico); **Cost Anomaly Detection** activo.
- Activa las etiquetas de asignación de costos (`project`, `environment`, `owner`, `cost_center`).
- Drivers típicos: NAT Gateway (horas + datos), transferencia entre AZ y a internet, ingesta de CloudWatch Logs, RDS/EKS ociosos, snapshots huérfanos.

## 13. Preflight de CLI (solo lectura)

```bash
aws sts get-caller-identity                 # ¿qué cuenta y qué rol soy?
aws configure list                          # perfil y región efectivos
aws ec2 describe-regions --query 'Regions[].RegionName' --output text   # opcional
```

Confirma cuenta, región y entorno **antes** de proponer cualquier cambio. Los comandos que crean, modifican o borran (`create-*`, `delete-*`, `put-*`, `update-*`, `terminate-*`, `attach-*`, `aws s3 rm|rb|mv|sync`, `lambda invoke`...) requieren confirmación explícita; nunca imprimas ni guardes las credenciales de la sesión.

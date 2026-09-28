# Terraform: plantillas de estructura

Versiones de referencia (septiembre de 2026): Terraform 1.16.x, AWS provider 6.x, Google 8.x, AzureRM 5.x, tflint 0.64. Verifica en el Registry/GitHub antes de fijarlas.

## .gitignore
```gitignore
.terraform/
*.tfstate
*.tfstate.*
crash.log
crash.*.log
*.tfplan
tfplan
override.tf
override.tf.json
*_override.tf
*_override.tf.json
.terraformrc
terraform.rc
# tfvars con secretos (los no sensibles sí se versionan)
*.secret.tfvars
*.auto.tfvars.local
```
No ignores `.terraform.lock.hcl`.

## bootstrap/ (bucket de estado, AWS)
Se aplica una sola vez con estado local (o migrado después al propio bucket con `terraform init -migrate-state`).
```hcl
resource "aws_s3_bucket" "tfstate" {
  bucket = "acme-tfstate-${data.aws_caller_identity.current.account_id}"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_caller_identity" "current" {}
```

## envs/<env>/versions.tf
```hcl
terraform {
  required_version = "~> 1.16"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
```

## envs/<env>/backend.tf
AWS:
```hcl
terraform {
  backend "s3" {
    bucket       = "acme-tfstate-123456789012"
    key          = "envs/staging/apps.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true   # locking nativo en S3; no uses dynamodb_table (deprecado)
  }
}
```
GCP:
```hcl
terraform {
  backend "gcs" {
    bucket = "acme-tfstate"
    prefix = "envs/staging/apps"
  }
}
```
Azure:
```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "acmetfstate"
    container_name       = "tfstate"
    key                  = "envs/staging/apps.tfstate"
    use_oidc             = true
    use_azuread_auth     = true
  }
}
```
Los backends no aceptan variables: si necesitas parametrizar, usa `terraform init -backend-config=backend.staging.hcl`.

## envs/<env>/providers.tf
```hcl
provider "aws" {
  region = var.region

  # Evita aplicar en la cuenta equivocada
  allowed_account_ids = [var.account_id]

  default_tags {
    tags = local.tags
  }
}

locals {
  name_prefix = "${var.project}-${var.environment}"
  tags = {
    project     = var.project
    environment = var.environment
    owner       = var.owner
    managed_by  = "terraform"
    repo        = "github.com/acme/infra"
  }
}
```
GCP: `provider "google" { project = var.project_id, region = var.region, default_labels = local.labels }` (las labels solo admiten minúsculas, dígitos, `_` y `-`).

## envs/<env>/variables.tf
```hcl
variable "project" {
  type        = string
  description = "Nombre corto del proyecto, usado como prefijo de recursos."
}

variable "environment" {
  type        = string
  description = "Entorno de despliegue."
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment debe ser dev, staging o production."
  }
}

variable "region" {
  type        = string
  description = "Región AWS."
}

variable "account_id" {
  type        = string
  description = "ID de la cuenta AWS permitida para este entorno."
}

variable "owner" {
  type        = string
  description = "Equipo responsable."
}
```

`envs/staging/terraform.tfvars` (sin secretos):
```hcl
project     = "acme"
environment = "staging"
region      = "us-east-1"
account_id  = "123456789012"
owner       = "platform"
```

## Módulo de ejemplo: modules/ecr-repository
`versions.tf`:
```hcl
terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0, < 7.0"
    }
  }
}
```
`variables.tf`:
```hcl
variable "name" {
  type        = string
  description = "Nombre del repositorio."
}

variable "untagged_expiration_days" {
  type        = number
  description = "Días antes de expirar imágenes sin tag."
  default     = 14
}

variable "tags" {
  type        = map(string)
  description = "Tags adicionales."
  default     = {}
}
```
`main.tf`:
```hcl
resource "aws_ecr_repository" "this" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "KMS"
  }
  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expirar imágenes sin tag"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = var.untagged_expiration_days
      }
      action = { type = "expire" }
    }]
  })
}
```
`outputs.tf`:
```hcl
output "repository_url" {
  description = "URL del repositorio para docker push."
  value       = aws_ecr_repository.this.repository_url
}

output "repository_arn" {
  description = "ARN del repositorio, para políticas IAM."
  value       = aws_ecr_repository.this.arn
}
```
Uso desde un entorno:
```hcl
module "api_repository" {
  source = "../../modules/ecr-repository"
  name   = "${local.name_prefix}-api"
}
```

## OIDC de GitHub Actions en AWS
```hcl
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # thumbprint_list ya no es obligatorio en versiones recientes del provider; verifica
}

data "aws_iam_policy_document" "github_deploy_trust" {
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
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:acme/api:environment:${var.environment}"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = "${local.name_prefix}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_deploy_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "ecr_push" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]   # esta acción no admite restricción por recurso
  }
  statement {
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [module.api_repository.repository_arn]
  }
}

resource "aws_iam_role_policy" "github_deploy_ecr" {
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.ecr_push.json
}
```
GCP: `google_iam_workload_identity_pool` + `google_iam_workload_identity_pool_provider` con `attribute_condition = "assertion.repository == 'acme/api'"`. Azure: `azuread_application_federated_identity_credential` con `subject = "repo:acme/api:environment:production"`.

## Secretos sin pasar por el estado
```hcl
# La contraseña la genera y rota RDS en Secrets Manager
resource "aws_db_instance" "main" {
  # ...
  manage_master_user_password = true
  deletion_protection         = true
}
```
Si debes pasar un secreto, usa un argumento write-only cuando el recurso lo ofrezca (p. ej. `password_wo` + `password_wo_version`, Terraform ≥ 1.11) con una variable `ephemeral = true`. Revisa la documentación del recurso concreto.

## .tflint.hcl
```hcl
plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

plugin "aws" {
  enabled = true
  version = "0.49.0"   # última a 2026-09; verifica en tflint-ruleset-aws
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}
```
Equivalentes: `tflint-ruleset-google`, `tflint-ruleset-azurerm`. Ejecuta `tflint --init` antes de `tflint --recursive`.

## Refactors seguros
```hcl
moved {
  from = aws_s3_bucket.assets_bucket
  to   = aws_s3_bucket.assets
}

import {
  to = aws_s3_bucket.legacy
  id = "acme-legacy-bucket"
}

removed {
  from = aws_s3_bucket.old
  lifecycle {
    destroy = false   # lo saca del estado sin borrarlo
  }
}
```

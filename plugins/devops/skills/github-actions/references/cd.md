# Plantillas de CD

Principios: construir una sola vez, publicar por digest, promover el mismo digest entre entornos, autenticar con OIDC y aprobar producción mediante `environment`. SHAs verificados el 2026-09-28: re-verifícalos.

## 1. Reusable workflow: build + push + attestation (GHCR)

`.github/workflows/_build-image.yml`:
```yaml
name: Build image

on:
  workflow_call:
    inputs:
      context:
        type: string
        default: "."
      image-name:
        type: string
        required: true       # p. ej. ghcr.io/mi-org/api (en minúsculas)
    outputs:
      digest:
        description: Digest de la imagen publicada
        value: ${{ jobs.build.outputs.digest }}

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      packages: write
      id-token: write
      attestations: write
    outputs:
      digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1
      - uses: docker/login-action@dbcb813823bdd20940b903addbd779551569679f # v4.6.0
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: meta
        uses: docker/metadata-action@dc802804100637a589fabce1cb79ff13a1411302 # v6.2.0
        with:
          images: ${{ inputs.image-name }}
          tags: |
            type=sha,format=long
            type=ref,event=branch
            type=semver,pattern={{version}}
      - id: build
        uses: docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc # v7.4.0
        with:
          context: ${{ inputs.context }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          provenance: mode=max
          sbom: true
      - uses: actions/attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8 # v4.2.2
        with:
          subject-name: ${{ inputs.image-name }}
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true
```

Escaneo opcional antes de promover (Trivy fijado por SHA a una versión posterior al incidente de marzo de 2026):
```yaml
      - uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        with:
          image-ref: ${{ inputs.image-name }}@${{ steps.build.outputs.digest }}
          severity: CRITICAL,HIGH
          ignore-unfixed: true
          exit-code: "1"
```

Multi-arquitectura: añade `docker/setup-qemu-action` y `platforms: linux/amd64,linux/arm64` (tarda más; úsalo solo si el cluster tiene nodos arm64).

## 2. Workflow de CD con entornos

`.github/workflows/cd.yml`:
```yaml
name: CD

on:
  push:
    branches: [main]
    tags: ["v*"]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  build:
    uses: ./.github/workflows/_build-image.yml
    permissions:
      contents: read
      packages: write
      id-token: write
      attestations: write
    with:
      image-name: ghcr.io/mi-org/api

  deploy-staging:
    needs: build
    uses: ./.github/workflows/_deploy.yml
    permissions:
      contents: read
      id-token: write
    with:
      environment: staging
      digest: ${{ needs.build.outputs.digest }}

  deploy-production:
    needs: [build, deploy-staging]
    if: startsWith(github.ref, 'refs/tags/v')
    uses: ./.github/workflows/_deploy.yml
    permissions:
      contents: read
      id-token: write
    with:
      environment: production
      digest: ${{ needs.build.outputs.digest }}
```
No hace falta `secrets: inherit`: el job del reusable declara `environment`, así que usa los secrets y `vars` de ese environment directamente. Si un reusable necesita un secreto del repo, pásalo por nombre (`secrets: { NPM_TOKEN: ${{ secrets.NPM_TOKEN }} }`).

Configura en Settings → Environments: `production` con required reviewers y deployment tags `v*`; `staging` limitado a `main`.

## 3. Reusable de deploy a Kubernetes (EKS con OIDC)

`.github/workflows/_deploy.yml`:
```yaml
name: Deploy

on:
  workflow_call:
    inputs:
      environment:
        type: string
        required: true
      digest:
        type: string
        required: true

permissions:
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    environment:
      name: ${{ inputs.environment }}
      url: ${{ vars.APP_URL }}
    concurrency:
      group: deploy-${{ inputs.environment }}
      cancel-in-progress: false
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - name: kubeconfig
        run: aws eks update-kubeconfig --name "$CLUSTER" --region "$AWS_REGION"
        env:
          CLUSTER: ${{ vars.EKS_CLUSTER }}
      - name: Render y aplicar (Kustomize)
        env:
          DIGEST: ${{ inputs.digest }}
          ENV_NAME: ${{ inputs.environment }}
        run: |
          cd "deploy/overlays/$ENV_NAME"
          kustomize edit set image "app=ghcr.io/mi-org/api@${DIGEST}"
          kubectl diff -k . || true
          kubectl apply -k . --server-side
          kubectl rollout status deployment/api -n "api-$ENV_NAME" --timeout=5m
```
Alternativas: GitOps (Argo CD / Flux) donde el workflow solo actualiza el digest en el repo de manifiestos; o `helm upgrade --install --atomic --wait`. En GitOps el workflow no necesita credenciales del cluster.

## 4. OIDC por proveedor

AWS (trust policy del rol, lado Terraform en `devops:terraform`):
```json
"Condition": {
  "StringEquals": {
    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
    "token.actions.githubusercontent.com:sub": "repo:mi-org/api:environment:production"
  }
}
```

ECR en lugar de GHCR:
```yaml
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_ECR_PUSH_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - id: ecr
        uses: aws-actions/amazon-ecr-login@03f1aad4c6c7ffd436567f42f9384779290529bd # v2.1.7
      # images: ${{ steps.ecr.outputs.registry }}/api
```

GCP (Workload Identity Federation):
```yaml
      - uses: google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093 # v3.0.0
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}   # projects/123/locations/global/workloadIdentityPools/github/providers/github
          service_account: ${{ vars.GCP_DEPLOY_SA }}
```

Azure (federated credential en una App Registration / Managed Identity):
```yaml
      - uses: azure/login@a641126d1b8aa4d1fa005f4f92df94a3a4c4c906 # v3.1.0
        with:
          client-id: ${{ vars.AZURE_CLIENT_ID }}
          tenant-id: ${{ vars.AZURE_TENANT_ID }}
          subscription-id: ${{ vars.AZURE_SUBSCRIPTION_ID }}
```
Todos requieren `permissions: id-token: write` en el job.

## 5. Terraform: plan en PR, apply con aprobación

```yaml
name: Terraform

on:
  pull_request:
    paths: ["infra/**"]
  push:
    branches: [main]
    paths: ["infra/**"]

permissions:
  contents: read

jobs:
  plan:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      contents: read
      id-token: write
      pull-requests: write
    defaults:
      run:
        working-directory: infra/envs/staging
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        with:
          terraform_version: 1.16.4
      - uses: terraform-linters/setup-tflint@1cf010d3c7aef302051ccdb68c14c5dc2efa34ef # v6.3.1
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_TF_PLAN_ROLE_ARN }}   # rol de solo lectura
          aws-region: ${{ vars.AWS_REGION }}
      - run: terraform fmt -check -recursive ../..
      - run: terraform init -input=false
      - run: terraform validate
      - run: tflint --init && tflint --recursive
      - run: terraform plan -input=false -no-color -out=tfplan
      # Publica el plan como comentario o job summary (sin secretos: revisa outputs sensitive)

  apply:
    if: github.event_name == 'push'
    needs: plan
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: infra-staging           # required reviewers
    concurrency:
      group: terraform-staging
      cancel-in-progress: false
    permissions:
      contents: read
      id-token: write
    defaults:
      run:
        working-directory: infra/envs/staging
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        with:
          terraform_version: 1.16.4
      - uses: aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd # v6.3.0
        with:
          role-to-assume: ${{ vars.AWS_TF_APPLY_ROLE_ARN }}
          aws-region: ${{ vars.AWS_REGION }}
      - run: terraform init -input=false
      - run: terraform plan -input=false -out=tfplan
      - run: terraform apply -input=false tfplan
```
El `apply` vuelve a planear sobre `main` y aplica ese plan exacto. Si se quiere aplicar el plan revisado del PR, súbelo como artifact cifrado o usa una herramienta dedicada (Atlantis, HCP Terraform, Spacelift).

## 6. Expo / EAS (mobile)

Las apps Expo no se dockerizan: se construyen en EAS. El token de Expo va en un secret de environment.
```yaml
jobs:
  eas-build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: mobile-preview
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: pnpm/action-setup@ea17c68df8912ef543352723c149a84f56e3d413 # v6.1.0
      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0
        with:
          node-version-file: .nvmrc
          cache: pnpm
      - uses: expo/expo-github-action@eab7a230208c952974db8c3245cfd78402c7b385 # 9.0.0
        with:
          eas-version: latest
          packager: pnpm
          token: ${{ secrets.EXPO_TOKEN }}
      - run: pnpm install --frozen-lockfile
      - run: eas build --platform all --profile preview --non-interactive --no-wait
```
- `eas update --channel preview` para OTA en PRs; `eas submit` solo en el environment `mobile-production` con aprobación.
- Alternativa: EAS Workflows (`.eas/workflows/*.yml`), que corre dentro de Expo sin runner de GitHub.

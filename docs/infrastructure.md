# Infrastructure & Dev-Ops

The system uses a professional-grade "Infrastructure-as-Code" (IaC) approach for building, deploying, and managing the microservices stack.

---

## 1. Containerization (Docker)

All services are containerized to ensure portability and resource isolation.

### `uv` Workspace Integration
We use the **astral-sh/uv** image to manage dependencies. The services are part of a unified workspace, allowing them to share local libraries (`libs/`) without needing an external package registry.

### Network Configuration
To allow containers to communicate with both each other and local host services (like the MT5 terminal or a local Database), we implement:
- **`extra_hosts`**: Maps `host.docker.internal` to the Docker bridge IP.
- **Service Discovery**: Internal HTTP calls use Docker service names as hostnames (e.g., `http://core_service:8001`).

### Deployment Modes:
- **`server`**: Optimized for production (`infra/docker/server/docker-compose.yml`).
- **`compose`**: Full-stack inclusive of a PostgreSQL container (`infra/compose/docker-compose.yml`).

---

## 2. Infrastructure as Code (Terraform)

Located in `infra/terraform/`, our Terraform configuration automates the provisioning of Google Cloud Platform (GCP) resources.

### Provisioned Resources:
- **Compute Instance**: A high-efficiency `e2-micro` VM (Free Tier eligible) on `us-east1`.
- **Restricted Firewall**: 
    - Whitelists only the developer's public IP.
    - Whitelists Meta's (Facebook) official IP ranges for WhatsApp webhooks.
- **Secret Manager**: Secure storage for OpenAI and WhatsApp API tokens, keeping them out of source control.

### Deployment Commands:
```bash
cd infra/terraform
terraform init
terraform apply -var="project_id=YOUR_PROJECT"
```

---

## 3. Automation (GitHub Actions)

Located in `.github/workflows/deploy.yml`, the project implements full CI/CD.

### Workflow Pipeline:
1. **Trigger**: Occurs on every push to the `main` branch.
2. **Environment**: Sets up Google credentials via `GCP_SA_KEY` GitHub Secret.
3. **Terraform Flow**: Runs `init`, `fmt`, `plan`, and `apply` automatically.

### Required GitHub Secrets:
| Secret Name | Description |
|-------------|-------------|
| `GCP_SA_KEY` | Service Account JSON Key (Base64 or Raw). |
| `GCP_PROJECT_ID` | Your Google Cloud Project ID. |

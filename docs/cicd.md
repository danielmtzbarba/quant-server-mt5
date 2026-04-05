# CI/CD & Automation

This project uses GitHub Actions to automate code quality checks (QA) and infrastructure deployment (IaC).

---

## 1. Pipeline Architecture

We maintain two distinct pipelines for security and clarity:

### A. CI Workflow (Quality Assurance)
- **File**: `.github/workflows/ci.yml`
- **Triggers**: Every push to any branch and all Pull Requests.
- **Goal**: Ensure the code is lint-free, formatted correctly, and all unit tests pass before merging.
- **Steps**:
    1.  **Repo Linting**: Runs `uv run ruff check .` for static analysis.
    2.  **Formatting**: Runs `uv run ruff format --check .` to ensure PEP 8 compliance.
    3.  **Testing**: Runs `uv run pytest` for functional verification.

### B. Deploy Workflow (Infrastructure)
- **File**: `.github/workflows/deploy.yml`
- **Triggers**: Only on push to the `main` branch.
- **Goal**: Provision and update GCP resources via Terraform.
- **Steps**:
    1.  **Terraform Plan**: Generates the infrastructure change set.
    2.  **Terraform Apply**: Applies changes to Google Cloud.

---

## 2. Automated Tests List

The following tests are executed automatically in the CI pipeline to ensure service liveness:

### Core Service
- **[test_core_health.py](file:///home/danielmtz/Projects/algotrading/mt5-quant-server/services/core_service/tests/test_core_health.py)**: Verifies the API is up and the database connection is functional.

### Execution Service
- **[test_execution_health.py](file:///home/danielmtz/Projects/algotrading/mt5-quant-server/services/execution_service/tests/test_execution_health.py)**: Verifies the signal queue logic and InfluxDB connectivity.

### Messaging Service
- **[test_messaging_health.py](file:///home/danielmtz/Projects/algotrading/mt5-quant-server/services/messaging_service/tests/test_messaging_health.py)**: Verifies the WhatsApp webhook receiver and OpenAI agent initialization.

---

## 3. Local Automation

You can run the same checks locally to ensure your code passes CI before pushing:

### Formatting
```bash
# Formats all files automatically
uv run ruff format .
```

### Linting
```bash
# Fixes common issues automatically
uv run ruff check . --fix
```

### Testing
```bash
# Run all tests
uv run pytest
```

### Infrastructure Validation
```bash
cd infra/terraform
terraform fmt -check
terraform plan
```

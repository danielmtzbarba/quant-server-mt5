# Local Development & Setup

This document provides a step-by-step guide on how to set up your local development environment and run the MT5 Quant Server microservices stack.

---

## 1. Prerequisites

Before you begin, ensure you have the following installed:
- **[uv](https://github.com/astral-sh/uv)**: A fast Python package manager and resolver.
- **Docker & Docker Compose**: For containerized execution.
- **Git**: To clone the repository.
- **MetaTrader 5 (MT5)**: Downloaded and configured to accept external signals (Expert Advisor enabled).

---

## 2. Setting Up the Environment

### Clone & Initialize
1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd mt5-quant-server
   ```
2. Create and synchronize the virtual environment:
   ```bash
   uv sync
   ```

### Configuration (.env)
Copy the example environment files and fill in your specific credentials (OpenAI key, WhatsApp tokens, etc.):
```bash
cp .env.example .env
cp infra/envs/shared.env.example infra/envs/shared.env
# ... and similarly for core, execution, and messaging.
```

---

## 3. Running the Stack

### Option A: Fully Containerized (Recommended)
This mode runs the services and a dedicated PostgreSQL container.
```bash
docker compose -f infra/compose/docker-compose.yml up --build
```

### Option B: Development Mode (Docker Watch)
Enable real-time code syncing and automatic container restarts:
```bash
docker compose -f infra/docker/server/docker-compose.yml watch
```

### Option C: Individual Services (Bare Metal)
Useful for debugging specific components:
```bash
uv run --project services/core_service uvicorn app.main:app --port 8001
```

---

## 4. Testing

Automated tests are located in each service's `tests/` directory.

### Running All Tests
To run the full suite across the workspace:
```bash
uv run pytest
```

### Running Service-Specific Tests
```bash
uv run pytest services/core_service
```

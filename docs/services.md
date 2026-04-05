# Microservices Deep Dive

This document details the functional responsibilities and key API endpoints for each microservice in the MT5 Quant Server ecosystem.

---

## 1. Core Service (`core-service`)
**Role**: Central data repository and business logic for user portfolios.
- **Port**: 8001
- **Technology**: FastAPI, SQLAlchemy 2.0 (Async), PostgreSQL.

### Key Responsibilities:
- **User Management**: Storing phone numbers and account linkages.
- **Watchlist & Alerts**: Managing real-time price interest and user-defined targets.
- **Position Tracking**: Serving a cached and synchronized state of MT5 positions to other services.

### Critical Endpoints:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/users` | POST | Create/Register a new user. |
| `/watchlist` | POST/DELETE | Manage symbols for monitoring. |
| `/alerts` | POST/GET | Set and retrieve price alerts. |
| `/positions/{account_id}` | GET | Retrieve live positions for an account. |

---

## 2. Execution Service (`execution-service`)
**Role**: Market adapter and trade orchestration.
- **Port**: 8002
- **Technology**: FastAPI, InfluxDB.

### Key Responsibilities:
- **MT5 Gateway**: Serving as the bridge for trade execution commands.
- **Position Gating**: Enforcing risk limits (e.g., maximum concurrent positions) before allowing a new trade.
- **Data Sync**: Receiving reports from MT5 and broadcasting updates to the Core Service.

### Critical Endpoints:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/signal` | POST | Accept a trade signal (BUY/SELL) and queue for MT5. |
| `/close_position` | POST | Queue a closure command for a specific ticket. |
| `/report` | POST | Receiver for positions/account reports sent by MT5. |
| `/refresh_mt5` | POST | Explicitly request a data update from the terminal. |

---

## 3. Messaging Service (`messaging-service`)
**Role**: User interaction and natural language translation.
- **Port**: 8003
- **Technology**: FastAPI, LangChain, LangGraph, OpenAI.

### Key Responsibilities:
- **Webhook Handling**: Ingesting incoming messages from the Meta (WhatsApp) Cloud API.
- **Agent Reasoning**: Using the **OpenAI Agent** to determine user intent and select the correct tool.
- **Response Orchestration**: Formatting service outputs into concise, human-readable WhatsApp messages.

### Critical Endpoints:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Inbound WhatsApp messages from Meta. |
| `/health` | GET | Basic liveness check. |

---

## Shared Logic (`libs/`)

To maintain DRY (Don't Repeat Yourself) principles, common logic is extracted into internal libraries:

- **`common-logging`**: Rich-formatted console output and standardized file logging.
- **`common-config`**: Environment variable validation and retrieval.
- **`common-events`**: Pydantic models used for JSON data exchange between services.
- **`common-models`**: Shared SQLAlchemy database models (used primarily by Core).

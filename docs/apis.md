# Project APIs Documentation

This document lists all available API endpoints across the microservices, categorized by their deployment environment and service.

## [GCP] Quant Server
The central backend infrastructure for user management, messaging, and signal orchestration.

### Core Service (Port 8001)
The primary backend service handling data persistence and business logic.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service landing page (HTML) |
| GET | `/health` | Service health status |
| GET | `/users/{phone_number}` | Get user by phone number |
| POST | `/users/signup/init` | Initialize user signup session |
| GET | `/signup/session/{phone_number}` | Get current signup state |
| GET | `/users/id/{user_id}` | Get user details by ID |
| PATCH | `/signup/session/{phone_number}` | Update signup session progress |
| PATCH | `/users/{phone_number}` | Update user profile |
| POST | `/users` | Create a new user record |
| GET | `/watchlist/users/{symbol}` | Get users watching a specific symbol |
| GET | `/watchlist/{user_id}` | Get user's watchlist |
| POST | `/watchlist` | Add symbol to watchlist |
| DELETE | `/watchlist` | Remove symbol from watchlist |
| GET | `/alerts/{user_id}` | Get user's active price alerts |
| POST | `/alerts` | Create a new price alert |
| DELETE | `/alerts/{alert_id}` | Remove a price alert |
| GET | `/accounts/verify/{account_number}` | Verify MT5 account authorization |
| GET | `/accounts/{account_id}/user` | Get owner of a broker account |
| POST | `/broker_accounts` | Register a new broker account |
| GET | `/strategies` | List available trading strategies |
| POST | `/strategies/{strategy_name}/subscribe` | Subscribe user to a strategy |
| GET | `/strategies/{strategy_name}/subscribers` | List active strategy subscribers |
| POST | `/orders` | Record a new trade order |
| GET | `/positions/{account_id}` | Get active positions for an account |
| POST | `/positions/sync` | Sync multiple positions at once |
| POST | `/signals` | Hub: Receive and broadcast strategy signals |
| POST | `/position_event` | Hub: Handle lifecycle events (Open/Close) |
| POST | `/positions/open` | Notify position opening |
| POST | `/positions/close` | Notify position closing |
| GET | `/admin` | Administration Dashboard (HTML) |
| DELETE | `/admin/{type}/{id}` | Admin: Delete resource (user, alert, etc.) |

### Messaging Service (Port 8003)
Handles WhatsApp integration and outbound notifications.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health status |
| GET | `/webhook` | WhatsApp Webhook verification (GET challenge) |
| POST | `/webhook` | WhatsApp message receiver and processor |
| POST | `/send` | Internal API to send outbound messages |
| POST | `/notifications` | Dispatch system notifications to users |

---

## [Azure] MT5 Engine
Infrastructure dedicated to low-latency interaction with the MetaTrader 5 terminal.

### MT5 Service (Port 8000)
Low-level wrapper for terminal automation.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Terminal connectivity and system status |
| GET | `/api/positions` | Get current open positions from terminal |
| POST | `/api/symbols` | Update dynamic symbol tracking |
| GET | `/api/symbols` | List currently tracked symbols |
| GET | `/api/history` | Fetch historical candle data from terminal |
| POST | `/api/order` | Execute trade orders (Market/Pending) |

### Sync Service (Port 8080)
Maintains data parity between MT5 and the database; provides visualization.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard redirect |
| GET | `/dashboard` | Performance and technical analysis view (HTML) |
| GET | `/portfolio` | Portfolio performance visualization (HTML) |
| GET | `/admin` | Sync service internal management (HTML) |
| GET | `/sync_status` | Status of candle and position synchronization |
| GET | `/check_repair` | Identify data gaps in historical records |
| POST | `/verify_history` | Automated data integrity check |
| POST | `/api/backfill` | Trigger manual historical data backfill |
| POST | `/api/order` | Proxy order requests to MT5 service |
| GET | `/api/positions` | Filtered positions view for dashboard |
| POST | `/report` | Receive full position reports from MT5 |
| POST | `/signal` | Process strategy-generated technical signals |
| POST | `/position_event` | Generic handler for trade lifecycle events |
| POST | `/position_opened` | Hook for new trade notification |
| POST | `/position_closed` | Hook for closed trade notification |
| POST | `/trade_error` | Capture and notify trade execution errors |

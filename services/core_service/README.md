# Core Service

The central data authority for the trading ecosystem.

## Features
- **User Management**: Unified registration and profile tracking.
- **Watchlist & Portfolio**: Persistence for user-selected symbols and current trading positions.
- **Alert Persistence**: Stores price alert configurations for cross-service notifications.
- **Database Migrations**: Owns the Alembic migration history for the PostgreSQL schema.
- **Data Persistence**: Handles all CRUD operations for the core trading domain.

## API Endpoints
- `GET /users/{phone_number}`: Retrieve user details.
- `POST /users`: Create or update users.
- `GET /watchlist/{user_id}`: Fetch user watchlist symbols.
- `GET /watchlist/users/{symbol}`: Internal endpoint to find users watching a specific symbol.
- `POST /watchlist`: Add symbols to a user's watchlist.
- `POST /orders`: Persist new trade orders.
- `GET /positions/{account_id}`: Retrieve current position state.

## Database Schema (PostgreSQL)

### `users`
- `id` (PK): Unique user identifier.
- `phone_number` (Unique, Index): WhatsApp phone number.
- `name`: User full name.
- `has_stock_portfolio`: Boolean flag for stock trading.
- `has_fx_portfolio`: Boolean flag for Forex trading.
- `stock_capital` / `fx_capital`: Allocated capital per market.

### `watchlist`
- `id` (PK): Item identifier.
- `user_id` (FK): Links to `users.id`.
- `stock_id`: Symbol (e.g., EURUSD, AAPL).
- `market`: Market type (FX, STOCK).
- *Unique Constraint*: `user_id`, `stock_id`, `market`.

### `alerts`
- `id` (PK): Alert identifier.
- `user_id` (FK): Links to `users.id`.
- `stock_id`: Target symbol.
- `target_price`: Trigger price level.
- `condition`: `ABOVE` or `BELOW`.
- `market`: Market type.
- `created_at`: Creation timestamp.

### `broker_accounts`
- `id` (PK): Account identifier.
- `user_id` (FK): Links to `users.id`.
- `account_number`: Broker's account ID.
- `broker_name`: Broker name (e.g., MetaQuotes).
- `account_type`: Platform type (MT5, IBKR).

### `orders`
- `id` (BIGINT, PK): Unique ticket/order ID from broker.
- `broker_account_id` (FK): Links to `broker_accounts.id`.
- `symbol`: Traded instrument.
- `action`: `BUY` or `SELL`.
- `quantity`: Trade volume.
- `price`: Execution price.
- `status`: `PENDING`, `FILLED`, `CANCELLED`.

### `positions`
- `id` (BIGINT, PK): Unique position ticket from broker.
- `broker_account_id` (FK): Links to `broker_accounts.id`.
- `symbol`: Instrument.
- `quantity`: Active volume.
- `average_price`: Entry price.
- `current_price`: Last known market price.

### `signup_sessions`
- `phone_number` (PK): User identify for registration.
- `step`: Current signup wizard step.
- `completed`: Boolean registration status.
- `interests`: `FX`, `STOCKS`, or `BOTH`.

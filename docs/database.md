# Data Layer

The project employs a dual-database strategy to handle both relational state and high-frequency time-series data.

---

## 1. Relational Database (PostgreSQL)

PostgreSQL serves as the primary "Source of Truth" for user profiles, portfolio state, and administrative configurations.

### Schema Overview (via SQLAlchemy)

| Table | Description | Key Columns |
|-------|-------------|-------------|
| `users` | Core user identity and contact info. | `id`, `phone_number`, `is_active` |
| `broker_accounts` | Linkages between Users and MT5 accounts. | `account_number`, `broker_name`, `account_type` |
| `orders` | Historical and pending trade requests. | `symbol`, `action` (BUY/SELL), `status` (PENDING/EXECUTED) |
| `positions` | **Live State** of open market positions. | `ticket_id`, `quantity`, `average_price`, `active_status` |
| `watchlists` | Target symbols for specific users. | `symbol`, `market_type` (FX/STOCK) |
| `alerts` | User-defined price triggers. | `target_price`, `condition` (ABOVE/BELOW) |

### Migration Management (Alembic)
Database migrations are managed via **Alembic**. To apply the latest schema changes:
```bash
uv run alembic upgrade head
```

---

## 2. Time-Series Database (InfluxDB)

InfluxDB is used for high-frequency logging and historical performance tracking, as it is optimized for high write loads and time-based queries.

### Usage in the Stack:
- **Trade Logging**: Every sync event from the MT5 terminal is logged as a "measurement".
- **Account Metrics**: Balance, equity, and margin levels are recorded to provide historical growth charts.
- **Signal Tracking**: Incoming signals and their execution latency are tracked for performance optimization.

### Connection Configuration:
We use the `INFLUX_URL`, `INFLUX_TOKEN`, and `INFLUX_BUCKET` environment variables to authenticate the `execution-service` with the InfluxDB instance (typically running on the host or in a separate container).

from prometheus_client import Counter, Gauge, Histogram

# Heartbeat & Latency
LAST_HEARTBEAT = Gauge(
    "mt5_last_heartbeat_timestamp_seconds",
    "Unix timestamp of the last successful MT5 health check",
)
POLLING_LATENCY = Histogram(
    "mt5_polling_latency_seconds",
    "Latency of MT5 API calls",
    ["call_type"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

# Reconciliation
RECONCILIATION_MISMATCHES = Counter(
    "sync_reconciliation_mismatches_total",
    "Total number of data gaps or mismatches found",
)

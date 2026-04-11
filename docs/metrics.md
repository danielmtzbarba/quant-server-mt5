# Operational Metrics Reference

This document details the Prometheus metrics exposed by the microservices for operational observability.

## Global Metrics (Standard)
Every service exposes standard FastAPI and Python metrics via `/metrics`.
- `http_requests_total`: Total HTTP requests handled.
- `http_request_duration_seconds`: Histogram of request latencies.
- `process_cpu_seconds_total`: Total user and system CPU time spent in seconds.
- `process_resident_memory_bytes`: Resident memory size in bytes.

---

## Messaging Service
**Targets**: `messaging-service:8003`

| Metric Name | Type | Description |
| :--- | :--- | :--- |
| `messaging_webhook_received_total` | Counter | Total webhooks received (labels: `event_type`). |
| `messaging_webhook_parse_failures_total` | Counter | Total number of failed webhook parses (malformed or unrecognized). |
| `messaging_outbound_send_failures_total` | Counter | Total number of failed outbound WhatsApp messages. |

---

## MT5 Service (Execution)
**Targets**: `mt5-engine-azure:8000` (Azure via Tailscale)

| Metric Name | Type | Description |
| :--- | :--- | :--- |
| `mt5_execution_success_total` | Counter | Total number of successful order executions. |
| `mt5_execution_failed_total` | Counter | Total number of orders rejected or failed. |

---

## Sync Service
**Targets**: `sync-service:8080`

| Metric Name | Type | Description |
| :--- | :--- | :--- |
| `mt5_last_heartbeat_timestamp_seconds` | Gauge | Unix timestamp of the last successful MT5 health probe. |
| `mt5_polling_latency_seconds` | Histogram | Latency of MT5 API calls (labels: `call_type`). |
| `sync_reconciliation_mismatches_total` | Counter | Total number of data gaps or mismatches found during health checks. |

---

## Access & Security
- **Internal Only**: The `/metrics` endpoints are only accessible within the **Tailscale network**.
- **GCP access**: Prometheus scrapes services via the internal Docker bridge network.
- **Cross-Cloud access**: Prometheus scrapes the Azure VM via the dedicated Tailscale hostname `mt5-engine-azure`.

> [!TIP]
> Use the **Prometheus UI** at `http://<GCP-VM-IP>:9090` to explore these metrics and build dashboards.

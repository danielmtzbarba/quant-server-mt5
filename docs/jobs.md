# Scheduled Jobs & Background Workers

This document details all persistent background tasks and scheduled loops within the Quant Server architecture.

## Architecture Overview

Background tasks are primarily concentrated in the **Sync Service**. The other services (`core`, `mt5`, `messaging`) are **Reactive**, meaning they only execute logic in response to incoming HTTP requests or signals.

---

## Sync Service (`sync-service`)

The Sync Service manages three primary background workers started during the service lifecycle.

### 1. Position Monitor
**File**: `services/sync_service/app/core/workers/monitoring.py`

Tracks real-time position state in the MT5 terminal and notifies the Core Service of lifecycle events (OPENED/CLOSED).

| State | Interval | Action |
| :--- | :--- | :--- |
| **Normal** | 5 seconds | Polls MT5 for active positions and completes diff analysis. |
| **MT5 Unavailable** | 2 seconds | Exponentially aggressive retry to restore connection. |
| **Generic Error** | 5 seconds | Cooldown before retrying logic. |

---

### 2. Candle Publisher
**File**: `services/sync_service/app/core/workers/publishing.py`

Polls market data for all tracked symbols, writes historical candles to InfluxDB, and triggers strategy analysis in the backend.

| State | Interval | Action |
| :--- | :--- | :--- |
| **Normal** | 1 second | Iterates through all tracked symbols and polls for new M1 candles. |
| **MT5 Unavailable** | 2 seconds | Wait for terminal connectivity. |
| **Generic Error** | 5 seconds | Cooldown before retrying logic. |

---

### 3. Health Monitor
**File**: `services/sync_service/app/core/workers/health.py`

Performs deep-check validation of symbols and terminal health to ensure data integrity. **Now features automated self-healing.**

| State | Interval | Action |
| :--- | :--- | :--- |
| **Normal** | 10 minutes | Runs `sync_service.run_health_check` across all symbols. |
| **Gap Detected** | Immediate | Triggers a **3-day backfill** from MT5 for the affected symbol. |
| **Error** | 60 seconds | Cooldown after a failed health scan. |

---

## Service Summary

| Service | Scheduled Jobs | Mechanism |
| :--- | :---: | :--- |
| **Core Service** | None | Reactive REST API |
| **MT5 Service** | None | Reactive Wrapper API |
| **Messaging Service** | None | Reactive Bot API |
| **Sync Service** | 3 | Asyncio Background Loops |

---

## Manual / External Jobs

### MT5-DB Synchronization
**File**: `scripts/sync_mt5_records.py`

- **Frequency**: On-demand / Manual.
- **Purpose**: Force a hard synchronization between the MT5 terminal state and the PostgreSQL database.
- **Trigger**: Usually executed manually by administrators or via a CI/CD cleanup step.

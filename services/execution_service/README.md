# Execution Service

The bridge between the trading logic and the broker (MetaTrader 5).

## Features
- **MT5 Polling**: Provides a lightweight JSON API for the MT5 EA to poll for pending trade commands.
- **Trade Execution**: Manages a singleton queue of `OPEN`, `CLOSE`, and `REPORT` commands.
- **Market Data Logic**: Integrated with `trade_db` for querying historical OHLCV data.
- **Signal Processing**: Receives trading signals from external sources and broadcasts notifications to interested users (via Core Service).
- **Position Reporting**: Synchronizes real-time position updates from the MT5 terminal.

## API Endpoints
- `POST /signal`: Receive and process trading signals.
- `GET /poll`: Dedicated endpoint for MT5 EA command fetching.
- `POST /report`: Receive position sync reports from MT5.
- `POST /position_event`: Real-time notification of position open/close events.

# Messaging Service

The user-facing entry point, handling all WhatsApp interactions and AI-driven command processing.

## Features
- **WhatsApp Webhook**: Receives and validates incoming messages from the WhatsApp Graph API.
- **AI Agent**: Utilizes LangGraph and OpenAI to translate natural language into technical trading actions.
- **Command Translation**: Maps user-facing commands (e.g., "!LOGIN", "COMANDOS") to service-level actions.
- **Outbound Messaging**: Manages consistent formatting and delivery of notifications to users.
- **Registration Flow**: Handles the multi-step user onboarding process.

## API Endpoints
- `GET /webhook`: Verification endpoint for WhatsApp API setup.
- `POST /webhook`: Inbound message listener.

## AI Agent Tools

The messaging agent uses LangGraph to orchestrate complex financial tasks. Below is a list of tools available to the agent:

### Watchlist Management
- **`create_watchlist(user_phone, ticker, market)`**: Adds a symbol to the user's focus list.
    - **Effect**: Calls `POST /watchlist` on Core Service. Creates a record in the `watchlist_items` table.
- **`delete_watchlist(user_phone, ticker)`**: Removes a symbol from the user's focus list.
    - **Effect**: Calls `DELETE /watchlist` on Core Service. Deletes the record from the `watchlist_items` table.
- **`get_watchlist(user_phone)`**: Retrieves the current symbols being monitored.
    - **Effect**: Calls `GET /watchlist/{user_id}` on Core Service.

### Price Alerts
- **`create_alert(user_phone, symbol, price, condition)`**: Sets a price threshold notification.
    - **Effect**: Calls `POST /alerts` on Core Service. Creates a record in the `alerts` table.
- **`delete_alert(user_phone, alert_id)`**: Cancels an existing alert by ID.
    - **Effect**: Calls `DELETE /alerts/{id}` on Core Service. Deletes the record from the `alerts` table.
- **`get_alerts(user_phone)`**: Lists all active price notifications for the user.
    - **Effect**: Calls `GET /alerts/{user_id}` on Core Service.

### Trading & MT5 Control
- **`open_position(user_phone, symbol, action, volume)`**: Executes a market BUY or SELL order.
    - **Effect**: Calls `POST /signal` on Execution Service. Queues a trade command for MT5.
- **`close_position(user_phone, ticket)`**: Terminates a specific trade.
    - **Effect**: Calls `POST /close_position` on Execution Service. Queues a `CLOSE` command for MT5.
- **`get_positions(user_phone)`**: Lists all active trades recorded in the system.
    - **Effect**: Triggers a `REFRESH` via Execution Service and queries the `positions` table in Core Service.
- **`refresh_mt5_data(user_phone)`**: Manually forces a synchronization with the MetaTrader 5 terminal.
    - **Effect**: Calls `POST /refresh_mt5` on Execution Service to queue a `REFRESH` command.
- **`verify_mt5_commands(user_phone)`**: Shows all pending actions currently in the execution queue.
    - **Effect**: Calls `GET /commands` on Execution Service.

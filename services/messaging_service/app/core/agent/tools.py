import httpx
import logging
from langchain_core.tools import tool
from common_config import get_env_var

logger = logging.getLogger("messaging-service")
CORE_SERVICE_URL = get_env_var("CORE_SERVICE_URL", "http://core-service:8001")
EXECUTION_SERVICE_URL = get_env_var(
    "EXECUTION_SERVICE_URL", "http://execution-service:8002"
)


@tool
def get_price(ticker: str) -> str:
    """Gets the current price for a stock ticker."""
    return "Price fetching is currently disabled. Please wait for signals."


@tool
async def create_watchlist(user_phone: str, ticker: str, market: str) -> str:
    """
    Adds a ticker to the user's watchlist via Core Service.
    market must be 'FX' or 'STOCK'.
    """
    async with httpx.AsyncClient() as client:
        try:
            # 1. Get user by phone
            resp = await client.get(f"{CORE_SERVICE_URL}/users/{user_phone}")
            if resp.status_code != 200:
                return "User not found. Please register first."
            user = resp.json()

            # 2. Add to watchlist
            resp = await client.post(
                f"{CORE_SERVICE_URL}/watchlist",
                params={
                    "user_id": user["id"],
                    "symbol": ticker.upper(),
                    "market": market.upper(),
                },
            )
            if resp.status_code == 200:
                return f"Successfully added {ticker} to your {market} watchlist."
            return f"Failed to add {ticker} to watchlist."
        except Exception as e:
            logger.error(f"Error in create_watchlist tool: {e}")
            return "Internal error communicating with core service."


@tool
async def get_watchlist(user_phone: str) -> str:
    """Gets the user's current watchlist from Core Service."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{CORE_SERVICE_URL}/users/{user_phone}")
            if resp.status_code != 200:
                return "User not found."
            user = resp.json()

            resp = await client.get(f"{CORE_SERVICE_URL}/watchlist/{user['id']}")
            items = resp.json()
            if not items:
                return "Your watchlist is empty."

            res = "Your Watchlist:\n"
            for sym in items:
                res += f"- {sym}\n"
            return res
        except Exception as e:
            return f"Error fetching watchlist: {e}"


@tool
async def delete_watchlist(user_phone: str, ticker: str) -> str:
    """Removes a ticker from the user's watchlist."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{CORE_SERVICE_URL}/users/{user_phone}")
            if resp.status_code != 200:
                return "User not found."
            user = resp.json()

            resp = await client.delete(
                f"{CORE_SERVICE_URL}/watchlist",
                params={"user_id": user["id"], "symbol": ticker.upper()},
            )
            if resp.status_code == 200:
                return f"Successfully removed {ticker} from your watchlist."
            return f"Failed to remove {ticker}."
        except Exception as e:
            return f"Error: {e}"


@tool
async def create_alert(
    user_phone: str, symbol: str, price: float, condition: str
) -> str:
    """Creates a price alert. condition: 'ABOVE' or 'BELOW'."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{CORE_SERVICE_URL}/users/{user_phone}")
            if resp.status_code != 200:
                return "User not found."
            user = resp.json()

            resp = await client.post(
                f"{CORE_SERVICE_URL}/alerts",
                params={
                    "user_id": user["id"],
                    "symbol": symbol.upper(),
                    "price": price,
                    "condition": condition.upper(),
                },
            )
            if resp.status_code == 200:
                return f"Alert set for {symbol} {condition} {price}."
            return "Failed to set alert."
        except Exception as e:
            return f"Error: {e}"


@tool
async def delete_alert(user_phone: str, alert_id: int) -> str:
    """Deletes an alert by ID."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{CORE_SERVICE_URL}/users/{user_phone}")
            if resp.status_code != 200:
                return "User not found."
            user = resp.json()

            resp = await client.delete(
                f"{CORE_SERVICE_URL}/alerts/{alert_id}", params={"user_id": user["id"]}
            )
            if resp.status_code == 200:
                return f"Alert {alert_id} deleted."
            return "Failed to delete alert."
        except Exception as e:
            return f"Error: {e}"


@tool
async def get_alerts(user_phone: str) -> str:
    """Lists your active price alerts."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{CORE_SERVICE_URL}/users/{user_phone}")
            if resp.status_code != 200:
                return "User not found."
            user = resp.json()

            resp = await client.get(f"{CORE_SERVICE_URL}/alerts/{user['id']}")
            alerts = resp.json()
            if not alerts:
                return "No active alerts."

            res = "Active Alerts:\n"
            for a in alerts:
                res += f"ID: {a['id']} | {a['symbol']} {a['condition']} {a['target_price']}\n"
            return res
        except Exception as e:
            return f"Error: {e}"


@tool
async def open_position(
    user_phone: str, symbol: str, action: str, volume: float
) -> str:
    """Opens a new trading position. action: 'BUY' or 'SELL'."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{EXECUTION_SERVICE_URL}/signal",
                json={
                    "symbol": symbol.upper(),
                    "action": action.upper(),
                    "price": 0.0,
                    "volume": volume,
                },
            )
            if resp.status_code == 200:
                return "Trade command sent to MT5. Acknowledgment will be sent once executed."
            elif resp.status_code == 429:
                return "Operation GATED: Maximum position limit reached. Please close a position before opening a new one."
            return f"Failed to queue trade: {resp.text}"
        except Exception as e:
            return f"Error: {e}"


@tool
async def close_position(user_phone: str, ticket: int) -> str:
    """Closes an open position by ticket ID."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{EXECUTION_SERVICE_URL}/close_position", params={"ticket": ticket}
            )
            if resp.status_code == 200:
                return f"Close command for ticket {ticket} queued."
            return "Failed to queue close command."
        except Exception as e:
            return f"Error: {e}"


@tool
async def get_positions(user_phone: str) -> str:
    """Retrieves current open positions from the database."""
    async with httpx.AsyncClient() as client:
        try:
            # First trigger a refresh from MT5 (via REFRESH command)
            await client.post(f"{EXECUTION_SERVICE_URL}/refresh_mt5")

            resp = await client.get(f"{CORE_SERVICE_URL}/users/{user_phone}")
            if resp.status_code != 200:
                return "User not found."

            # In a real setup, account_id would be matched to the user.
            # For now, we'll fetch positions for a default account or search by user.
            # Fetch positions for account 1 (aligned with Execution Service hardcode)
            resp = await client.get(f"{CORE_SERVICE_URL}/positions/1")
            positions = resp.json()
            if not positions:
                return "No open positions found. (Try again in 5s if you just changed something)"

            res = "Open Positions:\n"
            for p in positions:
                side = (
                    "BUY"
                    if p.get("type") == 0
                    else "SELL"
                    if p.get("type") == 1
                    else "TRADE"
                )
                res += f"- Ticket {p['id']}: {side} {p['quantity']} {p['symbol']} @ {p['average_price']}\n"
            return res
        except Exception as e:
            return f"Error: {e}"


@tool
async def refresh_mt5_data(user_phone: str) -> str:
    """Forces MT5 to send a fresh report of all positions and account state."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{EXECUTION_SERVICE_URL}/refresh_mt5")
            if resp.status_code == 200:
                return "MT5 refresh requested. Data will be updated in a few seconds."
            return "Failed to request refresh."
        except Exception as e:
            return f"Error: {e}"


@tool
async def verify_mt5_commands(user_phone: str) -> str:
    """Check what commands are currently waiting for MT5 to pick them up."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{EXECUTION_SERVICE_URL}/commands")
            data = resp.json()
            pending = data.get("pending", [])
            if not pending:
                return "No pending commands in queue."

            res = "Pending MT5 Commands:\n"
            for cmd in pending:
                res += f"- {cmd['action']} | {cmd}\n"
            return res
        except Exception as e:
            return f"Error: {e}"

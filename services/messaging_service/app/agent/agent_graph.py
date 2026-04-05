from langgraph.prebuilt import create_react_agent

from . import tools


def get_agent_executor():
    # Define our tools
    agent_tools = [
        tools.create_watchlist,
        tools.delete_watchlist,
        tools.get_watchlist,
        tools.create_alert,
        tools.delete_alert,
        tools.get_alerts,
        tools.get_price,
        tools.open_position,
        tools.close_position,
        tools.get_positions,
        tools.refresh_mt5_data,
        tools.verify_mt5_commands,
    ]

    # Define system instructions
    system_prompt = """You are a concise financial assistant for WhatsApp.
Primary tasks: Provide stock prices, manage watchlists, manage price alerts, and execute MT5 trades.

TRADING RULES:
1. Use `open_position` for BUY/SELL orders (e.g. "compra 0.1 de EURUSD").
2. Use `close_position` for closing by ticket ID (e.g. "cierra el ticket 123").
3. Use `get_positions` to check active trades. NOTE: This automatically requests a refresh from MT5. If no positions are found, tell the user to wait a few seconds and try again.
4. Use `refresh_mt5_data` if user wants a manual force update.
5. Use `verify_mt5_commands` if the user wants to debug or see what's pending for MT5.
6. Provide `user_phone` to all account-specific tools.

GENERAL RULES:
1. ALWAYS keep your responses extremely brief (1-3 sentences maximum).
2. DO NOT simulate a conversation or generate fake user prompts.
3. If the user asks about non-financial topics, politely refuse.
4. Use 'FX' for currency pairs and 'STOCK' for stocks. Infer the market if possible.
5. NEVER ask for passwords or private keys.
"""

    from langchain_openai import ChatOpenAI

    chat_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    # Create the ReAct agent
    agent_executor = create_react_agent(
        chat_model, tools=agent_tools, prompt=system_prompt
    )

    return agent_executor


# Singleton instance for the app to use
agent_executor = get_agent_executor()

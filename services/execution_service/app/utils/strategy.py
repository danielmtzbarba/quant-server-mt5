import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class PriceActionStrategy:
    """
    Evaluates market data against predefined mathematical conditions 
    to generate actionable Buy (1) and Sell (-1) signals, along with risk levels.
    """

    @staticmethod
    def bounce_rejection(
        df: pd.DataFrame, 
        sup_col: str = 'Sup_100', 
        res_col: str = 'Res_100', 
        atr_col: str = 'ATR_14',
        atr_multiplier: float = 0.3
    ) -> pd.DataFrame:
        """
        Generates signals when price tests a support/resistance zone and rejects it.
        """
        df = df.copy()
        df['Signal'] = 0
        
        required_cols = [sup_col, res_col, atr_col, 'Open', 'High', 'Low', 'Close']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing required columns for strategy. Need: {required_cols}")
            return df

        zone_depth = df[atr_col] * atr_multiplier

        # BUY LOGIC (Long)
        tested_support = df['Low'] <= (df[sup_col] + zone_depth)
        bullish_close = df['Close'] > df['Open']
        closed_safe = df['Close'] > df[sup_col]
        buy_condition = tested_support & bullish_close & closed_safe

        # SELL LOGIC (Short)
        tested_resistance = df['High'] >= (df[res_col] - zone_depth)
        bearish_close = df['Close'] < df['Open']
        closed_safe_short = df['Close'] < df[res_col]
        sell_condition = tested_resistance & bearish_close & closed_safe_short

        df.loc[buy_condition, 'Signal'] = 1
        df.loc[sell_condition, 'Signal'] = -1

        return df

    @staticmethod
    def calculate_levels(
        signal: int, 
        entry_price: float, 
        high: float, 
        low: float, 
        atr: float, 
        atr_buffer: float = 0.1, 
        rr_ratio: float = 2.0
    ) -> tuple:
        """
        Computes dynamic Stop Loss and Take Profit levels based on market volatility.
        
        Args:
            signal: 1 for Buy, -1 for Sell.
            entry_price: The expected execution price.
            high/low: The extremes of the signal candle to hide the Stop Loss behind.
            atr: The current Average True Range.
            atr_buffer: Fractional multiplier to push SL slightly beyond the wick.
            rr_ratio: The Risk-to-Reward ratio (e.g., 2.0 means target 2x the risk).
            
        Returns:
            Tuple of (stop_loss, take_profit)
        """
        if signal == 0:
            return None, None

        if signal == 1:  # BUY
            # SL placed just below the rejection wick
            sl = low - (atr * atr_buffer)
            # Risk is the distance from entry down to SL
            risk = entry_price - sl
            # TP is projected upward
            tp = entry_price + (risk * rr_ratio)
            
        elif signal == -1: # SELL
            # SL placed just above the rejection wick
            sl = high + (atr * atr_buffer)
            # Risk is the distance from SL down to entry
            risk = sl - entry_price
            # TP is projected downward
            tp = entry_price - (risk * rr_ratio)
            
        return sl, tp

    @classmethod
    def get_current_signal(
        cls, 
        df_window: pd.DataFrame, 
        sup_col: str = 'Sup_100', 
        res_col: str = 'Res_100', 
        atr_col: str = 'ATR_14',
        atr_multiplier: float = 0.3,
        rr_ratio: float = 2.0
    ) -> dict:
        """
        Evaluates the live edge (latest candle) of a provided data window.
        Designed to be called continuously by a live trading loop or Simulator.

        Returns:
            dict: Structured trade instructions including action, SL, and TP.
        """
        if df_window.empty:
            return {'action': 'HOLD', 'signal_code': 0}

        # Apply the vectorized logic to the window
        df_signals = cls.bounce_rejection(
            df_window, sup_col, res_col, atr_col, atr_multiplier
        )
        
        # Isolate the current (latest) candle
        latest = df_signals.iloc[-1]
        signal_val = latest['Signal']
        
        # If no signal, return immediately
        if signal_val == 0:
            return {
                'action': 'HOLD',
                'signal_code': 0,
                'timestamp': latest.name
            }

        # Determine the action string
        action = "BUY" if signal_val == 1 else "SELL"
        
        # The expected entry is the Close of the signal candle 
        # (which fundamentally equals the Open of the immediate next candle)
        entry_price = latest['Close']
        
        # Calculate risk management levels
        sl, tp = cls.calculate_levels(
            signal=signal_val,
            entry_price=entry_price,
            high=latest['High'],
            low=latest['Low'],
            atr=latest[atr_col],
            atr_buffer=0.1,  # 10% of ATR buffer behind the wick
            rr_ratio=rr_ratio
        )
        
        return {
            'action': action,
            'signal_code': signal_val,
            'entry_price': entry_price,
            'stop_loss': sl,
            'take_profit': tp,
            'risk_reward_ratio': rr_ratio,
            'atr_at_entry': latest[atr_col],
            'timestamp': latest.name
        }

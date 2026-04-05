import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from zoneinfo import ZoneInfo


class MarketVisualizer:
    """
    A professional charting module using Plotly to render interactive
    candlestick and line charts with technical indicator overlays.
    Optimized for professional 'light mode' visibility.
    """

    @staticmethod
    def get_standard_highlights(df: pd.DataFrame, gaps: list = None) -> list:
        """
        Generates a unified list of visual decorations:
        - Weekends (Yellow)
        - London/NY Overlaps (Green)
        - Data Gaps (Red - Optional)
        """
        highlights = []
        if df.empty:
            return highlights

        # 1. Weekends (Yellow) - Dynamically detect based on Friday's last candle
        ny_tz = ZoneInfo("US/Eastern")
        # Identify Fridays in NY time to match market close conventions
        df_ny_index = df.index.tz_convert(ny_tz)
        fridays = df_ny_index[df_ny_index.weekday == 4].normalize().unique()

        for fri in fridays:
            # Find the actual last candle of this Friday in the data
            day_mask = df_ny_index.normalize() == fri
            last_fri_ts_ny = df_ny_index[day_mask].max()

            # Find the first candle of the following Sunday
            sun_mask = df_ny_index.normalize() == (fri + pd.Timedelta(days=2))
            if sun_mask.any():
                first_sun_ts_ny = df_ny_index[sun_mask].min()
            else:
                # Fallback: Friday's last candle to 2 days later 17:00 NY
                first_sun_ts_ny = (fri + pd.Timedelta(days=2)).replace(
                    hour=17, minute=0, second=0
                )

            # Convert back to the original index timezone
            h_start = last_fri_ts_ny.tz_convert(df.index.tz)
            h_end = first_sun_ts_ny.tz_convert(df.index.tz)

            # CLIP TO CURRENT DATA: Don't highlight past the latest candle in the dataset
            if h_start >= df.index.max():
                continue
            if h_end > df.index.max():
                h_end = df.index.max()

            highlights.append(
                {
                    "start": h_start,
                    "end": h_end,
                    "color": "#FBC02D",
                    "label": "WEEKEND",
                    "opacity": 0.15,
                }
            )

        # 2. Golden Overlaps (Green) - London/NY Overlap (Score 10)
        from utils.forex import score_trading_hour

        current_overlap_start = None

        for ts in df.index:
            score = score_trading_hour(ts)
            if score == 10:
                if current_overlap_start is None:
                    current_overlap_start = ts
            else:
                if current_overlap_start is not None:
                    highlights.append(
                        {
                            "start": current_overlap_start,
                            "end": ts,
                            "color": "#26A69A",
                            "label": "",
                            "opacity": 0.1,
                        }
                    )
                    current_overlap_start = None

        if current_overlap_start:
            highlights.append(
                {
                    "start": current_overlap_start,
                    "end": df.index[-1],
                    "color": "#26A69A",
                    "label": "",
                    "opacity": 0.1,
                }
            )

        # 3. Gaps (Red)
        if gaps:
            for g in gaps:
                highlights.append(
                    {
                        "start": g["start"],
                        "end": g["end"],
                        "color": "#EF5350",
                        "label": "GAP",
                        "opacity": 0.3,
                    }
                )

        return highlights

    @staticmethod
    def plot_chart(
        df: pd.DataFrame,
        symbol: str,
        chart_type: str = "candle",
        overlays: list = None,
        show_volume: bool = False,
        highlights: list = None,
        include_plotlyjs: bool = True,
    ):
        """Generates and displays the interactive financial chart."""
        fig = MarketVisualizer.get_figure(
            df, symbol, chart_type, overlays, show_volume, highlights
        )
        if fig:
            fig.show(include_plotlyjs=include_plotlyjs)

    @staticmethod
    def get_figure(
        df: pd.DataFrame,
        symbol: str,
        chart_type: str = "candle",
        overlays: list = None,
        show_volume: bool = False,
        highlights: list = None,
    ):
        """Generates the Plotly figure object (Graph Object)."""
        if df.empty:
            print("[-] DataFrame is empty. Nothing to plot.")
            return None

        # --- Colors Configuration (Professional Light Mode) ---
        # 1. Main Colors
        PRICE_LINE_COLOR = "#333333"  # Dark Gray for primary close line
        GRID_COLOR = "#E0E0E0"  # Light Gray for grid (subtle)
        TEXT_COLOR = "#1A1A1A"  # Almost Black for axes and title

        # 2. Bull/Bear Candlestick colors (Slightly softer tones on white)
        BULL_COLOR = "#26A69A"  # Clean teal/green
        BEAR_COLOR = "#EF5350"  # Clean red

        # 3. Indicator Colors (Professional muted tones for white background)
        # Blue, Dark Orange, Dark Purple, Dark Gray
        INDICATOR_COLORS = ["#0000FF", "#FF8C00", "#6A0DAD", "#808080"]

        # --- Subplot Setup ---
        rows = 2 if show_volume else 1
        row_heights = [0.8, 0.2] if show_volume else [1.0]

        fig = make_subplots(
            rows=rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
        )

        # --- 1. Main Price Chart ---
        if chart_type == "candle":
            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df["Open"],
                    high=df["High"],
                    low=df["Low"],
                    close=df["Close"],
                    increasing_line_color=BULL_COLOR,
                    increasing_fillcolor=BULL_COLOR,
                    decreasing_line_color=BEAR_COLOR,
                    decreasing_fillcolor=BEAR_COLOR,
                    line=dict(width=1),  # Sharp wicks
                    name="Price Action",
                ),
                row=1,
                col=1,
            )
        elif chart_type == "line":
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["Close"],
                    mode="lines",
                    name="Close Price",
                    line=dict(color=PRICE_LINE_COLOR, width=2),
                ),
                row=1,
                col=1,
            )
        else:
            raise ValueError("chart_type must be 'candle' or 'line'")

        # --- 2. Indicator Overlays ---
        if overlays:
            for i, col in enumerate(overlays):
                if col in df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df[col],
                            mode="lines",
                            name=col,
                            line=dict(
                                width=1.5,
                                color=INDICATOR_COLORS[i % len(INDICATOR_COLORS)],
                            ),
                        ),
                        row=1,
                        col=1,
                    )

        # --- 2.5 Trade Signals Overlay ---
        if "Signal" in df.columns:
            # Filter rows where a Buy (1) or Sell (-1) occurred
            buys = df[df["Signal"] == 1]
            sells = df[df["Signal"] == -1]

            if not buys.empty:
                fig.add_trace(
                    go.Scatter(
                        x=buys.index,
                        y=buys["Low"]
                        - (buys["Low"] * 0.0005),  # Slightly below the wick
                        mode="markers",
                        name="Buy Signal",
                        marker=dict(
                            symbol="triangle-up",
                            size=14,
                            color="#00C853",
                            line=dict(width=1, color="black"),
                        ),
                    ),
                    row=1,
                    col=1,
                )

            if not sells.empty:
                fig.add_trace(
                    go.Scatter(
                        x=sells.index,
                        y=sells["High"]
                        + (sells["High"] * 0.0005),  # Slightly above the wick
                        mode="markers",
                        name="Sell Signal",
                        marker=dict(
                            symbol="triangle-down",
                            size=14,
                            color="#D50000",
                            line=dict(width=1, color="black"),
                        ),
                    ),
                    row=1,
                    col=1,
                )

        # --- 3. Volume Subplot ---
        if show_volume and "Volume" in df.columns:
            # Match volume bars to candlestick colors
            marker_colors = [
                BULL_COLOR if close >= open else BEAR_COLOR
                for close, open in zip(df["Close"], df["Open"])
            ]

            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=df["Volume"],
                    name="Volume",
                    marker_color=marker_colors,
                    marker=dict(line=dict(width=0)),  # Flat bars, no outline
                ),
                row=2,
                col=1,
            )

        # --- 4. Professional Formatting (White Background) ---

        # Use 'plotly' template as base (white bg)
        # Force high contrast black/dark gray lines
        fig.update_layout(
            title=f"{symbol} Market Analysis | Interactive View",
            title_font=dict(color=TEXT_COLOR, size=18),
            xaxis=dict(
                range=[df.index.min(), df.index.max()], rangeslider_visible=False
            ),
            xaxis_title_font=dict(color=TEXT_COLOR),
            yaxis_title_font=dict(color=TEXT_COLOR),
            template="plotly",  # Change to standard plotly template for white bg
            hovermode="x unified",
            height=800,
            paper_bgcolor="white",  # Pure white outer padding
            plot_bgcolor="white",  # Pure white chart area
        )

        # Universal formatting for all X and Y axes
        axis_formatting = dict(
            # Grid lines
            showgrid=True,
            gridcolor=GRID_COLOR,  # Light subtle gray
            # Axis lines (The 'L' frame)
            showline=True,
            linecolor=TEXT_COLOR,  # Black line
            linewidth=1,
            # Ticks and Text
            ticks="outside",
            tickcolor=TEXT_COLOR,  # Black ticks
            tickfont=dict(color=TEXT_COLOR, size=11),  # Black text
        )

        # --- 5. Custom Highlights (Gaps/Weekends) ---
        if highlights:
            for h in highlights:
                fig.add_vrect(
                    x0=h["start"],
                    x1=h["end"],
                    fillcolor=h.get("color", "red"),
                    opacity=h.get("opacity", 0.2),
                    layer="below",
                    line_width=0,
                    annotation_text=h.get("label", ""),
                    annotation_position="top left",
                    annotation_font=dict(size=10, color=h.get("color", "red")),
                )

        fig.update_xaxes(
            **axis_formatting,
            # rangebreaks=[dict(bounds=["sat", "mon"])], # Disabled to show weekend highlights
            rangeslider_visible=False,  # Turns off the bulky bottom slider
        )

        fig.update_yaxes(**axis_formatting)
        return fig

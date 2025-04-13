import yfinance as yf
import pandas as pd
import pandas_ta as ta
import streamlit as st
import time

st.set_page_config(page_title="Multi-Timeframe Trade Assistant", layout="wide")

st.title("📊 Trade Signal Dashboard")

# User-configurable ticker list
tickers = st.multiselect("Select tickers to analyze:", ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN"], default=["AAPL", "TSLA"])

# Define timeframes
frames = {
    "1m": {"interval": "1m", "period": "1d", "weight": 0.35},
    "5m": {"interval": "5m", "period": "5d", "weight": 0.30},
    "10m": {"interval": "5m", "period": "5d", "weight": 0.20},
    "1d": {"interval": "1d", "period": "90d", "weight": 0.15},
}

emoji_map = {2: "✅ STRONG BUY", 1: "🔼 BUY", 0: "⚖️ NEUTRAL", -1: "🔽 SELL", -2: "❌ STRONG SELL", None: "⚠️ No Data"}

for ticker in tickers:
    st.subheader(f"📈 {ticker}")
    col1, col2 = st.columns([2, 1])
    
    signals = {}
    conf_score = 0
    valid_weights = 0
    bullish_frames = 0

    with st.spinner(f"Loading data for {ticker}..."):
        for tf, tf_data in frames.items():
            df = yf.download(ticker, interval=tf_data["interval"], period=tf_data["period"], progress=False)

            if df.empty:
                signals[tf] = None
                continue

            flat_cols = []
            for col in df.columns:
                if isinstance(col, tuple):
                    flat_col = "_".join([str(c) for c in col if c])
                else:
                    flat_col = str(col)
                flat_cols.append(flat_col)
            df.columns = [col.split("_")[0].capitalize() for col in flat_cols]

            if tf == "10m":
                df = df.resample("10min").agg({
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum"
                }).dropna()

            df["RSI"] = ta.rsi(df["Close"], length=14)
            macd = ta.macd(df["Close"])
            if macd is not None and "MACD_12_26_9" in macd.columns:
                df["MACD"] = macd["MACD_12_26_9"]
                df["Signal"] = macd["MACDs_12_26_9"]

            df.dropna(inplace=True)
            if df.empty:
                signals[tf] = None
                continue

            last = df.iloc[-1]
            score = 0
            if last["RSI"] < 30:
                score += 1
            elif last["RSI"] > 70:
                score -= 1

            if last["MACD"] > last["Signal"]:
                score += 1
            elif last["MACD"] < last["Signal"]:
                score -= 1

            signals[tf] = score
            weight = tf_data.get("weight", 0.25)
            conf_score += score * weight
            valid_weights += abs(weight)
            if score > 0:
                bullish_frames += 1

    with col1:
        st.markdown("### Timeframe Signals")
        for tf, s in signals.items():
            label = emoji_map.get(s, "⚠️")
            st.write(f"**{tf}**: {label} (score: {s})")

    with col2:
        norm_conf = (conf_score / (2 * valid_weights)) * 100 if valid_weights > 0 else 0
        st.markdown("### Confidence Meter")
        st.progress(min(max((norm_conf + 100) // 2, 0), 100), text=f"{norm_conf:.1f}/100")

        hold_time = bullish_frames * 5
        if bullish_frames == 0:
            time_suggestion = "Avoid or scalp only"
        else:
            time_suggestion = f"Hold ~{hold_time} min ({bullish_frames} bars)"

        st.markdown("### ⏱️ Time-in-Trade Suggestion")
        st.write(time_suggestion)

    st.divider()
    time.sleep(0.3)


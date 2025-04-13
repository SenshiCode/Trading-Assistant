import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import plotly.graph_objs as go
import requests
from datetime import datetime
import time
from textblob import TextBlob

st.set_page_config(page_title="🧠 All-in-One Trade Assistant", layout="wide")
st.title("📊 Top Gappers + Trade Signal Dashboard")

# ---------- TOP GAPPERS SCANNER ----------
@st.cache_data(ttl=60)
def load_gappers():
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds=day_gainers&count=100"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return pd.DataFrame()
    try:
        quotes = response.json()["finance"]["result"][0]["quotes"]
        rows = []
        for item in quotes:
            try:
                symbol = item["symbol"]
                name = item.get("shortName", "")
                price = float(item["regularMarketPrice"])
                change = float(item["regularMarketChangePercent"])
                volume = int(item.get("regularMarketVolume", 0))

                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="10d")
                avg_volume = hist["Volume"].mean() if not hist.empty else 0
                rvol = round(volume / avg_volume, 2) if avg_volume > 0 else 0

                float_val = "-"
                short_float = "-"
                try:
                    finviz_url = f"https://finviz.com/quote.ashx?t={symbol}"
                    finviz_res = requests.get(finviz_url, headers=headers)
                    tables = pd.read_html(finviz_res.text)
                    summary = pd.concat(tables)
                    summary.columns = ["Metric", "Value"]
                    float_row = summary[summary["Metric"] == "Shs Float"]
                    short_row = summary[summary["Metric"] == "Short Float"]
                    if not float_row.empty:
                        float_val = float_row.iloc[0]["Value"]
                    if not short_row.empty:
                        short_float = short_row.iloc[0]["Value"]
                except:
                    pass

                if price < 50:
                    rows.append({
                        "Symbol": symbol,
                        "Name": name,
                        "Price": price,
                        "Gap %": round(change, 2),
                        "Volume": f"{volume/1e6:.1f}M" if volume >= 1e6 else f"{volume/1e3:.1f}K" if volume >= 1e3 else str(volume),
                        "RVOL": rvol,
                        "Float": float_val if isinstance(float_val, str) else f"{float_val}",
                        "Short %": short_float if isinstance(short_float, str) else f"{short_float}"
                    })
            except:
                continue
        df = pd.DataFrame(rows)
        return df.sort_values(by="Gap %", ascending=False)
    except Exception as e:
        st.error(f"Gappers error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_news(symbol):
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={symbol}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        results = response.json().get("news", [])
        return results[:5]
    except:
        return []

def score_sentiment(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.15:
        return "🟢 Bullish"
    elif polarity < -0.15:
        return "🔴 Bearish"
    else:
        return "⚪ Neutral"

st.markdown("### 🚀 Top Gappers (Under $50)")
with st.spinner("Loading gappers..."):
    gap_data = load_gappers()

if not gap_data.empty:
    st.dataframe(gap_data.reset_index(drop=True), use_container_width=True)
    selected = st.multiselect("Select tickers to analyze signals:", gap_data["Symbol"].tolist(), default=gap_data["Symbol"].tolist()[:3])
else:
    st.warning("⚠️ No gappers data available.")
    selected = []

st.divider()

# ---------- SIGNAL ENGINE ----------
frames = {
    "1m": {"interval": "1m", "period": "1d", "weight": 0.35},
    "5m": {"interval": "5m", "period": "5d", "weight": 0.30},
    "10m": {"interval": "5m", "period": "5d", "weight": 0.20},
    "1d": {"interval": "1d", "period": "90d", "weight": 0.15},
}

emoji_map = {2: "✅ STRONG BUY", 1: "🔼 BUY", 0: "⚖️ NEUTRAL", -1: "🔽 SELL", -2: "❌ STRONG SELL", None: "⚠️ No Data"}

for ticker in selected:
    st.subheader(f"📈 {ticker}")
    col1, col2 = st.columns([2, 1])

    signals = {}
    conf_score = 0
    valid_weights = 0
    bullish_frames = 0
    time_series_data = {}
    rsi_val, macd_val, macd_signal_val, rvol_val = None, None, None, None

    with st.spinner(f"Analyzing {ticker}..."):
        for tf, tf_data in frames.items():
            df = yf.download(ticker, interval=tf_data["interval"], period=tf_data["period"], progress=False)

            if df.empty:
                signals[tf] = None
                continue

            flat_cols = []
            for col in df.columns:
                flat_col = "_".join([str(c) for c in col if isinstance(col, tuple)]) if isinstance(col, tuple) else str(col)
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
            if tf == "1m":
                rsi_val = last["RSI"]
                macd_val = last.get("MACD")
                macd_signal_val = last.get("Signal")
                rvol_val = df["Volume"].iloc[-1] / df["Volume"].rolling(10).mean().iloc[-1] if len(df) >= 10 else 0

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

            time_series_data[tf] = df

    with col1:
        st.markdown("### Timeframe Signals")
        for tf, s in signals.items():
            label = emoji_map.get(s, "⚠️")
            st.write(f"**{tf}**: {label} (score: {s})")

    with col2:
        norm_conf = (conf_score / (2 * valid_weights)) * 100 if valid_weights > 0 else 0
        st.markdown("### Confidence Meter")
        st.progress(min(max(norm_conf / 100.0, 0.0), 1.0), text=f"{norm_conf:.1f}/100")

        hold_time = bullish_frames * 5
        time_suggestion = f"Hold ~{hold_time} min ({bullish_frames} bars)" if bullish_frames > 0 else "Avoid or scalp only"
        st.markdown("### ⏱️ Time-in-Trade")
        st.write(time_suggestion)

        st.markdown("### 🎯 Entry/Exit Suggestion")
        if rsi_val is not None and macd_val is not None and macd_signal_val is not None:
            if 30 < rsi_val < 60 and macd_val > macd_signal_val and rvol_val and rvol_val >= 1.5:
                st.success("Strong BUY entry confirmed ✅")
            elif rsi_val > 70 and macd_val < macd_signal_val and rvol_val < 1:
                st.error("Possible EXIT signal ⚠️")
            else:
                st.info("No confirmed entry/exit setup.")
        else:
            st.write("Insufficient signal data.")

        

        st.markdown("### 🧪 Simulated Level 2 Insight")
        if rsi_val is not None and macd_val is not None and macd_signal_val is not None:
            if rsi_val < 50 and macd_val > macd_signal_val and rvol_val and rvol_val >= 1.5:
                st.success("🟩 Buyers stacking bids — breakout likely")
                st.write("⏱️ Estimated breakout window: 2–3 bars")
            elif rsi_val > 60 and macd_val < macd_signal_val and rvol_val < 1:
                st.warning("🟥 Sell wall forming — resistance likely")
                st.write("⏱️ Possible reversal zone")
            else:
                st.info("⚪ No clear pressure detected")
        else:
            st.write("Waiting for Level 2 signals...")

        st.markdown("### 📰 News Headlines + Sentiment")
        news = get_news(ticker)
        if news:
            for item in news:
                sentiment = score_sentiment(item['title'])
                st.markdown(f"{sentiment} [{item['title']}]({item['link']})")
        else:
            st.write("No headlines found.")

    with st.expander("📉 View Charts"):
        for tf, df in time_series_data.items():
            st.markdown(f"**{ticker} - {tf}**")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Price", line=dict(color="blue")))
            fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", yaxis="y2", line=dict(color="orange")))
            fig.update_layout(
                xaxis_title="Time",
                yaxis=dict(title="Price", side="left"),
                yaxis2=dict(title="RSI", overlaying="y", side="right", showgrid=False),
                height=350,
                margin=dict(l=10, r=10, t=20, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    time.sleep(0.2)
 
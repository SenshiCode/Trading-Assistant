import streamlit as st
import pandas as pd
import requests
from datetime import datetime

st.set_page_config(page_title="📈 Top Gappers Scanner", layout="wide")
st.title("🚀 Top Gappers & Momentum Scanner")

@st.cache_data(ttl=300)
def load_gainers():
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds=day_gainers&count=100"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

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

                if price < 50:
                    rows.append({
                        "Symbol": symbol,
                        "Name": name,
                        "Price": price,
                        "Gap %": round(change, 2),
                        "Volume": volume
                    })
            except:
                continue
        df = pd.DataFrame(rows)
        return df.sort_values(by="Gap %", ascending=False)

    except Exception as e:
        st.error(f"Error parsing Yahoo response: {e}")
        return pd.DataFrame()

# Load and display
with st.spinner("📡 Loading top gainers under $50..."):
    data = load_gainers()

if not data.empty:
    st.dataframe(data.reset_index(drop=True), use_container_width=True)
else:
    st.warning("⚠️ No data returned. Yahoo Finance API may be blocked or rate-limited.")

st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
import yfinance as yf
import pandas as pd

# 🔹 Step 1: Define your watchlist — change this anytime
tickers = ["AAPL", "MSFT", "TSLA", "NVDA", "GOOGL", "AMZN"]

# 🔹 Step 2: Set up a results list
results = []

for ticker in tickers:
    try:
        df = yf.download(ticker, period="120d", interval="1d", progress=False)

        # Calculate RSI
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # Calculate MACD
        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

        df.dropna(inplace=True)
        if df.empty:
            continue

        # Get the latest values
        rsi_val = df["RSI"].iloc[-1].item()
        macd_val = df["MACD"].iloc[-1].item()
        signal_val = df["Signal"].iloc[-1].item()

        # Signal logic
        score = 0
        if rsi_val < 30:
            score += 1
        elif rsi_val > 70:
            score -= 1
        if macd_val > signal_val:
            score += 1
        elif macd_val < signal_val:
            score -= 1

        if score >= 2:
            suggestion = "STRONG BUY ✅"
        elif score == 1:
            suggestion = "BUY 🔼"
        elif score == 0:
            suggestion = "NEUTRAL ⚖️"
        elif score == -1:
            suggestion = "SELL 🔽"
        else:
            suggestion = "STRONG SELL ❌"

        results.append({
            "Ticker": ticker,
            "RSI": round(rsi_val, 2),
            "MACD": round(macd_val, 2),
            "Signal": round(signal_val, 2),
            "Score": score,
            "Suggestion": suggestion
        })

    except Exception as e:
        print(f"Error with {ticker}: {e}")

# 🔹 Step 3: Display results sorted by strongest signals
df_results = pd.DataFrame(results)
df_results.sort_values("Score", ascending=False, inplace=True)

print("\n📊 Signal Results:\n")
print(df_results.to_string(index=False))
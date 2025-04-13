import yfinance as yf
import pandas as pd
import pandas_ta as ta

# Define the tickers you want to scan
tickers = ["AAPL", "TSLA", "NVDA"]

# Define timeframes to pull
timeframes = {
    "1m": {"interval": "1m", "period": "1d", "weight": 0.35},
    "5m": {"interval": "5m", "period": "5d", "weight": 0.30},
    "10m": {"interval": "5m", "period": "5d", "weight": 0.20},  # resampled from 5m
    "1d": {"interval": "1d", "period": "90d", "weight": 0.15},
}

for ticker in tickers:
    print(f"\n🔍 Analyzing {ticker}...\n")
    data = {}
    signals = {}

    for tf_name, tf_params in timeframes.items():
        print(f"  ⏱️ Loading {tf_name} timeframe...")

        df = yf.download(
            ticker,
            interval=tf_params["interval"],
            period=tf_params["period"],
            progress=False
        )

        if df.empty:
            print(f"    ⚠️ No data for {tf_name} timeframe.")
            continue

        # Normalize column names
        flat_cols = []
        for col in df.columns:
            if isinstance(col, tuple):
                flat_col = "_".join([str(c) for c in col if c])
            else:
                flat_col = str(col)
            flat_cols.append(flat_col)
        df.columns = [col.split("_")[0].capitalize() for col in flat_cols]

        if tf_name == "10m":
            required_cols = ["Open", "High", "Low", "Close", "Volume"]
            if all(col in df.columns for col in required_cols):
                df = df.resample("10min").agg({
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum"
                }).dropna()
            else:
                print(f"    ⚠️ Cannot resample to 10m — missing columns: {df.columns.tolist()}")
                continue

        df.dropna(inplace=True)

        # Calculate RSI and MACD
        df["RSI"] = ta.rsi(df["Close"], length=14)
        macd = ta.macd(df["Close"])
        if macd is not None and "MACD_12_26_9" in macd.columns:
            df["MACD"] = macd["MACD_12_26_9"]
            df["Signal"] = macd["MACDs_12_26_9"]
        else:
            df["MACD"] = df["Signal"] = None

        df.dropna(inplace=True)
        data[tf_name] = df.tail(5)

        # Generate signal score
        if not df.empty:
            latest = df.iloc[-1]
            score = 0
            try:
                if latest["RSI"] < 30:
                    score += 1
                elif latest["RSI"] > 70:
                    score -= 1
                if latest["MACD"] > latest["Signal"]:
                    score += 1
                elif latest["MACD"] < latest["Signal"]:
                    score -= 1
                signals[tf_name] = score
            except:
                signals[tf_name] = None

    # Combine scores into a confidence meter (0-100 scale)
    confidence_score = 0
    valid_weights = 0
    signal_alignment = 0
    for tf, score in signals.items():
        weight = timeframes[tf].get("weight", 0.25)
        if score is not None:
            confidence_score += score * weight
            valid_weights += abs(weight)
            if score > 0:
                signal_alignment += 1

    # Normalize confidence to a 0-100 scale
    if valid_weights > 0:
        normalized_conf = (confidence_score / (2 * valid_weights)) * 100
    else:
        normalized_conf = 0

    # Estimate time in trade based on how many frames are bullish
    est_minutes = signal_alignment * 5  # assume each signal = 1 bar = ~5min
    est_hold = f"Hold for {est_minutes} minutes (~{signal_alignment} bars)" if signal_alignment > 0 else "Avoid or scalp only"

    # Display results
    print(f"\n✅ Signals for {ticker}:")
    for tf, score in signals.items():
        emoji = ""
        if score is None:
            emoji = "⚠️"
            label = "No data"
        elif score >= 2:
            emoji = "✅"
            label = "STRONG BUY"
        elif score == 1:
            emoji = "🔼"
            label = "BUY"
        elif score == 0:
            emoji = "⚖️"
            label = "NEUTRAL"
        elif score == -1:
            emoji = "🔽"
            label = "SELL"
        else:
            emoji = "❌"
            label = "STRONG SELL"
        print(f"  {tf}: {label} {emoji} (score: {score})")

    print(f"\n🔢 Confidence Score: {normalized_conf:.1f}/100")
    print(f"🕛 Estimated Time in Trade: {est_hold}")

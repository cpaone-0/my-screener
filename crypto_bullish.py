# ==========================================================
# Crypto Screener - BULLISH (Daily + 4H Combined)
# Runs as a standalone script via GitHub Actions (scheduled every 8 hours)
# ==========================================================
#
# Checks each coin on TWO timeframes and reports both:
#
#   DAILY (full 4-part check, includes volume):
#     1. MACD bullish cross    2. RSI recovering from oversold (<35)
#     3. Price above 50 EMA    4. Volume upturn
#
#   4H (3-part check - CoinGecko's free OHLC endpoint doesn't
#      return volume at this granularity, so volume is skipped here):
#     1. MACD bullish cross    2. RSI recovering from oversold (<35)
#     3. Price above 50 EMA
#
#   both_flagged = daily_flagged AND h4_flagged -> the strongest,
#   most convincing signal (your bigger-trend timeframe and your
#   timing timeframe agree).
#
# Data source: CoinGecko free public API (no key needed)
#   - Daily data: /market_chart endpoint (up to ~100 days history)
#   - 4H data: /ohlc endpoint (auto-returns 4H candles for a
#     3-30 day window - this is a free-tier feature)

import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ---- 1. YOUR WATCHLIST ----
WATCHLIST = {
    "bitcoin": "BTC",
    "sui": "SUI",
    "zcash": "ZEC",
    "solana": "SOL",
    "aave": "AAVE",
    "binancecoin": "BNB",
    "ethereum": "ETH",
    "uniswap": "UNI",
    "aster-2": "ASTER",
    "bittensor": "TAO",
    "hyperliquid": "HYPE",
    "near": "NEAR",
    "dogecoin": "DOGE",
    "walrus-2": "WAL",
    "chainlink": "LINK",
    "ondo-finance": "ONDO",
    "okb": "OKB",
    "ripple": "XRP",
    "arbitrum": "ARB",
    "bitcoin-cash": "BCH",
}

DAILY_DAYS = 100   # daily history window
H4_DAYS = 30       # 4H history window (CoinGecko free /ohlc gives 4H candles for a 3-30 day range)


def fetch_daily(coin_id, days=DAILY_DAYS, max_retries=5):
    """Daily close + volume from CoinGecko /market_chart."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    for attempt in range(max_retries):
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"    (daily rate limited, waiting {wait}s...)")
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()
        prices = pd.DataFrame(data["total_volumes"], columns=["ts", "volume"])
        closes = pd.DataFrame(data["prices"], columns=["ts", "close"])
        df = closes.merge(prices, on="ts")
        df["date"] = pd.to_datetime(df["ts"], unit="ms")
        return df[["date", "close", "volume"]]
    raise Exception(f"Still rate-limited after {max_retries} retries (daily)")


def fetch_4h(coin_id, days=H4_DAYS, max_retries=5):
    """4H OHLC closes from CoinGecko /ohlc (auto-granularity: 3-30 days -> 4H candles). No volume at this endpoint."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": days}
    for attempt in range(max_retries):
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"    (4H rate limited, waiting {wait}s...)")
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()  # [ [ts, open, high, low, close], ... ]
        if not data:
            raise Exception("empty 4H OHLC response")
        df = pd.DataFrame(data, columns=["ts", "open", "high", "low", "close"])
        df["date"] = pd.to_datetime(df["ts"], unit="ms")
        return df[["date", "close"]]
    raise Exception(f"Still rate-limited after {max_retries} retries (4H)")


def compute_core_indicators(df):
    """RSI, MACD, EMA50 - works on any 'close' series (daily or 4H)."""
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    return df


def check_core_bullish(df, min_len=35):
    """MACD cross / RSI recovering / above EMA50 - no volume. Shared logic for both timeframes."""
    if len(df) < min_len:
        return None
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    macd_cross = (prev["macd"] < prev["macd_signal"]) and (latest["macd"] > latest["macd_signal"])

    recent_rsi = df["rsi"].iloc[-10:]
    was_oversold = (recent_rsi < 35).any()
    rsi_rising = latest["rsi"] > prev["rsi"]
    rsi_recovering = was_oversold and rsi_rising

    above_ema50 = latest["close"] > latest["ema50"]

    return {
        "price": round(latest["close"], 4),
        "rsi": round(latest["rsi"], 1),
        "macd_cross": macd_cross,
        "rsi_recovering": rsi_recovering,
        "above_ema50": above_ema50,
    }


def run_screener():
    results = []
    for coin_id, ticker in WATCHLIST.items():
        row = {"ticker": ticker}

        # ---- DAILY (4-part, includes volume) ----
        try:
            daily_df = fetch_daily(coin_id)
            daily_df = compute_core_indicators(daily_df)
            daily_df["vol_avg10"] = daily_df["volume"].rolling(10).mean()
            core = check_core_bullish(daily_df, min_len=55)
            if core is None:
                row.update({"d_price": None, "d_rsi": None, "d_macd": None,
                            "d_rsi_rec": None, "d_ema": None, "d_vol": None, "daily_flagged": False})
            else:
                latest = daily_df.iloc[-1]
                vol_upturn = bool(latest["volume"] > latest["vol_avg10"])
                macd_cross = bool(core["macd_cross"])
                rsi_recovering = bool(core["rsi_recovering"])
                above_ema50 = bool(core["above_ema50"])
                d_flagged = macd_cross and rsi_recovering and above_ema50 and vol_upturn
                row.update({
                    "d_price": core["price"], "d_rsi": core["rsi"],
                    "d_macd": macd_cross, "d_rsi_rec": rsi_recovering,
                    "d_ema": above_ema50, "d_vol": vol_upturn,
                    "daily_flagged": bool(d_flagged),
                })
        except Exception as e:
            print(f"⚠️  {ticker}: daily fetch error ({e})")
            row.update({"d_price": None, "d_rsi": None, "d_macd": None,
                        "d_rsi_rec": None, "d_ema": None, "d_vol": None, "daily_flagged": False})
        time.sleep(7)

        # ---- 4H (3-part, no volume available) ----
        try:
            h4_df = fetch_4h(coin_id)
            h4_df = compute_core_indicators(h4_df)
            core4 = check_core_bullish(h4_df, min_len=35)
            if core4 is None:
                row.update({"h4_price": None, "h4_rsi": None, "h4_macd": None,
                            "h4_rsi_rec": None, "h4_ema": None, "h4_flagged": False})
            else:
                macd_cross4 = bool(core4["macd_cross"])
                rsi_recovering4 = bool(core4["rsi_recovering"])
                above_ema50_4 = bool(core4["above_ema50"])
                h4_flagged = macd_cross4 and rsi_recovering4 and above_ema50_4
                row.update({
                    "h4_price": core4["price"], "h4_rsi": core4["rsi"],
                    "h4_macd": macd_cross4, "h4_rsi_rec": rsi_recovering4,
                    "h4_ema": above_ema50_4, "h4_flagged": bool(h4_flagged),
                })
        except Exception as e:
            print(f"⚠️  {ticker}: 4H fetch error ({e})")
            row.update({"h4_price": None, "h4_rsi": None, "h4_macd": None,
                        "h4_rsi_rec": None, "h4_ema": None, "h4_flagged": False})
        time.sleep(11)

        row["both_flagged"] = bool(row.get("daily_flagged")) and bool(row.get("h4_flagged"))

        print(f"{'🟢🟢' if row['both_flagged'] else ('🟢 ' if row.get('daily_flagged') else '   ')} "
              f"{ticker:6s} daily_price={row.get('d_price')}  daily_flag={row.get('daily_flagged')}  "
              f"4h_price={row.get('h4_price')}  4h_flag={row.get('h4_flagged')}")

        results.append(row)

    print("\n=== BOTH TIMEFRAMES FLAGGED (strongest signal) ===")
    both = [r["ticker"] for r in results if r.get("both_flagged")]
    print("  " + ", ".join(both) if both else "  None right now.")

    print("\n=== DAILY ONLY FLAGGED ===")
    daily_only = [r["ticker"] for r in results if r.get("daily_flagged") and not r.get("both_flagged")]
    print("  " + ", ".join(daily_only) if daily_only else "  None right now.")

    print("\n=== 4H ONLY FLAGGED ===")
    h4_only = [r["ticker"] for r in results if r.get("h4_flagged") and not r.get("both_flagged")]
    print("  " + ", ".join(h4_only) if h4_only else "  None right now.")

    return pd.DataFrame(results)


def export_html(df, filename="reports/bullish_screener_results.html"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    def bool_icon(val):
        if isinstance(val, bool):
            return "✅" if val else "—"
        return val if val is not None else "n/a"

    display_df = df.copy()
    bool_cols = ["d_macd", "d_rsi_rec", "d_ema", "d_vol", "daily_flagged",
                 "h4_macd", "h4_rsi_rec", "h4_ema", "h4_flagged", "both_flagged"]
    for col in bool_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(bool_icon)

    col_order = ["ticker", "d_price", "d_rsi", "d_macd", "d_rsi_rec", "d_ema", "d_vol", "daily_flagged",
                 "h4_price", "h4_rsi", "h4_macd", "h4_rsi_rec", "h4_ema", "h4_flagged", "both_flagged"]
    display_df = display_df[[c for c in col_order if c in display_df.columns]]

    def row_color(row):
        both = df.loc[row.name, "both_flagged"]
        daily = df.loc[row.name, "daily_flagged"]
        h4 = df.loc[row.name, "h4_flagged"]
        if both:
            color = "#8fe08f"   # strong green - both timeframes agree
        elif daily or h4:
            color = "#d4f7d4"   # light green - one timeframe only
        else:
            color = "#ffffff"
        return [f"background-color: {color}"] * len(row)

    styled = (display_df.style
              .format({"d_price": "{:.4f}", "d_rsi": "{:.1f}", "h4_price": "{:.4f}", "h4_rsi": "{:.1f}"}, na_rep="n/a")
              .apply(row_color, axis=1)
              .set_table_styles([
                  {"selector": "th", "props": [("background-color", "#2b2b2b"), ("color", "white"),
                                                 ("padding", "6px"), ("text-align", "center"), ("font-size", "12px")]},
                  {"selector": "td", "props": [("padding", "6px"), ("text-align", "center"),
                                                 ("font-family", "Arial, sans-serif"), ("font-size", "12px")]},
              ])
              .set_caption(f"Bullish Screener (Daily + 4H) — {timestamp}"))

    html_content = f"""
    <html><head><meta charset="utf-8"><title>Bullish Screener Results</title></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
    <h2>🟢 Bullish Screener (Daily + 4H) — {timestamp}</h2>
    <p><b>Dark green</b> = both timeframes flagged (strongest signal). <b>Light green</b> = one timeframe flagged. White = neither.</p>
    <p>Columns prefixed <code>d_</code> = daily (4-part, includes volume). Prefixed <code>h4_</code> = 4-hour (3-part, no volume data at this granularity).</p>
    {styled.to_html()}
    </body></html>
    """

    with open(filename, "w") as f:
        f.write(html_content)

    print(f"\n✅ Saved report: {filename}")


# ---- RUN IT ----
if __name__ == "__main__":
    results_df = run_screener()
    export_html(results_df)
    print(f"\nDone. {len(results_df)} tickers processed.")

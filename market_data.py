"""
market_data.py — Fetches OHLCV candles from Binance public API via ccxt.
No API key required for market data.
"""

import ccxt
import pandas as pd
import logging

logger = logging.getLogger(__name__)

TIMEFRAMES = {
    "15m": {"limit": 100, "label": "15-minute"},
    "1h":  {"limit": 100, "label": "1-hour"},
    "4h":  {"limit": 100, "label": "4-hour"},
}


def get_exchange():
    return ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })


def fetch_candles(symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 100) -> pd.DataFrame:
    """Fetch OHLCV candles. Returns DataFrame indexed by UTC timestamp."""
    exchange = get_exchange()
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").astype(float)
        return df
    except Exception as e:
        logger.error(f"Failed to fetch {symbol} {timeframe}: {e}")
        raise


def fetch_all_timeframes(symbol: str = "BTC/USDT") -> dict:
    """Fetch all configured timeframes for a symbol."""
    result = {}
    for tf, cfg in TIMEFRAMES.items():
        result[tf] = fetch_candles(symbol, timeframe=tf, limit=cfg["limit"])
        logger.debug(f"Fetched {len(result[tf])} candles for {symbol} {tf}")
    return result


def get_current_price(symbol: str = "BTC/USDT") -> float:
    """Get the latest close price."""
    exchange = get_exchange()
    ticker = exchange.fetch_ticker(symbol)
    return float(ticker["last"])


def get_market_summary(symbol: str = "BTC/USDT") -> dict:
    """Get 24h market summary."""
    exchange = get_exchange()
    ticker = exchange.fetch_ticker(symbol)
    return {
        "price":      float(ticker["last"]),
        "change_24h": float(ticker.get("percentage", 0)),
        "volume_24h": float(ticker.get("quoteVolume", 0)),
        "high_24h":   float(ticker.get("high", 0)),
        "low_24h":    float(ticker.get("low", 0)),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    summary = get_market_summary()
    print(f"BTC/USDT: ${summary['price']:,.2f}  |  24h: {summary['change_24h']:.2f}%  |  Vol: ${summary['volume_24h']:,.0f}")
    candles = fetch_candles("BTC/USDT", "1h", limit=5)
    print(f"\nLast 5 x 1h candles:\n{candles[['open','high','low','close','volume']].to_string()}")

"""真实技术指标计算——基于个股历史K线序列，替代 pct 线性近似。

所有函数输入均为按时间升序排列的序列，返回最新一根 K 线对应的指标值。
"""

from __future__ import annotations


def compute_indicators(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    amounts: list[float] | None = None,
    open_prices: list[float] | None = None,
) -> dict:
    """从价格序列计算真实技术指标，返回可合并到 factor dict 的字段。

    closes 必须提供且长度 >= 2。其他序列可选，缺失时对应指标退回近似值。
    """
    n = len(closes)
    if n < 2:
        return _empty()

    highs = highs or []
    lows = lows or []
    volumes = volumes or []
    amounts = amounts or []
    open_prices = open_prices or []

    result: dict = {}

    # --- 均线 ---
    ma50 = _sma(closes, 50)
    result["ma_50"] = round(ma50, 2) if ma50 is not None else None
    result["aboveMa"] = bool(ma50 is not None and closes[-1] > ma50)

    # --- RSI(14) ---
    result["rsi"] = round(_rsi(closes, 14), 1)

    # --- MACD ---
    macd_line, signal_line, histogram = _macd(closes)
    if macd_line is not None and signal_line is not None:
        result["macdLine"] = round(macd_line, 4)
        result["macdSignal"] = round(signal_line, 4)
        result["macdHistogram"] = round(histogram, 4)
        result["macdCross"] = macd_line > signal_line
    else:
        result["macdCross"] = None  # 数据不足，由上层决定是否退回近似值

    # --- 量比 ---
    if len(volumes) >= 21:
        avg_vol = _sma(volumes[:-1], 20)
        result["volRatio"] = round(volumes[-1] / avg_vol, 2) if avg_vol else 1.0
    else:
        result["volRatio"] = None

    # --- N 日新高 ---
    if highs:
        latest_high = highs[-1]
        high_days = 1
        for h in reversed(highs[:-1]):
            if h >= latest_high:
                break
            high_days += 1
        result["highDays"] = high_days
    else:
        result["highDays"] = None

    # --- 下影线比率 ---
    if highs and lows and open_prices and len(highs) == n:
        result["lowerShadowRatio"] = round(_lower_shadow(open_prices[-1], highs[-1], lows[-1], closes[-1]), 2)

    return result


def _empty() -> dict:
    return {
        "ma_50": None,
        "aboveMa": None,
        "rsi": 50.0,
        "macdCross": None,
        "volRatio": None,
        "highDays": None,
        "lowerShadowRatio": None,
    }


# ---- 基础计算 ----

def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _ema(values: list[float], period: int) -> list[float]:
    """返回与输入等长的 EMA 序列（前 period-1 个值为 0）。"""
    if len(values) < period:
        return [0.0] * len(values)
    multiplier = 2 / (period + 1)
    result = [0.0] * (period - 1)
    seed = sum(values[:period]) / period
    result.append(seed)
    for price in values[period:]:
        result.append((price - result[-1]) * multiplier + result[-1])
    return result


def _rsi(closes: list[float], period: int = 14) -> float:
    """Wilder's RSI。"""
    if len(closes) < period + 1:
        return 50.0
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def _macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD 指标。返回 (macd_line, signal_line, histogram)。"""
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_series = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_series = _ema(macd_series, signal)
    return macd_series[-1], signal_series[-1], macd_series[-1] - signal_series[-1]


def _lower_shadow(open_price: float, high: float, low: float, close: float) -> float:
    """下影线比率：(min(open, close) - low) / (high - low)。"""
    hl_range = high - low
    if hl_range <= 0:
        return 0.5
    body_low = min(open_price, close)
    return max(0.0, (body_low - low) / hl_range)

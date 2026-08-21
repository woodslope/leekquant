"""真实技术指标计算模块的单元测试。"""

from __future__ import annotations

import unittest

from server.engine.indicators import _ema, _macd, _rsi, _sma, compute_indicators


class IndicatorsTest(unittest.TestCase):
    # ---- SMA ----

    def test_sma_returns_none_when_insufficient_data(self):
        self.assertIsNone(_sma([10, 20], 5))

    def test_sma_returns_average_of_last_n(self):
        self.assertAlmostEqual(_sma([1, 2, 3, 4, 5], 3), 4.0)  # (3+4+5)/3

    # ---- EMA ----

    def test_ema_length_matches_input(self):
        closes = list(range(10, 20))
        result = _ema(closes, 5)
        self.assertEqual(len(result), len(closes))

    def test_ema_increases_after_uptrend(self):
        closes = [10] * 10 + list(range(11, 21))
        result = _ema(closes, 5)
        self.assertGreater(result[-1], result[10])

    # ---- RSI ----

    def test_rsi_returns_50_with_insufficient_data(self):
        self.assertEqual(_rsi([10, 20], 14), 50.0)

    def test_rsi_100_when_all_gains(self):
        closes = list(range(10, 30))  # monotonic increase
        rsi = _rsi(closes, 14)
        self.assertAlmostEqual(rsi, 100.0, places=0)

    def test_rsi_0_when_all_losses(self):
        closes = list(range(30, 10, -1))  # monotonic decrease
        rsi = _rsi(closes, 14)
        self.assertAlmostEqual(rsi, 0.0, places=0)

    def test_rsi_around_50_when_flat(self):
        closes = [20.0, 20.1] * 20  # tiny changes
        rsi = _rsi(closes, 14)
        self.assertAlmostEqual(rsi, 50.0, delta=10)

    # ---- MACD ----

    def test_macd_returns_none_with_insufficient_data(self):
        macd_line, signal_line, hist = _macd(list(range(10)))
        self.assertIsNone(macd_line)
        self.assertIsNone(signal_line)

    def test_macd_cross_detectable_in_uptrend(self):
        # 构造先平后涨的走势：MACD 应由负转正
        closes = [10] * 40 + list(range(10, 20))
        macd_line, signal_line, hist = _macd(closes)
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)
        self.assertGreater(macd_line, 0)  # 上涨走势中 MACD 应为正

    # ---- compute_indicators ----

    def test_empty_when_less_than_2_bars(self):
        result = compute_indicators([10.0])
        self.assertEqual(result["rsi"], 50.0)
        self.assertIsNone(result["aboveMa"])

    def test_returns_all_keys_with_sufficient_data(self):
        n = 60
        closes = [20.0 + i * 0.1 for i in range(n)]
        highs = [c + 0.5 for c in closes]
        lows = [c - 0.5 for c in closes]
        volumes = [1000] * n
        amounts = [20000] * n
        opens = [c - 0.05 for c in closes]

        result = compute_indicators(closes, highs, lows, volumes, amounts, opens)
        self.assertIsNotNone(result["rsi"])
        self.assertIsNotNone(result["aboveMa"])
        self.assertIsNotNone(result["macdCross"])
        self.assertIsNotNone(result["highDays"])
        self.assertIsNotNone(result["lowerShadowRatio"])
        self.assertGreaterEqual(result["rsi"], 50)  # 上涨走势 RSI 应 >= 50

    def test_high_days_counts_consecutive_lower_highs(self):
        closes = list(range(30, 0, -1))
        highs = [c + 1 for c in closes]
        result = compute_indicators(closes, highs)
        # 一直下跌，每日高点都比前一天低 → highDays 应该为 1
        self.assertEqual(result["highDays"], 1)

    def test_vol_ratio_compares_to_20day_average(self):
        n = 30
        closes = [10.0] * n
        volumes = [1000] * 20 + [3000] * 10  # 最近 10 天放量 3 倍
        result = compute_indicators(closes, volumes=volumes)
        self.assertIsNotNone(result["volRatio"])
        self.assertGreater(result["volRatio"], 1.5)  # 放量期间量比应 > 1


if __name__ == "__main__":
    unittest.main()

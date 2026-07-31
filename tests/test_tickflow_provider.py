from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from server.engine.rules import scan
from server.providers.tickflow_provider import TickFlowProvider


class FakeRow:
    """模拟 pandas Series，同时支持 .to_dict() 和 ["key"] 访问。"""

    def __init__(self, data: dict):
        self._data = data

    def to_dict(self) -> dict:
        return self._data

    def __getitem__(self, key: str):
        return self._data[key]


class FakeSeries:
    """模拟 pandas Series，支持 .iloc / .tail / .head / .mean / astype。"""

    def __init__(self, values: list):
        self._values = list(values)

    def astype(self, dtype) -> "FakeSeries":
        return FakeSeries([float(v) for v in self._values])

    def tail(self, n: int) -> "FakeSeries":
        return FakeSeries(self._values[-n:])

    def head(self, n: int) -> "FakeSeries":
        return FakeSeries(self._values[:n])

    def mean(self) -> float:
        if not self._values:
            return 0.0
        return sum(self._values) / len(self._values)

    def __len__(self) -> int:
        return len(self._values)

    @property
    def iloc(self):
        return _FakeSeriesILoc(self._values)


class _FakeSeriesILoc:
    def __init__(self, values: list):
        self._values = values

    def __getitem__(self, index):
        if isinstance(index, int):
            return self._values[index]
        return FakeSeries(self._values[index])


class FakeDataFrame:
    """模拟 pandas DataFrame，覆盖 TickFlowProvider 使用的所有属性和方法。"""

    empty = False

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def to_dict(self, orient: str = "records") -> list[dict]:
        return self._rows

    def head(self, n: int) -> "FakeDataFrame":
        return FakeDataFrame(self._rows[:n])

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, key: str) -> FakeSeries:
        return FakeSeries([row.get(key, 0) for row in self._rows])

    @property
    def iloc(self):
        return _FakeILoc(self._rows)


class _FakeILoc:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def __getitem__(self, index):
        if isinstance(index, int):
            return FakeRow(self._rows[index])
        return FakeDataFrame(self._rows[index])


def _make_tickflow_module(client):
    """构造一个假的 tickflow 模块，返回给定的 client 实例。"""
    mod = types.ModuleType("tickflow")
    mod.TickFlow = lambda api_key=None: client
    mod.TickFlow.free = lambda: client
    return mod


class TickFlowProviderTest(unittest.TestCase):
    # ---- init ----

    def test_init_free_mode_when_no_api_key(self):
        """无 TICKFLOW_API_KEY 时使用免费客户端。"""
        client = types.SimpleNamespace()
        fake_mod = _make_tickflow_module(client)

        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            self.assertFalse(provider._has_paid)
            self.assertEqual(provider.tf, client)

    def test_init_paid_mode_when_api_key_present(self):
        """有 TICKFLOW_API_KEY 时使用付费客户端。"""
        client = types.SimpleNamespace()
        fake_mod = _make_tickflow_module(client)

        with patch.dict("os.environ", {"TICKFLOW_API_KEY": "sk-xxx"}), patch.dict(
            "sys.modules", {"tickflow": fake_mod}
        ):
            provider = TickFlowProvider()
            self.assertTrue(provider._has_paid)

    # ---- stock_daily ----

    def test_stock_daily_maps_rows_to_project_contract(self):
        """stock_daily 应将 TickFlow 日线行映射为项目标准字段。"""
        client = types.SimpleNamespace()
        client.klines = types.SimpleNamespace()
        client.klines.get = lambda symbol, period, count, as_dataframe: FakeDataFrame(
            [
                {
                    "symbol": "600000.SH",
                    "trade_date": "2026-07-09",
                    "open": "10.10",
                    "high": "10.80",
                    "low": "9.90",
                    "close": "10.50",
                    "volume": "120000",
                    "amount": "1300000",
                    "pct_chg": "2.3",
                }
            ]
        )

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            rows = provider.stock_daily("600000", "20260701", "20260709")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["code"], "600000")
        self.assertEqual(rows[0]["date"], "2026-07-09")
        self.assertEqual(rows[0]["open"], 10.10)
        self.assertEqual(rows[0]["close"], 10.50)
        self.assertEqual(rows[0]["amount"], 1300000.0)
        self.assertEqual(rows[0]["pct"], 2.3)

    def test_stock_daily_calculates_pct_from_prev_close(self):
        """API 未返回 pct_chg 时，stock_daily 应基于前一日收盘价反推。"""
        client = types.SimpleNamespace()
        client.klines = types.SimpleNamespace()
        client.klines.get = lambda symbol, period, count, as_dataframe: FakeDataFrame(
            [
                {
                    "symbol": "600000.SH",
                    "trade_date": "2026-07-08",
                    "open": "10.00",
                    "high": "10.30",
                    "low": "9.80",
                    "close": "10.00",
                    "volume": "100000",
                    "amount": "1000000",
                },
                {
                    "symbol": "600000.SH",
                    "trade_date": "2026-07-09",
                    "open": "10.10",
                    "high": "10.80",
                    "low": "9.90",
                    "close": "10.50",
                    "volume": "120000",
                    "amount": "1300000",
                },
            ]
        )

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            rows = provider.stock_daily("600000", "20260701", "20260710")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["pct"], 0.0)  # 第一行无前日数据
        self.assertEqual(rows[1]["pct"], 5.0)  # (10.50 / 10.00 - 1) * 100

    def test_stock_daily_empty_dataframe_returns_empty_list(self):
        """DataFrame 为空时返回空列表。"""
        empty_df = FakeDataFrame([])
        empty_df.empty = True

        client = types.SimpleNamespace()
        client.klines = types.SimpleNamespace()
        client.klines.get = lambda symbol, period, count, as_dataframe: empty_df

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            rows = provider.stock_daily("600000", "20260701", "20260709")

        self.assertEqual(rows, [])

    # ---- today_market (free) ----

    def test_today_market_free_uses_klines_batch_and_index(self):
        """免费层 today_market 应使用 klines.batch + 上证指数日线。"""
        index_rows = []
        for day in range(1, 31):
            index_rows.append(
                {
                    "trade_date": f"2026-06-{day:02d}",
                    "close": str(3200 + day),
                    "volume": str(1000000 + day * 1000),
                }
            )

        client = types.SimpleNamespace()
        client.klines = types.SimpleNamespace()

        def fake_get(symbol, period, count, as_dataframe):
            if "000001" in symbol:
                return FakeDataFrame(index_rows)
            return FakeDataFrame([])

        client.klines.get = fake_get

        def fake_batch(symbols, period, count, as_dataframe):
            self.assertEqual(count, 2)  # 应拉取 2 天数据
            result = {}
            for sym in symbols[:2]:  # 只构造前两只
                result[sym] = FakeDataFrame(
                    [
                        {
                            "symbol": sym,
                            "trade_date": "2026-07-08",
                            "open": "10.00",
                            "high": "10.30",
                            "low": "9.80",
                            "close": "10.00",
                            "volume": "100000",
                            "amount": "1000000",
                        },
                        {
                            "symbol": sym,
                            "trade_date": "2026-07-09",
                            "open": "10.10",
                            "high": "10.80",
                            "low": "9.90",
                            "close": "10.50",
                            "volume": "120000",
                            "amount": "1300000000",
                        },
                    ]
                )
            return result

        client.klines.batch = fake_batch

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider(limit=2)
            provider._symbols = ["600000.SH", "600001.SH"]  # 缩小股票池加速测试
            market = provider.today_market()

        self.assertIn("date", market)
        self.assertEqual(market["date"], "2026-07-09")
        self.assertEqual(len(market["stocks"]), 2)
        # pct 应基于前日收盘价计算
        self.assertAlmostEqual(market["stocks"][0]["surgePct"], 5.0, places=1)

    def test_today_market_free_raises_when_no_stocks_returned(self):
        """免费层在 klines.batch 全部返回空时应抛出异常。"""
        client = types.SimpleNamespace()
        client.klines = types.SimpleNamespace()
        client.klines.batch = lambda symbols, period, count, as_dataframe: {}
        client.klines.get = lambda symbol, period, count, as_dataframe: FakeDataFrame([])

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            provider._symbols = ["600000.SH"]
            with self.assertRaisesRegex(RuntimeError, "未返回任何股票日线数据"):
                provider.today_market()

    # ---- today_market output contract ----

    def test_today_market_output_matches_scan_contract(self):
        """today_market 输出应符合 scan 引擎所需的字段契约。"""
        index_rows = []
        for day in range(1, 31):
            index_rows.append(
                {
                    "trade_date": f"2026-06-{day:02d}",
                    "close": str(3200 + day),
                    "volume": str(1000000 + day * 1000),
                }
            )

        client = types.SimpleNamespace()
        client.klines = types.SimpleNamespace()
        client.klines.get = lambda symbol, period, count, as_dataframe: FakeDataFrame(index_rows)

        def fake_batch(symbols, period, count, as_dataframe):
            return {
                "600000.SH": FakeDataFrame(
                    [
                        {
                            "symbol": "600000.SH",
                            "name": "浦发银行",
                            "trade_date": "2026-07-08",
                            "open": "10.00",
                            "high": "10.30",
                            "low": "9.80",
                            "close": "10.00",
                            "volume": "100000",
                            "amount": "1000000",
                        },
                        {
                            "symbol": "600000.SH",
                            "name": "浦发银行",
                            "trade_date": "2026-07-09",
                            "open": "10.10",
                            "high": "10.80",
                            "low": "9.90",
                            "close": "10.50",
                            "volume": "120000",
                            "amount": "1300000000",
                        },
                    ]
                )
            }

        client.klines.batch = fake_batch

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider(limit=1)
            provider._symbols = ["600000.SH"]
            market = provider.today_market()

        required_market_fields = {
            "date", "indexAboveMa", "limitDownCount", "crashDays",
            "marketDrop", "marketVolRatio", "ma20Up", "time", "stocks",
        }
        required_stock_fields = {
            "id", "name", "closeAbovePrev", "closeAboveOpen", "highDays",
            "gapUp", "surgePct", "aboveMa", "fundSafeDays", "macdCross",
            "superInflowDays", "volRatio", "rsi", "mainInflowPct",
            "northDays", "northPct", "backtestReturn", "maxLoss", "exitReason",
        }

        self.assertTrue(required_market_fields.issubset(market))
        self.assertEqual(len(market["stocks"]), 1)
        self.assertEqual(market["stocks"][0]["id"], "600000")
        self.assertTrue(required_stock_fields.issubset(market["stocks"][0]))

        # 应能正常通过 scan 引擎
        result = scan({}, market)
        self.assertIn("funnel", result)
        self.assertIn("signals", result)

    # ---- today_market (paid) ----

    def test_today_market_paid_uses_quotes_get(self):
        """付费层 today_market 应使用 quotes.get 获取行情。"""
        client = types.SimpleNamespace()
        client.quotes = types.SimpleNamespace()

        def fake_quotes_get(universes, as_dataframe):
            self.assertEqual(universes, ["CN_Equity_A"])
            return FakeDataFrame(
                [
                    {
                        "symbol": "600000.SH",
                        "name": "浦发银行",
                        "trade_date": "2026-07-09",
                        "open": "10.10",
                        "high": "10.80",
                        "low": "9.90",
                        "close": "10.50",
                        "pre_close": "10.00",
                        "change_pct": "5.0",
                        "amount": "1300000000",
                        "turnover": "2.5",
                    }
                ]
            )

        client.quotes.get = fake_quotes_get

        # 指数日线
        def fake_klines_get(symbol, period, count, as_dataframe):
            rows = [
                {"trade_date": f"2026-06-{day:02d}", "close": str(3200 + day), "volume": str(1000000 + day * 1000)}
                for day in range(1, 31)
            ]
            return FakeDataFrame(rows)

        client.klines = types.SimpleNamespace()
        client.klines.get = fake_klines_get

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {"TICKFLOW_API_KEY": "sk-xxx"}), patch.dict(
            "sys.modules", {"tickflow": fake_mod}
        ):
            provider = TickFlowProvider(limit=1)
            market = provider.today_market()

        self.assertEqual(len(market["stocks"]), 1)
        self.assertEqual(market["stocks"][0]["id"], "600000")
        self.assertEqual(market["stocks"][0]["surgePct"], 5.0)

    # ---- code format helpers ----

    def test_to_tickflow_shanghai(self):
        client = types.SimpleNamespace()
        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            self.assertEqual(provider._to_tickflow("600000"), "600000.SH")
            self.assertEqual(provider._to_tickflow("601318"), "601318.SH")

    def test_to_tickflow_shenzhen(self):
        client = types.SimpleNamespace()
        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            self.assertEqual(provider._to_tickflow("000001"), "000001.SZ")
            self.assertEqual(provider._to_tickflow("002594"), "002594.SZ")
            self.assertEqual(provider._to_tickflow("300750"), "300750.SZ")

    def test_to_tickflow_beijing(self):
        client = types.SimpleNamespace()
        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            self.assertEqual(provider._to_tickflow("430047"), "430047.BJ")
            self.assertEqual(provider._to_tickflow("830799"), "830799.BJ")

    def test_to_tickflow_already_formatted(self):
        client = types.SimpleNamespace()
        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            self.assertEqual(provider._to_tickflow("600000.SH"), "600000.SH")
            self.assertEqual(provider._to_tickflow("000001.SZ"), "000001.SZ")

    def test_plain_code_extraction(self):
        client = types.SimpleNamespace()
        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            self.assertEqual(provider._plain_code("600000.SH"), "600000")
            self.assertEqual(provider._plain_code("000001.SZ"), "000001")
            self.assertEqual(provider._plain_code("sh.600000"), "sh")

    # ---- historical_markets ----

    def test_historical_markets_returns_list_with_dates(self):
        """historical_markets 返回包含指定日期的列表。"""
        client = types.SimpleNamespace()
        client.klines = types.SimpleNamespace()

        def fake_batch(symbols, period, count, as_dataframe):
            return {
                "600000.SH": FakeDataFrame(
                    [
                        {
                            "symbol": "600000.SH",
                            "name": "test",
                            "trade_date": "2026-07-09",
                            "open": "10.00", "high": "10.50", "low": "9.90",
                            "close": "10.20", "volume": "100000", "amount": "1000000",
                        },
                        {
                            "symbol": "600000.SH",
                            "name": "test",
                            "trade_date": "2026-07-09",
                            "open": "10.00", "high": "10.50", "low": "9.90",
                            "close": "10.20", "volume": "100000", "amount": "1000000",
                        },
                    ]
                )
            }

        client.klines.batch = fake_batch

        def fake_get(symbol, period, count, as_dataframe):
            return FakeDataFrame(
                [
                    {"trade_date": f"2026-06-{day:02d}", "close": str(3200 + day), "volume": str(1000000)}
                    for day in range(1, 31)
                ]
            )

        client.klines.get = fake_get

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider(limit=1)
            provider._symbols = ["600000.SH"]
            result = provider.historical_markets(start="2025-01-02", end="2025-12-31")

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["date"], "2025-01-02")
        self.assertEqual(result[1]["date"], "2025-12-31")

    def test_historical_markets_reconstructs_daily_snapshots(self):
        """historical_markets 应从批量日线数据按交易日重建 market 快照。"""
        client = types.SimpleNamespace()
        client.klines = types.SimpleNamespace()

        def fake_batch(symbols, period, count, as_dataframe):
            return {
                "600000.SH": FakeDataFrame(
                    [
                        {"symbol": "600000.SH", "name": "test", "trade_date": "2026-07-08", "open": "10.0", "high": "10.5", "low": "9.9", "close": "10.0", "volume": "100000", "amount": "1000000"},
                        {"symbol": "600000.SH", "name": "test", "trade_date": "2026-07-09", "open": "10.2", "high": "10.8", "low": "10.0", "close": "10.5", "volume": "120000", "amount": "1300000"},
                    ]
                )
            }

        client.klines.batch = fake_batch

        def fake_get(symbol, period, count, as_dataframe):
            return FakeDataFrame(
                [{"trade_date": f"2026-07-{day:02d}", "close": str(3200 + day), "volume": str(1000000)} for day in range(1, 15)]
            )

        client.klines.get = fake_get

        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider(limit=1)
            provider._symbols = ["600000.SH"]
            result = provider.historical_markets(start="20260701", end="20260715")

        # 应有 2 个交易日（07-08 和 07-09 在范围内）
        self.assertGreaterEqual(len(result), 1)
        dates = [m["date"] for m in result]
        self.assertIn("2026-07-08", dates)
        self.assertIn("2026-07-09", dates)
        # 每个 snapshot 应有完整字段
        for m in result:
            self.assertIn("indexAboveMa", m)
            self.assertIn("marketDrop", m)
            self.assertIn("stocks", m)
            self.assertEqual(len(m["stocks"]), 1)
            self.assertEqual(m["stocks"][0]["id"], "600000")
        # pct 应基于前日收盘价计算（07-09: (10.5/10.0-1)*100 = 5.0）
        day09 = next(m for m in result if m["date"] == "2026-07-09")
        self.assertAlmostEqual(day09["stocks"][0]["surgePct"], 5.0, places=1)

    # ---- date helpers ----

    def test_date_key_formats_yyyymmdd_to_iso(self):
        client = types.SimpleNamespace()
        fake_mod = _make_tickflow_module(client)
        with patch.dict("os.environ", {}, clear=True), patch.dict("sys.modules", {"tickflow": fake_mod}):
            provider = TickFlowProvider()
            self.assertEqual(provider._date_key("20260709"), "2026-07-09")
            self.assertEqual(provider._date_key("2026-07-09"), "2026-07-09")
            self.assertEqual(provider._date_key(None), "")


if __name__ == "__main__":
    unittest.main()

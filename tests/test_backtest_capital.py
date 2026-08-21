from __future__ import annotations

import unittest
from pathlib import Path

from server.engine.rules import backtest


ROOT = Path(__file__).resolve().parents[1]


class BacktestCapitalTest(unittest.TestCase):
    def test_engine_preserves_initial_capital_in_result(self):
        result = backtest({}, [], "资金参数测试", "2025-01-01 ~ 2025-12-31", 250000)

        self.assertEqual(result["capital"], 250000)
        self.assertEqual(result["details"]["summary"]["capital"], 250000)

    def test_frontend_sends_capital_and_shows_it_in_details(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("capital: Number(draft.capital)", html)
        self.assertIn("}, 8000)", html)
        self.assertIn("const controller = new AbortController();", html)
        self.assertIn("runBacktest(draft.config, draft.name.trim(), draft.range, draft.capital)", html)
        self.assertIn("初始资金：¥${Number(bt.capital || details.summary.capital || 100000)", html)
        self.assertNotIn("[ 图表占位：此处渲染 ECharts 净值曲线与基准对比图 ]", html)


if __name__ == "__main__":
    unittest.main()

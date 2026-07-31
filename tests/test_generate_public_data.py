from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts.generate_public_data import generate_public_data


class GeneratePublicDataTest(unittest.TestCase):
    def test_generate_mock_close_scan_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            now = datetime(2026, 7, 9, 16, 35, tzinfo=ZoneInfo("Asia/Shanghai"))

            result = generate_public_data(output_dir=output_dir, provider_name="mock", now=now)

            latest_path = output_dir / "latest-scan.json"
            status_path = output_dir / "run-status.json"
            market_path = output_dir / "market-snapshot.json"
            history_path = output_dir / "history" / f"{result['tradeDate']}.json"

            self.assertTrue(latest_path.exists())
            self.assertTrue(status_path.exists())
            self.assertTrue(market_path.exists())
            self.assertTrue(history_path.exists())

            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            status = json.loads(status_path.read_text(encoding="utf-8"))

            self.assertTrue(latest["ok"])
            self.assertEqual(latest["mode"], "close-scan")
            self.assertEqual(latest["provider"], "mock")
            self.assertEqual(latest["runAt"], "2026-07-09 16:35:00")
            self.assertIn("strategyName", latest)
            self.assertIn("funnel", latest)
            self.assertIn("details", latest)
            self.assertIsInstance(latest["signals"], list)
            self.assertGreaterEqual(len(latest["signals"]), 3)

            self.assertTrue(status["ok"])
            self.assertEqual(status["latestFile"], "public-data/latest-scan.json")
            self.assertEqual(status["historyFile"], f"public-data/history/{result['tradeDate']}.json")

    def test_auto_uses_baostock_daily_history_fallback_when_tickflow_and_akshare_market_fetch_fail(self):
        class FailingTickFlowProvider:
            name = "tickflow"

            def today_market(self):
                raise RuntimeError("tf down")

        class FailingAkshareProvider:
            name = "akshare"

            def today_market(self):
                raise RuntimeError("ak down")

        class FallbackProvider:
            name = "baostock"

            def today_market(self):
                return {
                    "date": "2026-07-08",
                    "indexAboveMa": True,
                    "limitDownCount": 3,
                    "crashDays": 0,
                    "marketDrop": 1.6,
                    "marketVolRatio": 1.8,
                    "ma20Up": True,
                    "time": "15:01",
                    "stocks": [],
                }

        fake_baostock_module = types.ModuleType("server.providers.baostock_provider")
        fake_baostock_module.BaostockProvider = FallbackProvider

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            with patch(
                "server.providers.tickflow_provider.TickFlowProvider", FailingTickFlowProvider
            ), patch("server.providers.akshare_provider.AkshareProvider", FailingAkshareProvider), patch.dict(
                sys.modules, {"server.providers.baostock_provider": fake_baostock_module}
            ):
                result = generate_public_data(output_dir=output_dir, provider_name="auto")

            latest = json.loads((output_dir / "latest-scan.json").read_text(encoding="utf-8"))

            self.assertEqual(result["provider"], "baostock")
            self.assertEqual(result["tradeDate"], "2026-07-08")
            self.assertEqual(latest["provider"], "baostock")
            self.assertTrue(any("akshare 行情获取失败" in item for item in latest["warnings"]))
            self.assertFalse(any("样本数据" in item for item in latest["warnings"]))


if __name__ == "__main__":
    unittest.main()

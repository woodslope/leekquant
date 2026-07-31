from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

from server.providers.chain import build_providers, call_provider_method, provider_config_status


class ProviderChainTest(unittest.TestCase):
    def test_auto_provider_chain_uses_baostock_before_sina_for_daily_history(self):
        class FailingTickFlowProvider:
            def __init__(self):
                raise RuntimeError("tf init down")

        class FailingAkshareProvider:
            def __init__(self):
                raise RuntimeError("ak init down")

        class BaostockProvider:
            name = "baostock"

        class SinaProvider:
            name = "sina"

        fake_baostock_module = types.ModuleType("server.providers.baostock_provider")
        fake_baostock_module.BaostockProvider = BaostockProvider
        fake_sina_module = types.ModuleType("server.providers.sina_provider")
        fake_sina_module.SinaProvider = SinaProvider

        with patch(
            "server.providers.tickflow_provider.TickFlowProvider", FailingTickFlowProvider
        ), patch("server.providers.akshare_provider.AkshareProvider", FailingAkshareProvider), patch.dict(
            sys.modules,
            {
                "server.providers.baostock_provider": fake_baostock_module,
                "server.providers.sina_provider": fake_sina_module,
            },
        ):
            providers, warnings = build_providers("auto")

        self.assertEqual([provider.name for provider in providers], ["baostock", "sina", "mock"])
        self.assertTrue(any("AKShare 初始化失败" in item for item in warnings))

    def test_call_provider_method_uses_next_real_provider_before_mock(self):
        class FailingProvider:
            name = "akshare"

            def today_market(self):
                raise RuntimeError("ak market down")

        class SinaProvider:
            name = "sina"

            def today_market(self):
                return {"date": "2026-07-08", "stocks": []}

        warnings: list[str] = []

        provider, market = call_provider_method(
            [FailingProvider(), SinaProvider()],
            warnings,
            "today_market",
            action_label="行情获取",
        )

        self.assertEqual(provider.name, "sina")
        self.assertEqual(market["date"], "2026-07-08")
        self.assertTrue(any("akshare 行情获取失败，已尝试备用免费源" in item for item in warnings))
        self.assertFalse(any("样本数据" in item for item in warnings))

    def test_auto_provider_order_can_be_overridden_by_environment(self):
        class SinaProvider:
            name = "sina"

        class AkshareProvider:
            name = "akshare"

        fake_sina_module = types.ModuleType("server.providers.sina_provider")
        fake_sina_module.SinaProvider = SinaProvider
        fake_akshare_module = types.ModuleType("server.providers.akshare_provider")
        fake_akshare_module.AkshareProvider = AkshareProvider

        with patch.dict("os.environ", {"LEEK_PROVIDER_ORDER": "sina,akshare,mock"}), patch.dict(
            sys.modules,
            {
                "server.providers.sina_provider": fake_sina_module,
                "server.providers.akshare_provider": fake_akshare_module,
            },
        ):
            providers, warnings = build_providers("auto")

        self.assertEqual([provider.name for provider in providers], ["sina", "akshare", "mock"])
        self.assertEqual(warnings, [])

    def test_default_auto_provider_chain_includes_baostock_before_mock(self):
        class TickFlowProvider:
            name = "tickflow"

        class AkshareProvider:
            name = "akshare"

        class SinaProvider:
            name = "sina"

        class BaostockProvider:
            name = "baostock"

        fake_tickflow_module = types.ModuleType("server.providers.tickflow_provider")
        fake_tickflow_module.TickFlowProvider = TickFlowProvider
        fake_akshare_module = types.ModuleType("server.providers.akshare_provider")
        fake_akshare_module.AkshareProvider = AkshareProvider
        fake_sina_module = types.ModuleType("server.providers.sina_provider")
        fake_sina_module.SinaProvider = SinaProvider
        fake_baostock_module = types.ModuleType("server.providers.baostock_provider")
        fake_baostock_module.BaostockProvider = BaostockProvider

        with patch.dict("os.environ", {}, clear=True), patch.dict(
            sys.modules,
            {
                "server.providers.tickflow_provider": fake_tickflow_module,
                "server.providers.akshare_provider": fake_akshare_module,
                "server.providers.sina_provider": fake_sina_module,
                "server.providers.baostock_provider": fake_baostock_module,
            },
        ):
            providers, warnings = build_providers("auto")

        self.assertEqual([provider.name for provider in providers], ["tickflow", "akshare", "baostock", "sina", "mock"])
        self.assertEqual(warnings, [])

    def test_tushare_can_be_enabled_by_provider_order_and_token(self):
        class TushareProvider:
            name = "tushare"

        class SinaProvider:
            name = "sina"

        fake_tushare_module = types.ModuleType("server.providers.tushare_provider")
        fake_tushare_module.TushareProvider = TushareProvider
        fake_sina_module = types.ModuleType("server.providers.sina_provider")
        fake_sina_module.SinaProvider = SinaProvider

        with patch.dict("os.environ", {"LEEK_PROVIDER_ORDER": "tushare,sina,mock", "TUSHARE_TOKEN": "secret"}), patch.dict(
            sys.modules,
            {
                "server.providers.tushare_provider": fake_tushare_module,
                "server.providers.sina_provider": fake_sina_module,
            },
        ):
            providers, warnings = build_providers("auto")

        self.assertEqual([provider.name for provider in providers], ["tushare", "sina", "mock"])
        self.assertEqual(warnings, [])

    def test_provider_config_status_exposes_order_and_token_presence_without_token_value(self):
        with patch.dict("os.environ", {"LEEK_PROVIDER_ORDER": "tushare,akshare,mock", "TUSHARE_TOKEN": "secret"}):
            status = provider_config_status("auto")

        self.assertEqual(status["providerOrder"], ["tushare", "akshare", "mock"])
        self.assertEqual(status["configured"], {"tushare": True, "tickflow": False})
        self.assertNotIn("secret", str(status))


if __name__ == "__main__":
    unittest.main()

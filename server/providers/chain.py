from __future__ import annotations

from typing import Any

from server.config import get_env, get_provider_order
from server.providers.mock_provider import MockProvider


AUTO_PROVIDER_NAMES = ("akshare", "sina", "baostock", "tickflow")
OPTIONAL_PROVIDER_NAMES = ("tushare",)
REAL_PROVIDER_NAMES = {*AUTO_PROVIDER_NAMES, *OPTIONAL_PROVIDER_NAMES}


def build_providers(provider_name: str = "auto"):
    warnings: list[str] = []
    if provider_name == "mock":
        return [MockProvider()], warnings
    if provider_name not in {"auto", *REAL_PROVIDER_NAMES}:
        warnings.append(f"未知数据源 {provider_name}，已降级到样本数据")
        return [MockProvider()], warnings

    names = get_provider_order() if provider_name == "auto" else (provider_name,)
    providers = []
    for index, name in enumerate(names):
        if name == "mock":
            continue
        provider = _try_create_provider(name, warnings, allow_next=provider_name == "auto" or index < len(names) - 1)
        if provider is not None:
            providers.append(provider)
    providers.append(MockProvider())
    return providers, warnings


def build_provider(provider_name: str = "auto"):
    providers, warnings = build_providers(provider_name)
    return providers[0], warnings


def provider_config_status(provider_name: str = "auto") -> dict:
    order = get_provider_order() if provider_name == "auto" else (provider_name,)
    return {
        "providerOrder": list(order),
        "configured": {
            "tushare": bool(get_env("TUSHARE_TOKEN")),
            "tickflow": bool(get_env("TICKFLOW_API_KEY")),
        },
    }


def call_provider_method(
    providers,
    warnings: list[str],
    method_name: str,
    *args: Any,
    action_label: str = "数据获取",
    **kwargs: Any,
):
    provider_list = providers if isinstance(providers, list) else [providers]
    for index, provider in enumerate(provider_list):
        try:
            return provider, getattr(provider, method_name)(*args, **kwargs)
        except Exception as exc:
            has_next_real_provider = any(item.name != "mock" for item in provider_list[index + 1 :])
            if provider.name == "mock":
                raise
            if has_next_real_provider:
                warnings.append(f"{provider.name} {action_label}失败，已尝试备用免费源: {exc}")
            else:
                warnings.append(f"{provider.name} {action_label}失败，已降级到样本数据: {exc}")

    fallback = MockProvider()
    return fallback, getattr(fallback, method_name)(*args, **kwargs)


def _try_create_provider(name: str, warnings: list[str], allow_next: bool):
    try:
        if name == "tickflow":
            from server.providers.tickflow_provider import TickFlowProvider

            return TickFlowProvider()
        if name == "akshare":
            from server.providers.akshare_provider import AkshareProvider

            return AkshareProvider()
        if name == "tushare":
            from server.providers.tushare_provider import TushareProvider

            return TushareProvider()
        if name == "sina":
            from server.providers.sina_provider import SinaProvider

            return SinaProvider()
        if name == "baostock":
            from server.providers.baostock_provider import BaostockProvider

            return BaostockProvider()
    except Exception as exc:
        display_names = {"tickflow": "TickFlow", "akshare": "AKShare", "tushare": "Tushare", "sina": "新浪", "baostock": "BaoStock"}
        display_name = display_names.get(name, name)
        if allow_next:
            warnings.append(f"{display_name} 初始化失败，已尝试备用免费源: {exc}")
        else:
            warnings.append(f"{display_name} 初始化失败，已降级到样本数据: {exc}")
    return None

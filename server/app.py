from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.engine.rules import DEFAULT_PARAMS, backtest, scan  # noqa: E402
from server.providers.chain import build_provider, build_providers, call_provider_method, provider_config_status  # noqa: E402
from server.providers.mock_provider import MockProvider  # noqa: E402
from server.storage import CacheStore  # noqa: E402


STORE = CacheStore()


def get_provider():
    return build_provider("auto")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            provider, warnings = get_provider()
            return self.json({"ok": True, "provider": provider.name, "warnings": warnings, "cache": STORE.cache_info(), "defaultParams": DEFAULT_PARAMS, **provider_config_status("auto")})
        if parsed.path == "/api/a/market/snapshot":
            return self.handle_market_snapshot()
        if parsed.path.startswith("/api/a/stocks/") and parsed.path.endswith("/daily"):
            return self.handle_stock_daily(parsed)
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/a/scan":
            return self.handle_scan()
        if parsed.path == "/api/a/backtest":
            return self.handle_backtest()
        self.send_error(404, "Not Found")

    def handle_market_snapshot(self):
        providers, warnings = build_providers("auto")
        cached = STORE.get_market_snapshot_record(ttl_minutes=5)
        if cached:
            warnings.extend(cached["warnings"])
            return self.json(
                {
                    "ok": True,
                    "provider": cached["provider"],
                    "warnings": warnings,
                    "market": cached["market"],
                    "cacheHit": True,
                    "cache": STORE.cache_info(),
                }
            )
        try:
            provider, market = call_provider_method(providers, warnings, "today_market", action_label="行情获取")
            STORE.save_market_snapshot(market, provider.name, warnings=warnings)
            return self.json({"ok": True, "provider": provider.name, "warnings": warnings, "market": market, "cache": STORE.cache_info()})
        except Exception as exc:
            fallback = MockProvider()
            warnings.append(str(exc))
            market = fallback.today_market()
            STORE.save_market_snapshot(market, fallback.name, warnings=warnings)
            return self.json({"ok": True, "provider": fallback.name, "warnings": warnings, "market": market, "cache": STORE.cache_info()})

    def handle_scan(self):
        payload = self.read_json()
        providers, warnings = build_providers("auto")
        provider_name = providers[0].name
        try:
            cached = STORE.get_market_snapshot_record(ttl_minutes=5)
            if cached:
                market = cached["market"]
                provider_name = cached["provider"]
                warnings.extend(cached["warnings"])
            else:
                provider, market = call_provider_method(providers, warnings, "today_market", action_label="行情获取")
                provider_name = provider.name
                STORE.save_market_snapshot(market, provider_name, warnings=warnings)
        except Exception as exc:
            fallback = MockProvider()
            warnings.append(str(exc))
            provider_name = fallback.name
            market = fallback.today_market()
            STORE.save_market_snapshot(market, provider_name, warnings=warnings)
        result = scan(
            payload.get("config") or {},
            market,
            executed_ids=payload.get("executedSignalIds") or [],
            position_ids=payload.get("positionIds") or [],
        )
        return self.json({"ok": True, "provider": provider_name, "warnings": warnings, **result})

    def handle_backtest(self):
        payload = self.read_json()
        query = parse_qs(urlparse(self.path).query)
        providers, warnings = build_providers("auto")
        start = payload.get("start") or query.get("start", [None])[0]
        end = payload.get("end") or query.get("end", [None])[0]
        try:
            provider, markets = call_provider_method(
                providers,
                warnings,
                "historical_markets",
                start=start,
                end=end,
                action_label="历史行情获取",
            )
        except Exception as exc:
            fallback = MockProvider()
            warnings.append(str(exc))
            provider = fallback
            markets = fallback.historical_markets(start=start, end=end)
        result = backtest(payload.get("config") or {}, markets, payload.get("name") or "未命名回测", payload.get("range") or f"{start or ''} ~ {end or ''}")
        return self.json({"ok": True, "provider": provider.name, "warnings": warnings, "backtest": result})

    def handle_stock_daily(self, parsed):
        parts = parsed.path.strip("/").split("/")
        code = parts[3] if len(parts) >= 5 else ""
        query = parse_qs(parsed.query)
        start = query.get("start", ["20200101"])[0]
        end = query.get("end", ["20991231"])[0]
        providers, warnings = build_providers("auto")
        provider = providers[0]

        cached_rows = STORE.get_daily_range(code, self.date_key(start), self.date_key(end))
        _, max_date = STORE.get_daily_bounds(code)
        fetch_start = start
        if max_date:
            next_day = (datetime.strptime(max_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
            if next_day >= start:
                fetch_start = next_day

        fetched_rows = []
        try:
            provider, fetched_rows = call_provider_method(
                providers,
                warnings,
                "stock_daily",
                code,
                fetch_start,
                end,
                action_label="个股日线获取",
            )
            STORE.save_daily(code, fetched_rows, provider.name)
        except Exception as exc:
            warnings.append(str(exc))
            fallback = MockProvider()
            provider = fallback
            fetched_rows = fallback.stock_daily(code, fetch_start, end)
            STORE.save_daily(code, fetched_rows, fallback.name)

        rows = STORE.get_daily_range(code, self.date_key(start), self.date_key(end))
        return self.json({
            "ok": True,
            "provider": provider.name,
            "warnings": warnings,
            "code": code,
            "start": start,
            "end": end,
            "cacheHitRows": len(cached_rows),
            "fetchedRows": len(fetched_rows),
            "rows": rows,
            "cache": STORE.cache_info(),
        })

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def date_key(value: str) -> str:
        value = value or ""
        if len(value) == 8 and value.isdigit():
            return f"{value[:4]}-{value[4:6]}-{value[6:]}"
        return value


def main():
    port = 8765
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"LeekQuant server: http://127.0.0.1:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()

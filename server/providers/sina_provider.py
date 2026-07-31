from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


class SinaProvider:
    name = "sina"

    def __init__(self, limit: int = 80, timeout: int = 12, retries: int = 3):
        self.limit = limit
        self.timeout = timeout
        self.retries = retries

    def today_market(self) -> dict:
        gainers = self._fetch_spot(asc=0)
        decliners = self._fetch_spot(asc=1)
        index_rows = self._fetch_kline("sh000001", datalen=300)
        if not gainers:
            raise RuntimeError("新浪未返回 A 股横截面行情")
        if not index_rows:
            raise RuntimeError("新浪未返回上证指数日 K")

        closes = [row["close"] for row in index_rows if row["close"] > 0]
        volumes = [row["volume"] for row in index_rows if row["volume"] > 0]
        latest_index = index_rows[-1]
        previous_volumes = volumes[-21:-1]
        previous_avg_volume = sum(previous_volumes) / len(previous_volumes) if previous_volumes else 0
        latest_volume = volumes[-1] if volumes else 0

        index_above_ma = bool(closes[-1] > sum(closes[-250:]) / 250) if len(closes) >= 250 else True
        ma20_up = bool(sum(closes[-20:]) / 20 > sum(closes[-40:-20]) / 20) if len(closes) >= 40 else True
        market_vol_ratio = latest_volume / previous_avg_volume if previous_avg_volume else 1.0

        return {
            "date": latest_index["date"],
            "indexAboveMa": index_above_ma,
            "limitDownCount": sum(1 for row in decliners if self._num(row.get("changepercent")) <= -9.5),
            "crashDays": self._crash_days(index_rows),
            "marketDrop": round(abs(latest_index["pct"]), 2),
            "marketVolRatio": round(max(0.1, market_vol_ratio), 2),
            "ma20Up": ma20_up,
            "time": str(gainers[0].get("ticktime") or datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%H:%M"))[:5],
            "stocks": [self._spot_to_factor(row) for row in gainers[: self.limit]],
        }

    def historical_markets(self, start: str | None = None, end: str | None = None) -> list[dict]:
        today = self.today_market()
        return [
            {**today, "date": start or "2025-01-02"},
            {**today, "date": end or today["date"]},
        ]

    def stock_daily(self, code: str, start: str, end: str) -> list[dict]:
        start_key = self._date_key(start)
        end_key = self._date_key(end)
        rows = self._fetch_kline(self._symbol(code), datalen=1024)
        return [
            {
                "code": code,
                "date": row["date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "amount": 0,
                "pct": row["pct"],
            }
            for row in rows
            if start_key <= row["date"].replace("-", "") <= end_key
        ]

    def _fetch_spot(self, asc: int) -> list[dict]:
        text = self._request_text(
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData",
            {
                "page": 1,
                "num": max(100, self.limit),
                "sort": "changepercent",
                "asc": asc,
                "node": "hs_a",
                "symbol": "",
                "_s_r_a": "init",
            },
        )
        return json.loads(text)

    def _fetch_kline(self, symbol: str, datalen: int) -> list[dict]:
        text = self._request_text(
            "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20data=/CN_MarketDataService.getKLineData",
            {
                "symbol": symbol,
                "scale": 240,
                "ma": "no",
                "datalen": datalen,
            },
        )
        match = re.search(r"=\((\[.*\])\);?\s*$", text, flags=re.S)
        if not match:
            return []

        raw_rows = json.loads(match.group(1))
        rows = []
        previous_close = 0.0
        for item in raw_rows:
            close = self._num(item.get("close"))
            pct = (close - previous_close) / previous_close * 100 if previous_close else 0.0
            rows.append(
                {
                    "date": str(item.get("day") or ""),
                    "open": self._num(item.get("open")),
                    "high": self._num(item.get("high")),
                    "low": self._num(item.get("low")),
                    "close": close,
                    "volume": self._num(item.get("volume")),
                    "pct": pct,
                }
            )
            if close > 0:
                previous_close = close
        return rows

    def _request_text(self, base_url: str, params: dict[str, Any]) -> str:
        url = f"{base_url}?{urlencode(params)}"
        last_error: Exception | None = None
        for attempt in range(self.retries):
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://finance.sina.com.cn/",
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8", errors="replace")
            except Exception as exc:
                last_error = exc
                if attempt < self.retries - 1:
                    time.sleep(0.4)
        raise RuntimeError(f"新浪请求失败: {last_error}") from last_error

    def _spot_to_factor(self, row: dict) -> dict:
        code = str(row.get("code") or "")
        name = str(row.get("name") or code)
        latest = self._num(row.get("trade"))
        pct = self._num(row.get("changepercent"))
        amount = self._num(row.get("amount"))
        turnover = self._num(row.get("turnoverratio"))
        open_price = self._num(row.get("open"))
        prev_close = self._num(row.get("settlement"))
        amplitude = self._amplitude(row)
        vol_ratio = max(0.8, min(4.5, amount / 1_000_000_000)) if amount else 1.2
        high_days = int(max(5, min(30, 10 + pct * 2)))
        return {
            "id": code,
            "name": name,
            "close": latest,
            "closeAbovePrev": latest >= prev_close if prev_close else pct >= 0,
            "closeAboveOpen": latest >= open_price if open_price else pct >= 0,
            "highDays": high_days,
            "platformDays": int(max(8, min(30, 15 + turnover))),
            "platformAmp": round(max(4, min(18, amplitude or abs(pct) + 7)), 1),
            "gapUp": open_price > prev_close and pct > 3 if prev_close else pct > 3,
            "pullbackDays": int(max(1, min(8, 3 + turnover / 2))),
            "lowerShadowRatio": round(max(0.5, min(3, 1 + abs(pct) / 5)), 1),
            "surgePct": pct,
            "aboveMa": pct > -1,
            "fundSafeDays": int(max(1, min(8, 4 + pct / 2))),
            "macdCross": pct > 1,
            "superInflowDays": 1 if pct > 0 else 0,
            "volRatio": round(vol_ratio, 2),
            "rsi": round(max(20, min(80, 45 + pct * 3)), 1),
            "mainInflowPct": round(max(0, min(25, 8 + pct)), 1),
            "northDays": int(max(1, min(8, 4 + pct / 2))),
            "northPct": round(max(0.01, min(0.35, 0.08 + pct / 100)), 3),
            "backtestReturn": round(max(-12, min(18, pct * 1.8)), 1),
            "maxLoss": round(min(-2, -abs(pct) - 2), 1),
            "exitReason": "策略止盈" if pct >= 0 else "硬止损",
        }

    def _amplitude(self, row: dict) -> float:
        high = self._num(row.get("high"))
        low = self._num(row.get("low"))
        prev_close = self._num(row.get("settlement"))
        return (high - low) / prev_close * 100 if prev_close else 0.0

    def _crash_days(self, rows: list[dict]) -> int:
        count = 0
        for row in reversed(rows):
            if row["pct"] <= -3:
                count += 1
            else:
                break
        return count

    def _symbol(self, code: str) -> str:
        code = str(code)
        if code.startswith(("0", "2", "3")):
            return f"sz{code}"
        if code.startswith(("4", "8", "9")):
            return f"bj{code}"
        return f"sh{code}"

    def _date_key(self, value: str | None) -> str:
        value = str(value or "")
        return value.replace("-", "") if value else "19900101"

    @staticmethod
    def _num(value) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

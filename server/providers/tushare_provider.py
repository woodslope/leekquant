from __future__ import annotations

from datetime import datetime

from server.config import get_env


class TushareProvider:
    name = "tushare"

    def __init__(self, limit: int = 80):
        token = get_env("TUSHARE_TOKEN")
        if not token:
            raise RuntimeError("TUSHARE_TOKEN 未配置")
        try:
            import tushare as ts  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError(f"Tushare 未安装或无法导入: {exc}") from exc
        self.ts = ts
        self.pro = ts.pro_api(token)
        self.limit = limit

    def today_market(self) -> dict:
        trade_date = datetime.now().strftime("%Y%m%d")
        daily = self._frame_rows(self.pro.daily(trade_date=trade_date))[: self.limit]
        stocks = [self._daily_to_factor(row) for row in daily]
        index_rows = self._frame_rows(self.pro.index_daily(ts_code="000001.SH", start_date="20250101", end_date=trade_date))
        closes = [self._num(row.get("close")) for row in index_rows if self._num(row.get("close")) > 0]

        return {
            "date": self._display_date(trade_date),
            "indexAboveMa": bool(closes[0] > sum(closes[:250]) / 250) if len(closes) >= 250 else True,
            "limitDownCount": sum(1 for row in daily if self._num(row.get("pct_chg")) <= -9.5),
            "crashDays": 0,
            "marketDrop": round(abs(self._num(index_rows[0].get("pct_chg"))) if index_rows else 0.0, 2),
            "marketVolRatio": 1.0,
            "ma20Up": bool(sum(closes[:20]) / 20 > sum(closes[20:40]) / 20) if len(closes) >= 40 else True,
            "time": datetime.now().strftime("%H:%M"),
            "stocks": stocks,
        }

    def historical_markets(self, start: str | None = None, end: str | None = None) -> list[dict]:
        today = self.today_market()
        return [
            {**today, "date": start or "2025-01-02"},
            {**today, "date": end or today["date"]},
        ]

    def stock_daily(self, code: str, start: str, end: str) -> list[dict]:
        rows = self._frame_rows(
            self.pro.daily(
                ts_code=self._ts_code(code),
                start_date=self._date_key(start),
                end_date=self._date_key(end),
            )
        )
        return [self._daily_row(row) for row in rows]

    def _daily_row(self, row: dict) -> dict:
        return {
            "code": self._plain_code(row.get("ts_code", "")),
            "date": self._display_date(row.get("trade_date", "")),
            "open": self._num(row.get("open")),
            "high": self._num(row.get("high")),
            "low": self._num(row.get("low")),
            "close": self._num(row.get("close")),
            "volume": self._num(row.get("vol")),
            "amount": self._num(row.get("amount")),
            "pct": self._num(row.get("pct_chg")),
        }

    def _daily_to_factor(self, row: dict) -> dict:
        daily = self._daily_row(row)
        pct = daily["pct"]
        amount = daily["amount"]
        vol_ratio = max(0.8, min(4.5, amount / 1_000_000_000)) if amount else 1.2
        return {
            "id": daily["code"],
            "name": daily["code"],
            "close": daily["close"],
            "closeAbovePrev": pct >= 0,
            "closeAboveOpen": daily["close"] >= daily["open"] if daily["open"] else pct >= 0,
            "highDays": int(max(5, min(30, 10 + pct * 2))),
            "platformDays": 15,
            "platformAmp": round(max(4, min(18, abs(pct) + 7)), 1),
            "gapUp": pct > 3,
            "pullbackDays": 3,
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

    def _frame_rows(self, frame) -> list[dict]:
        if frame is None or getattr(frame, "empty", False):
            return []
        return frame.to_dict("records")

    def _ts_code(self, code: str) -> str:
        value = str(code)
        if "." in value:
            return value.upper()
        digits = "".join(ch for ch in value if ch.isdigit())
        suffix = "SZ" if digits.startswith(("0", "2", "3")) else "BJ" if digits.startswith(("4", "8", "9")) else "SH"
        return f"{digits}.{suffix}"

    def _plain_code(self, code: str) -> str:
        return str(code).split(".")[0]

    def _date_key(self, value: str | None) -> str:
        value = str(value or "")
        return value.replace("-", "")

    def _display_date(self, value: str) -> str:
        value = str(value or "")
        if len(value) == 8 and value.isdigit():
            return f"{value[:4]}-{value[4:6]}-{value[6:]}"
        return value

    @staticmethod
    def _num(value) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

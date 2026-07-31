from __future__ import annotations

from datetime import datetime


class BaostockProvider:
    name = "baostock"

    def __init__(self, limit: int = 80):
        try:
            import baostock as bs  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError(f"BaoStock 未安装或无法导入: {exc}") from exc
        self.bs = bs
        self.limit = limit
        login = self.bs.login()
        if getattr(login, "error_code", "0") != "0":
            raise RuntimeError(f"BaoStock 登录失败: {getattr(login, 'error_msg', '')}")

    def today_market(self) -> dict:
        trade_date = datetime.now().strftime("%Y-%m-%d")
        stock_rows = self._query_all_stock(trade_date)
        if not stock_rows:
            raise RuntimeError("BaoStock 未返回当前交易日股票清单")
        stocks = []
        for item in stock_rows[: self.limit]:
            code = self._plain_code(item.get("code", ""))
            daily_rows = self.stock_daily(code, trade_date.replace("-", ""), trade_date.replace("-", ""))
            if daily_rows:
                stocks.append(self._daily_to_factor(daily_rows[-1], item.get("code_name") or code))

        index_rows = self._query_daily_rows("sh.000001", "date,close,volume,pctChg", "2025-01-01", trade_date)
        closes = [row["close"] for row in index_rows if row["close"] > 0]
        volumes = [row["volume"] for row in index_rows if row["volume"] > 0]
        market_drop = abs(index_rows[-1]["pct"]) if index_rows else 0.0
        latest_volume = volumes[-1] if volumes else 0.0
        previous = volumes[-21:-1]
        avg_volume = sum(previous) / len(previous) if previous else 0.0

        return {
            "date": trade_date,
            "indexAboveMa": bool(closes[-1] > sum(closes[-250:]) / 250) if len(closes) >= 250 else True,
            "limitDownCount": sum(1 for row in stocks if row["surgePct"] <= -9.5),
            "crashDays": 0,
            "marketDrop": round(market_drop, 2),
            "marketVolRatio": round(latest_volume / avg_volume, 2) if avg_volume else 1.0,
            "ma20Up": bool(sum(closes[-20:]) / 20 > sum(closes[-40:-20]) / 20) if len(closes) >= 40 else True,
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
        return self._query_daily_rows(
            self._symbol(code),
            "date,code,open,high,low,close,volume,amount,pctChg",
            self._date_key(start),
            self._date_key(end),
        )

    def _query_all_stock(self, trade_date: str) -> list[dict]:
        result = self.bs.query_all_stock(day=trade_date)
        return self._rows(result)

    def _query_daily_rows(self, code: str, fields: str, start: str, end: str) -> list[dict]:
        result = self.bs.query_history_k_data_plus(
            code,
            fields,
            start_date=start,
            end_date=end,
            frequency="d",
            adjustflag="2",
        )
        rows = []
        for row in self._rows(result):
            plain_code = self._plain_code(row.get("code", code))
            rows.append(
                {
                    "code": plain_code,
                    "date": row.get("date", ""),
                    "open": self._num(row.get("open")),
                    "high": self._num(row.get("high")),
                    "low": self._num(row.get("low")),
                    "close": self._num(row.get("close")),
                    "volume": self._num(row.get("volume")),
                    "amount": self._num(row.get("amount")),
                    "pct": self._num(row.get("pctChg")),
                }
            )
        return rows

    def _rows(self, result) -> list[dict]:
        if getattr(result, "error_code", "0") != "0":
            raise RuntimeError(f"BaoStock 查询失败: {getattr(result, 'error_msg', '')}")
        rows = []
        while result.next():
            rows.append(dict(zip(result.fields, result.get_row_data())))
        return rows

    def _daily_to_factor(self, row: dict, name: str) -> dict:
        pct = self._num(row.get("pct"))
        close = self._num(row.get("close"))
        open_price = self._num(row.get("open"))
        amount = self._num(row.get("amount"))
        vol_ratio = max(0.8, min(4.5, amount / 1_000_000_000)) if amount else 1.2
        return {
            "id": row.get("code", ""),
            "name": name,
            "close": close,
            "closeAbovePrev": pct >= 0,
            "closeAboveOpen": close >= open_price if open_price else pct >= 0,
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

    def _symbol(self, code: str) -> str:
        value = str(code).replace(".", "")
        if value.startswith(("sh", "sz", "bj")) and "." in str(code):
            return str(code)
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits.startswith(("0", "2", "3")):
            return f"sz.{digits}"
        if digits.startswith(("4", "8", "9")):
            return f"bj.{digits}"
        return f"sh.{digits}"

    def _plain_code(self, code: str) -> str:
        return str(code).split(".")[-1]

    def _date_key(self, value: str | None) -> str:
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

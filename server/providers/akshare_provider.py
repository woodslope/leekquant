from __future__ import annotations

from datetime import datetime


class AkshareProvider:
    name = "akshare"

    def __init__(self, limit: int = 80):
        try:
            import akshare as ak  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError(f"AKShare 未安装或无法导入: {exc}") from exc
        self.ak = ak
        self.limit = limit

    def today_market(self) -> dict:
        spot = self.ak.stock_zh_a_spot_em()
        index = self.ak.stock_zh_index_daily_em(symbol="sh000001")
        if spot is None or spot.empty:
            raise RuntimeError("AKShare 未返回 A 股实时行情")

        recent_index = index.tail(260).copy()
        close = recent_index["close"].astype(float)
        index_above_ma = bool(close.iloc[-1] > close.tail(250).mean()) if len(close) >= 250 else True
        ma20_up = bool(close.tail(20).mean() > close.tail(40).head(20).mean()) if len(close) >= 40 else True
        market_drop = abs(float(recent_index["close"].pct_change().iloc[-1] or 0) * 100)

        records = spot.head(self.limit).to_dict("records")
        stocks = [self._spot_to_factor(row) for row in records]
        limit_down_count = sum(1 for row in records if self._num(row.get("涨跌幅")) <= -9.5)

        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "indexAboveMa": index_above_ma,
            "limitDownCount": limit_down_count,
            "crashDays": 0,
            "marketDrop": round(market_drop, 2),
            "marketVolRatio": 1.5,
            "ma20Up": ma20_up,
            "time": datetime.now().strftime("%H:%M"),
            "stocks": stocks,
        }

    def historical_markets(self, start: str | None = None, end: str | None = None) -> list[dict]:
        # 免费源回测先用“当前横截面 + 模拟历史日”的方式兜底，避免大量逐股历史请求。
        today = self.today_market()
        return [
            {**today, "date": start or "2025-01-02"},
            {**today, "date": end or today["date"]},
        ]

    def stock_daily(self, code: str, start: str, end: str) -> list[dict]:
        df = self.ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq")
        if df is None or df.empty:
            return []
        rows = []
        for row in df.to_dict("records"):
            date_value = row.get("日期")
            rows.append(
                {
                    "code": code,
                    "date": str(date_value),
                    "open": self._num(row.get("开盘")),
                    "high": self._num(row.get("最高")),
                    "low": self._num(row.get("最低")),
                    "close": self._num(row.get("收盘")),
                    "volume": self._num(row.get("成交量")),
                    "amount": self._num(row.get("成交额")),
                    "pct": self._num(row.get("涨跌幅")),
                }
            )
        return rows

    def _spot_to_factor(self, row: dict) -> dict:
        code = str(row.get("代码") or row.get("code") or "")
        name = str(row.get("名称") or row.get("name") or code)
        pct = self._num(row.get("涨跌幅"))
        turnover = self._num(row.get("换手率"))
        amount = self._num(row.get("成交额"))
        vol_ratio = max(0.8, min(4.5, amount / 1_000_000_000)) if amount else 1.2
        high_days = int(max(5, min(30, 10 + pct * 2)))
        return {
            "id": code,
            "name": name,
            "close": self._num(row.get("最新价")),
            "closeAbovePrev": pct >= 0,
            "closeAboveOpen": self._num(row.get("最新价")) >= self._num(row.get("今开")),
            "highDays": high_days,
            "platformDays": int(max(8, min(30, 15 + turnover))),
            "platformAmp": round(max(4, min(18, abs(pct) + 7)), 1),
            "gapUp": pct > 3,
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

    @staticmethod
    def _num(value) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

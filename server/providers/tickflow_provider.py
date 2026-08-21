from __future__ import annotations

from datetime import datetime

from server.config import get_env

# 默认股票池：覆盖沪深主要流动性标的，约 80 只
# 免费层无法调用 quotes.get(universes=...) 获取全市场快照，因此用预定义列表 + klines.batch 兜底
DEFAULT_SYMBOLS = [
    # 上证50 / 沪深300 权重股
    "600000.SH", "600016.SH", "600028.SH", "600030.SH", "600036.SH",
    "600048.SH", "600050.SH", "600104.SH", "600111.SH", "600150.SH",
    "600196.SH", "600276.SH", "600309.SH", "600406.SH", "600436.SH",
    "600438.SH", "600519.SH", "600570.SH", "600585.SH", "600588.SH",
    "600690.SH", "600809.SH", "600887.SH", "600893.SH", "600900.SH",
    "600919.SH", "601012.SH", "601088.SH", "601111.SH", "601166.SH",
    "601211.SH", "601288.SH", "601318.SH", "601328.SH", "601336.SH",
    "601390.SH", "601398.SH", "601601.SH", "601628.SH", "601668.SH",
    "601688.SH", "601818.SH", "601857.SH", "601888.SH", "601899.SH",
    "601919.SH", "601939.SH", "601985.SH", "601988.SH", "601989.SH",
    "603259.SH", "603288.SH", "603799.SH",
    # 深证主板 / 中小板
    "000001.SZ", "000002.SZ", "000063.SZ", "000100.SZ", "000333.SZ",
    "000338.SZ", "000425.SZ", "000568.SZ", "000625.SZ", "000651.SZ",
    "000661.SZ", "000725.SZ", "000776.SZ", "000858.SZ", "000895.SZ",
    "002007.SZ", "002049.SZ", "002142.SZ", "002230.SZ", "002241.SZ",
    "002271.SZ", "002304.SZ", "002352.SZ", "002415.SZ", "002460.SZ",
    "002475.SZ", "002594.SZ", "002714.SZ", "002916.SZ",
    # 创业板
    "300015.SZ", "300059.SZ", "300124.SZ", "300274.SZ", "300413.SZ",
    "300498.SZ", "300529.SZ", "300750.SZ", "300760.SZ",
    # 科创板
    "688012.SH", "688036.SH", "688111.SH", "688981.SH",
]

INDEX_SYMBOL = "000001.SH"  # 上证指数


class TickFlowProvider:
    name = "tickflow"

    def __init__(self, limit: int = 80):
        api_key = get_env("TICKFLOW_API_KEY")
        try:
            from tickflow import TickFlow  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError(f"TickFlow 未安装或无法导入: {exc}") from exc

        if api_key:
            self.tf = TickFlow(api_key=api_key)
            self._has_paid = True
        else:
            self.tf = TickFlow.free()
            self._has_paid = False

        self.limit = limit
        self._symbols = DEFAULT_SYMBOLS[:limit]

    # ---- Public interface ----

    def today_market(self) -> dict:
        if self._has_paid:
            return self._today_market_paid()
        return self._today_market_free()

    def historical_markets(self, start: str | None = None, end: str | None = None) -> list[dict]:
        """基于 klines.batch 批量获取历史日线，按交易日重建 market 快照列表。

        先拉取指数和全量股票的日线数据，再按交易日分组，逐日计算市场指标（无未来数据），
        返回可用于回测的真实历史行情序列。
        """
        start = start or "2025-01-02"
        end = end or datetime.now().strftime("%Y-%m-%d")

        # 多拉 300 天用于 MA 计算（250 日年线需要历史数据）
        total_days = min(self._estimate_count(start, end) + 300, 10000)
        start_dt = self._date_key(start)
        end_dt = self._date_key(end)

        # 1) 获取指数日线
        try:
            index_df = self.tf.klines.get(INDEX_SYMBOL, period="1d", count=total_days, as_dataframe=True)
        except Exception:
            index_df = None

        # 2) 批量获取全量股票日线
        try:
            dfs = self.tf.klines.batch(self._symbols, period="1d", count=total_days, as_dataframe=True)
        except Exception as exc:
            raise RuntimeError(f"TickFlow 历史日线批量获取失败: {exc}") from exc

        # 3) 按 symbol 分组排序，注入 _prev_close，再按 date 聚合
        symbol_rows: dict[str, list[dict]] = {}
        all_rows_by_date: dict[str, list[dict]] = {}
        for sym, df in dfs.items():
            if df is None or df.empty:
                continue
            rows = sorted(df.to_dict("records"), key=lambda r: str(r.get("trade_date", "")))
            symbol_rows[sym] = rows
            for i, row in enumerate(rows):
                td = str(row.get("trade_date", ""))
                if td < start_dt or td > end_dt:
                    continue
                if i > 0:
                    row["_prev_close"] = rows[i - 1].get("close")
                if td not in all_rows_by_date:
                    all_rows_by_date[td] = []
                all_rows_by_date[td].append(row)

        # 3.5) 预计算每个 symbol 的真实技术指标，注入到对应日期的 row
        from server.engine.indicators import compute_indicators  # noqa: E402

        for sym, rows in symbol_rows.items():
            closes = [self._num(r.get("close")) for r in rows]
            highs = [self._num(r.get("high")) for r in rows]
            lows = [self._num(r.get("low")) for r in rows]
            volumes = [self._num(r.get("volume")) for r in rows]
            amounts = [self._num(r.get("amount")) for r in rows]
            opens = [self._num(r.get("open")) for r in rows]

            # 对每个日期切出 <= 该日期的子序列计算指标（无未来数据）
            for i, row in enumerate(rows):
                td = str(row.get("trade_date", ""))
                if td < start_dt or td > end_dt:
                    continue
                sub_closes = closes[: i + 1]
                sub_highs = highs[: i + 1]
                sub_lows = lows[: i + 1]
                sub_volumes = volumes[: i + 1]
                sub_amounts = amounts[: i + 1]
                sub_opens = opens[: i + 1]

                ind = compute_indicators(sub_closes, sub_highs, sub_lows, sub_volumes, sub_amounts, sub_opens)
                row["_ind"] = ind  # 将真实指标注入 row，后续 _build_factor 会读取

        # 4) 逐日构建 market 快照
        markets: list[dict] = []
        for td in sorted(all_rows_by_date.keys()):
            date_rows = all_rows_by_date[td]
            stocks = [self._klines_to_factor(r) for r in date_rows]
            if not stocks:
                continue
            market = self._build_market_dict(stocks, date_rows, target_date=td, index_df=index_df)
            markets.append(market)

        if not markets:
            # 数据不足时降级到桩实现
            today = self.today_market()
            return [{**today, "date": start}, {**today, "date": end}]

        return markets

    def stock_daily(self, code: str, start: str, end: str) -> list[dict]:
        tf_code = self._to_tickflow(code)
        count = self._estimate_count(start, end)
        try:
            df = self.tf.klines.get(tf_code, period="1d", count=count, as_dataframe=True)
        except Exception as exc:
            raise RuntimeError(f"TickFlow 个股日线获取失败 ({code}): {exc}") from exc

        if df is None or df.empty:
            return []

        start_dt = self._date_key(start)
        end_dt = self._date_key(end)
        rows = []
        for row in df.to_dict("records"):
            trade_date = str(row.get("trade_date", ""))
            if trade_date < start_dt or trade_date > end_dt:
                continue
            # 优先使用 API 返回的涨跌幅字段
            pct = self._num(row.get("pct_chg") or row.get("change_pct") or row.get("pct"))
            rows.append(
                {
                    "code": self._plain_code(row.get("symbol", "")),
                    "date": trade_date,
                    "open": self._num(row.get("open")),
                    "high": self._num(row.get("high")),
                    "low": self._num(row.get("low")),
                    "close": self._num(row.get("close")),
                    "volume": self._num(row.get("volume")),
                    "amount": self._num(row.get("amount")),
                    "pct": pct,
                }
            )

        # API 未返回 pct 时，基于前一日收盘价反推
        for i in range(1, len(rows)):
            if rows[i]["pct"] == 0.0 and rows[i - 1]["close"]:
                rows[i]["pct"] = round((rows[i]["close"] / rows[i - 1]["close"] - 1) * 100, 2)

        return rows

    # ---- Private: market data builders ----

    def _today_market_paid(self) -> dict:
        """付费层：使用 quotes.get 获取全市场实时快照。"""
        try:
            quotes = self.tf.quotes.get(universes=["CN_Equity_A"], as_dataframe=True)
        except Exception as exc:
            raise RuntimeError(f"TickFlow 实时行情获取失败: {exc}") from exc

        if quotes is None or quotes.empty:
            raise RuntimeError("TickFlow 未返回 A 股行情数据")

        records = quotes.head(self.limit).to_dict("records")
        stocks = [self._quotes_to_factor(row) for row in records]
        return self._build_market_dict(stocks, records)

    def _today_market_free(self) -> dict:
        """免费层：使用 klines.batch 获取最近两日日线作为快照兜底（需前一日收盘价计算涨跌幅）。"""
        try:
            dfs = self.tf.klines.batch(self._symbols, period="1d", count=2, as_dataframe=True)
        except Exception as exc:
            raise RuntimeError(f"TickFlow 日线批量获取失败: {exc}") from exc

        stocks = []
        all_rows = []
        for sym, df in dfs.items():
            if df is None or df.empty:
                continue
            row = df.iloc[-1].to_dict()
            # 传入前一日收盘价，用于计算日涨跌幅
            if len(df) >= 2:
                row["_prev_close"] = df.iloc[-2]["close"]
            all_rows.append(row)
            stocks.append(self._klines_to_factor(row))

        if not stocks:
            raise RuntimeError("TickFlow 未返回任何股票日线数据")

        return self._build_market_dict(stocks, all_rows)

    def _build_market_dict(
        self,
        stocks: list[dict],
        raw_rows: list[dict],
        target_date: str | None = None,
        index_df=None,
    ) -> dict:
        """基于股票列表和指数数据构造标准 market dict。

        target_date / index_df 用于历史回测场景：传入指定日期和预拉取的指数日线，
        指标计算仅使用 target_date 及之前的数据（无未来数据）。
        """
        if target_date:
            trade_date = target_date
        else:
            trade_dates = [str(row.get("trade_date", "")) for row in raw_rows if row.get("trade_date")]
            trade_date = max(trade_dates) if trade_dates else datetime.now().strftime("%Y-%m-%d")

        # 历史模式使用传入的 index_df，实时模式现场拉取
        if index_df is None:
            try:
                index_df = self.tf.klines.get(INDEX_SYMBOL, period="1d", count=260, as_dataframe=True)
            except Exception:
                pass

        indicators = self._compute_market_indicators(index_df, trade_date)
        limit_down_count = sum(1 for s in stocks if s.get("surgePct", 0) <= -9.5)

        return {
            "date": trade_date,
            "indexAboveMa": indicators["indexAboveMa"],
            "limitDownCount": limit_down_count,
            "crashDays": 0,
            "marketDrop": round(indicators["marketDrop"], 2),
            "marketVolRatio": indicators["marketVolRatio"],
            "ma20Up": indicators["ma20Up"],
            "time": datetime.now().strftime("%H:%M") if not target_date else "15:00",
            "stocks": stocks,
        }

    @staticmethod
    def _compute_market_indicators(index_df, target_date: str) -> dict:
        """基于指数日线计算 target_date 时刻的市场指标（仅用 <= target_date 的数据）。"""
        defaults = {"indexAboveMa": True, "marketDrop": 0.0, "marketVolRatio": 1.0, "ma20Up": True}
        if index_df is None or getattr(index_df, "empty", False):
            return defaults

        rows = index_df.to_dict("records")
        past = [r for r in rows if str(r.get("trade_date", "")) <= target_date]
        if len(past) < 2:
            return defaults

        closes = [TickFlowProvider._num(r.get("close")) for r in past]
        volumes = [TickFlowProvider._num(r.get("volume")) for r in past]

        index_above_ma = True
        if len(closes) >= 250:
            index_above_ma = closes[-1] > sum(closes[-250:]) / 250

        ma20_up = True
        if len(closes) >= 40:
            ma20_up = sum(closes[-20:]) / 20 > sum(closes[-40:-20]) / 20

        market_drop = 0.0
        if len(closes) >= 2:
            market_drop = abs((closes[-1] / closes[-2] - 1) * 100)

        market_vol_ratio = 1.0
        if len(volumes) >= 21:
            latest_vol = volumes[-1]
            avg_vol = sum(volumes[-21:-1]) / 20
            market_vol_ratio = round(latest_vol / avg_vol, 2) if avg_vol else 1.0

        return {
            "indexAboveMa": bool(index_above_ma),
            "marketDrop": market_drop,
            "marketVolRatio": market_vol_ratio,
            "ma20Up": bool(ma20_up),
        }

    # ---- Private: factor mapping ----

    def _quotes_to_factor(self, row: dict) -> dict:
        """付费层：将 quotes.get 返回的实时行情行映射为标准 factor dict。"""
        code = self._plain_code(str(row.get("symbol", "")))
        name = str(row.get("name") or code)
        close = self._num(row.get("close"))
        open_price = self._num(row.get("open"))
        pre_close = self._num(row.get("pre_close") or row.get("prev_close"))
        pct = self._num(row.get("change_pct") or row.get("pct_chg"))
        if pre_close and not pct:
            pct = round((close / pre_close - 1) * 100, 2) if pre_close else 0.0

        amount = self._num(row.get("amount"))
        turnover = self._num(row.get("turnover") or row.get("turnover_rate"))
        high = self._num(row.get("high"))
        low = self._num(row.get("low"))

        return self._build_factor(code, name, close, open_price, high, low, pct, amount, turnover)

    def _klines_to_factor(self, row: dict) -> dict:
        """免费层：将 klines.get 返回的日线行映射为标准 factor dict。"""
        code = self._plain_code(str(row.get("symbol", "")))
        name = str(row.get("name") or code)
        close = self._num(row.get("close"))
        open_price = self._num(row.get("open"))
        high = self._num(row.get("high"))
        low = self._num(row.get("low"))
        amount = self._num(row.get("amount"))

        # 优先使用 API 返回的涨跌幅，其次用前日收盘价计算，最后用日内 OHLC 兜底
        pct = self._num(row.get("pct_chg") or row.get("change_pct") or row.get("pct"))
        if not pct:
            prev_close = self._num(row.get("_prev_close") or row.get("prev_close"))
            if prev_close:
                pct = round((close / prev_close - 1) * 100, 2)
            elif open_price:
                pct = round((close / open_price - 1) * 100, 2)

        return self._build_factor(code, name, close, open_price, high, low, pct, amount, turnover=0.0, indicators=row.get("_ind"))

    def _build_factor(
        self,
        code: str,
        name: str,
        close: float,
        open_price: float,
        high: float,
        low: float,
        pct: float,
        amount: float,
        turnover: float,
        indicators: dict | None = None,
    ) -> dict:
        """将原始字段统一映射为标准 stock factor dict。

        indicators 为 compute_indicators() 返回的真实指标字典。
        有真实值时优先使用，否则退回 pct 线性近似。
        """
        ind = indicators or {}

        # ---- 真实指标（优先） / 近似值（兜底） ----
        # RSI
        rsi_real = ind.get("rsi")
        if rsi_real is not None:
            rsi = round(rsi_real, 1)
        else:
            rsi = round(max(20, min(80, 45 + pct * 3)), 1)

        # MACD 金叉
        macd_cross = ind.get("macdCross")
        if macd_cross is not None:
            _macd_cross = bool(macd_cross)
        else:
            _macd_cross = pct > 1

        # 站上均线
        above_ma = ind.get("aboveMa")
        if above_ma is not None:
            _above_ma = bool(above_ma)
        else:
            _above_ma = pct > -1

        # 量比
        vol_ratio_real = ind.get("volRatio")
        if vol_ratio_real is not None:
            _vol_ratio = round(vol_ratio_real, 2)
        else:
            _vol_ratio = round(max(0.8, min(4.5, amount / 1_000_000_000)), 2) if amount else 1.2

        # N 日新高
        high_days_real = ind.get("highDays")
        if high_days_real is not None:
            _high_days = int(max(1, min(60, high_days_real)))
        else:
            _high_days = int(max(5, min(30, 10 + pct * 2)))

        # 下影线比率
        lower_shadow_real = ind.get("lowerShadowRatio")
        if lower_shadow_real is not None:
            _lower_shadow = round(lower_shadow_real, 2)
        else:
            body_low = min(close, open_price) if close and open_price else close
            hl_range = (high - low) if high and low else 0.01
            _lower_shadow = max(0.0, (body_low - low) / max(hl_range, 0.01)) if body_low and low else 1.0
            _lower_shadow = round(max(0.5, min(3.0, _lower_shadow + abs(pct) / 5)), 1)

        # ---- 仍为近似值的字段（需要资金流 / 北向等数据） ----
        return {
            "id": code,
            "name": name,
            "close": close,
            "closeAbovePrev": pct >= 0,
            "closeAboveOpen": close >= open_price if open_price else pct >= 0,
            "highDays": _high_days,
            "platformDays": int(max(8, min(30, 15 + turnover))) if turnover else 15,
            "platformAmp": round(max(4, min(18, abs(pct) + 7)), 1),
            "gapUp": pct > 3,
            "pullbackDays": int(max(1, min(8, 3 + turnover / 2))) if turnover else 3,
            "lowerShadowRatio": _lower_shadow,
            "surgePct": pct,
            "aboveMa": _above_ma,
            "fundSafeDays": int(max(1, min(8, 4 + pct / 2))),
            "macdCross": _macd_cross,
            "superInflowDays": 1 if pct > 0 else 0,
            "volRatio": _vol_ratio,
            "rsi": rsi,
            "mainInflowPct": round(max(0, min(25, 8 + pct)), 1),
            "northDays": int(max(1, min(8, 4 + pct / 2))),
            "northPct": round(max(0.01, min(0.35, 0.08 + pct / 100)), 3),
            "backtestReturn": round(max(-12, min(18, pct * 1.8)), 1),
            "maxLoss": round(min(-2, -abs(pct) - 2), 1),
            "exitReason": "策略止盈" if pct >= 0 else "硬止损",
            # 标记指标可信度
            "indicatorConfidence": "real" if indicators else "approximate",
        }

    # ---- Private: code format helpers ----

    def _to_tickflow(self, code: str) -> str:
        """将项目内部代码（如 600000）转为 TickFlow 格式（600000.SH）。"""
        value = str(code)
        if "." in value:
            return value.upper()
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits:
            return value
        # 深圳：000/001/002/003/300/301 开头
        if digits.startswith(("0", "2", "3")):
            return f"{digits}.SZ"
        # 北京：4/8/9 开头
        if digits.startswith(("4", "8", "9")):
            return f"{digits}.BJ"
        # 其余默认上海
        return f"{digits}.SH"

    def _plain_code(self, code: str) -> str:
        """从 TickFlow 格式（600000.SH）提取纯数字代码。"""
        return str(code).split(".")[0]

    # ---- Private: utilities ----

    def _date_key(self, value: str | None) -> str:
        value = str(value or "")
        if len(value) == 8 and value.isdigit():
            return f"{value[:4]}-{value[4:6]}-{value[6:]}"
        return value

    def _estimate_count(self, start: str, end: str) -> int:
        """根据日期范围估算需要的 K 线根数，默认不超过 10000。"""
        try:
            s = self._date_key(start)
            e = self._date_key(end)
            if s and e and s <= e:
                from datetime import timedelta

                sd = datetime.strptime(s, "%Y-%m-%d")
                ed = datetime.strptime(e, "%Y-%m-%d")
                days = (ed - sd).days + 1
                return min(max(days + 100, 100), 10000)
        except Exception:
            pass
        return 10000

    @staticmethod
    def _num(value) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

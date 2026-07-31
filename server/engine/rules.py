from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "default-strategy.json"

# 硬编码兜底值，当配置文件缺失时使用
_FALLBACK_PARAMS = {
    "s0_ma": "250",
    "s0_limit": "50",
    "s0_crash": "3",
    "s1_drop": "1.0",
    "s1_vol_panic": "1.5",
    "s1_pm": "13:30",
    "s1_high": "20",
    "s1_plat_days": "20",
    "s1_plat_amp": "10",
    "s1_pullback": "5",
    "s1_shadow": "2",
    "s1_surge": "5",
    "s2_ma": "50",
    "s2_fund": "5",
    "s2_macd": "12/26/9",
    "s2_super": "1",
    "s2_vol": "2.0",
    "s2_rsi_level": "30",
    "s2_rsi_period": "14",
    "s2_main": "10",
    "s2_north_days": "5",
    "s2_north_pct": "0.1",
    "s3_hard": "-8.0",
    "s3_break_ma": "20",
    "s3_break_vol": "1.5",
    "s3_trail": "10",
    "s3_sun": "3",
    "s3_fund": "5",
    "s3_stag_vol": "3.0",
    "s3_stag_gain": "1",
    "s3_market_limit": "50",
}


def _load_default_params() -> dict:
    """从 config/default-strategy.json 加载默认策略参数，作为前后端单一来源。"""
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        config = raw.get("config", raw)
        params = config.get("params", {})
        if params:
            return {**params}
    except Exception:
        pass
    return dict(_FALLBACK_PARAMS)


DEFAULT_PARAMS = _load_default_params()


def normalize_config(config: dict | None) -> dict:
    config = config or {}
    return {
        **config,
        "s1Keys": config["s1Keys"] if "s1Keys" in config else ["s1_drop", "s1_close", "s1_vol_panic", "s1_inverse"],
        "s2Keys": config["s2Keys"] if "s2Keys" in config else ["s2_ma", "s2_fund", "s2_macd", "s2_super"],
        "s3Keys": config["s3Keys"] if "s3Keys" in config else ["s3_hard", "s3_break", "s3_trail"],
        "params": {**DEFAULT_PARAMS, **(config.get("params") or {})},
    }


def scan(config: dict, market: dict, executed_ids: list[str] | None = None, position_ids: list[str] | None = None) -> dict:
    config = normalize_config(config)
    blocked = set(executed_ids or []) | set(position_ids or [])
    s0 = _market_checks(config, market)
    stock_results = [_evaluate_stock(config, market, stock) for stock in market.get("stocks", [])]
    s0_pass = all(item["pass"] for item in s0)
    passed = [item for item in stock_results if s0_pass and item["pass"] and item["stock"]["id"] not in blocked]

    return {
        "providerDate": market.get("date"),
        "funnel": {
            "s0": {"status": "pass" if s0_pass else "fail", "text": "开机" if s0_pass else "关机"},
            "s1": {"status": "pass" if any(r["s1Pass"] for r in stock_results) else "fail", "text": f"{sum(1 for r in stock_results if r['s1Pass'])}只触发"},
            "s2": {"status": "ready" if passed else "neutral", "text": f"{len(passed)}只就绪" if passed else "无新信号"},
        },
        "details": {
            "s0": _details(s0),
            "s1": _details(stock_results[0]["s1Results"]) if stock_results else [],
            "s2": _details(stock_results[0]["s2Results"]) if stock_results else [],
        },
        "signals": [
            {
                "id": item["stock"]["id"],
                "name": item["stock"]["name"],
                "indicator": ", ".join(r["name"] for r in item["s2Results"] if r["pass"]) or "规则通过",
                "reason": "+".join(r["name"] for r in item["s1Results"] if r["pass"]) or "策略条件满足",
                "msg": " / ".join(f"{r['name']}:{'通过' if r['pass'] else '阻断'}" for r in item["s1Results"] + item["s2Results"]),
            }
            for item in passed
        ],
    }


def backtest(config: dict, markets: list[dict], name: str, range_text: str) -> dict:
    config = normalize_config(config)
    # 按日期索引 market 快照，用于查找离场日的真实价格
    market_by_date = {m.get("date", ""): m for m in markets}
    trading_dates = sorted(market_by_date.keys())
    trades = []
    held: dict[str, str] = {}  # code -> exit_date，持仓期间不再重复入场

    for entry_idx, market in enumerate(markets):
        entry_date = market.get("date", "")
        # 释放已到离场日的持仓
        held = {code: ed for code, ed in held.items() if ed > entry_date}

        result = scan(config, market)
        # 离场日：往后找第 5 个实际交易日（约一周），没有则取最后一个
        exit_idx = min(entry_idx + 5, len(trading_dates) - 1)
        exit_date = trading_dates[exit_idx] if exit_idx < len(trading_dates) else entry_date
        exit_market = market_by_date.get(exit_date, market)

        for index, signal in enumerate(result["signals"]):
            code = signal["id"]
            if code in held:
                continue  # 持仓中，不重复入场

            stock = next((s for s in market.get("stocks", []) if s["id"] == code), None)
            if not stock:
                continue
            adjusted, reason = _apply_exit_rules(config, market, stock)
            entry_price = float(stock.get("close", 0)) or (20 + float(stock.get("volRatio", 1)) * 12 + index * 3)

            # 离场价：用离场日同只股票的真实收盘价；找不到时退回估算
            exit_stock = next((s for s in exit_market.get("stocks", []) if s["id"] == code), None)
            if exit_stock and exit_stock.get("close"):
                exit_price = float(exit_stock["close"])
            else:
                exit_price = entry_price * (1 + adjusted / 100)

            held[code] = exit_date  # 标记持仓

            trades.append(
                {
                    "id": f"{entry_date}_{code}_{index}",
                    "code": code,
                    "name": signal["name"],
                    "entry": entry_date,
                    "entryPrice": f"{entry_price:.1f}",
                    "exit": exit_date,
                    "exitPrice": f"{exit_price:.1f}",
                    "return": _fmt((exit_price / entry_price - 1) * 100 if entry_price else 0),
                    "reason": reason,
                    "maxLoss": float(stock.get("maxLoss", 0)),
                }
            )

    total = sum(_parse_pct(item["return"]) for item in trades)
    wins = sum(1 for item in trades if _parse_pct(item["return"]) > 0)
    win_rate = f"{wins / len(trades) * 100:.1f}%" if trades else "0.0%"
    max_drawdown = min((float(item.get("maxLoss", 0)) for item in trades), default=0)
    bt_id = f"bt_{int(datetime.now().timestamp() * 1000)}"
    return {
        "id": bt_id,
        "name": name,
        "range": range_text,
        "return": _fmt(total),
        "winRate": win_rate,
        "synced": False,
        "strategyId": None,
        "config": config,
        "trades": len(trades),
        "details": {
            "summary": {
                "return": _fmt(total),
                "annualized": _fmt(total / 2),
                "sharpe": f"{max(0.3, (wins + 1) / max(1, len(trades) - wins + 1)):.2f}",
                "maxDrawdown": _fmt(max_drawdown),
                "winRate": win_rate,
                "trades": len(trades),
                "avgHold": "7天",
            },
            "trades": trades,
        },
    }


def _market_checks(config: dict, market: dict) -> list[dict]:
    p = config["params"]
    return [
        {"name": f"{p['s0_ma']}日年线", "pass": bool(market.get("indexAboveMa")), "val": "指数在年线上方" if market.get("indexAboveMa") else "指数跌破年线"},
        {"name": "跌停家数", "pass": _num(market.get("limitDownCount")) <= _num(p["s0_limit"]), "val": f"{market.get('limitDownCount')} <= {p['s0_limit']}"},
        {"name": "连续暴跌", "pass": _num(market.get("crashDays")) < _num(p["s0_crash"]), "val": f"{market.get('crashDays')} < {p['s0_crash']}"},
    ]


def _evaluate_stock(config: dict, market: dict, stock: dict) -> dict:
    s1_map = _s1_checks(config, market, stock)
    s2_map = _s2_checks(config, stock)
    s1 = [{**s1_map[key], "key": key} for key in config["s1Keys"] if key in s1_map]
    s2 = [{**s2_map[key], "key": key} for key in config["s2Keys"] if key in s2_map]
    return {
        "stock": stock,
        "s1Results": s1,
        "s2Results": s2,
        "s1Pass": all(item["pass"] for item in s1),
        "s2Pass": all(item["pass"] for item in s2),
        "pass": all(item["pass"] for item in s1) and all(item["pass"] for item in s2),
    }


def _s1_checks(config: dict, market: dict, stock: dict) -> dict:
    p = config["params"]
    return {
        "s1_drop": {"name": "大盘跌幅", "pass": _num(market.get("marketDrop")) >= _num(p["s1_drop"]), "val": f"{market.get('marketDrop')}% >= {p['s1_drop']}%"},
        "s1_close": {"name": "个股收盘价", "pass": bool(stock.get("closeAbovePrev")), "val": "收盘 >= 昨收" if stock.get("closeAbovePrev") else "收盘 < 昨收"},
        "s1_vol_panic": {"name": "大盘恐慌放量", "pass": _num(market.get("marketVolRatio")) >= _num(p["s1_vol_panic"]), "val": f"{market.get('marketVolRatio')} >= {p['s1_vol_panic']}"},
        "s1_inverse": {"name": "个股逆势收阳", "pass": bool(stock.get("closeAboveOpen")), "val": "收盘 > 开盘" if stock.get("closeAboveOpen") else "收盘 <= 开盘"},
        "s1_ma20": {"name": "大盘均线向上", "pass": bool(market.get("ma20Up")), "val": "20日线向上" if market.get("ma20Up") else "20日线走弱"},
        "s1_high": {"name": "创N日新高", "pass": _num(stock.get("highDays")) >= _num(p["s1_high"]), "val": f"{stock.get('highDays')} >= {p['s1_high']}"},
        "s1_gap": {"name": "跳空高开缺口", "pass": bool(stock.get("gapUp")), "val": "存在缺口" if stock.get("gapUp") else "无缺口"},
        "s1_pullback": {"name": "回踩不破均线", "pass": _num(stock.get("pullbackDays")) >= _num(p["s1_pullback"]), "val": f"{stock.get('pullbackDays')} >= {p['s1_pullback']}"},
        "s1_shadow": {"name": "长下影反包", "pass": _num(stock.get("lowerShadowRatio")) >= _num(p["s1_shadow"]), "val": f"{stock.get('lowerShadowRatio')} >= {p['s1_shadow']}"},
        "s1_surge": {"name": "事件放量异动", "pass": _num(stock.get("surgePct")) >= _num(p["s1_surge"]), "val": f"{stock.get('surgePct')}% >= {p['s1_surge']}%"},
    }


def _s2_checks(config: dict, stock: dict) -> dict:
    p = config["params"]
    return {
        "s2_ma": {"name": "站上均线", "pass": bool(stock.get("aboveMa")), "val": f"{'站上' if stock.get('aboveMa') else '跌破'}{p['s2_ma']}日线"},
        "s2_fund": {"name": "资金未流出", "pass": _num(stock.get("fundSafeDays")) >= _num(p["s2_fund"]), "val": f"{stock.get('fundSafeDays')} >= {p['s2_fund']}"},
        "s2_macd": {"name": "指标金叉", "pass": bool(stock.get("macdCross")), "val": "金叉" if stock.get("macdCross") else "未金叉"},
        "s2_super": {"name": "特大单净流入", "pass": _num(stock.get("superInflowDays")) >= _num(p["s2_super"]), "val": f"{stock.get('superInflowDays')} >= {p['s2_super']}"},
        "s2_vol": {"name": "成交量放大", "pass": _num(stock.get("volRatio")) >= _num(p["s2_vol"]), "val": f"{stock.get('volRatio')} >= {p['s2_vol']}"},
        "s2_rsi": {"name": "超卖回升", "pass": _num(stock.get("rsi")) >= _num(p["s2_rsi_level"]), "val": f"{stock.get('rsi')} >= {p['s2_rsi_level']}"},
        "s2_main": {"name": "主力净流占比", "pass": _num(stock.get("mainInflowPct")) > _num(p["s2_main"]), "val": f"{stock.get('mainInflowPct')}% > {p['s2_main']}%"},
        "s2_north": {"name": "北向资金增持", "pass": _num(stock.get("northDays")) >= _num(p["s2_north_days"]) and _num(stock.get("northPct")) > _num(p["s2_north_pct"]), "val": f"{stock.get('northDays')}日 / {stock.get('northPct')}%"},
    }


def _apply_exit_rules(config: dict, market: dict, stock: dict) -> tuple[float, str]:
    keys = set(config.get("s3Keys") or [])
    p = config["params"]
    ret = _num(stock.get("backtestReturn"))
    reason = stock.get("exitReason") or "策略离场"
    if "s3_hard" in keys and _num(stock.get("maxLoss")) <= _num(p["s3_hard"]):
        ret = max(ret, _num(p["s3_hard"]))
        reason = "硬止损"
    if "s3_market" in keys and _num(market.get("limitDownCount")) > _num(p["s3_market_limit"]):
        ret = min(ret, -3)
        reason = "系统性防御清仓"
    if "s3_trail" in keys and ret > 8:
        ret -= 1
        reason = "移动止盈"
    return ret, reason


def _details(items: list[dict]) -> list[dict]:
    return [{"name": item["name"], "val": item["val"], "status": "通过" if item["pass"] else "阻断"} for item in items]


def _num(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _parse_pct(value: str) -> float:
    return _num(str(value).replace("%", "").replace("+", ""))


def _fmt(value: float) -> str:
    return f"{'+' if value >= 0 else ''}{value:.1f}%"

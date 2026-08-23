from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MonitorPageTest(unittest.TestCase):
    def test_monitor_header_has_manual_scan_button(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const handleRunScan = (", html)
        self.assertIn("onClick={() => handleRunScan()}", html)
        self.assertIn("执行扫描", html)
        self.assertIn("bg-blue-600 hover:bg-blue-500 text-white px-3 md:px-4 py-1.5 rounded-md flex items-center text-sm font-medium transition-colors", html)

    def test_new_users_start_without_seeded_demo_trades(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("useSeedAwareState([], 'lq_positions_v2', 'lq_positions', MOCK_DB.monitorPositions)", html)
        self.assertIn("useSeedAwareState([], 'lq_history_v2', 'lq_history', MOCK_DB.historyTrades)", html)
        self.assertIn("暂无模拟持仓；完成扫描后可将观察标的加入这里", html)

    def test_demo_data_cannot_modify_simulated_positions(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("currentProvider !== 'mock'", html)
        self.assertIn("当前为演示或离线数据，只能查看，不能修改模拟持仓", html)
        self.assertIn("加入模拟持仓", html)

    def test_monitor_scan_feedback_names_strategy_and_result(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("按当前运行策略重新执行扫描", html)
        self.assertIn("const scanSignalCount = (data.signals || []).length;", html)
        self.assertIn("onShowToast(`已按【${appliedStrategy.name}】完成扫描：${scanSignalCount} 只候选 (${dataSourceName(data.provider)})`);", html)

    def test_monitor_scan_button_exposes_busy_feedback(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("isScanning ? '扫描中，请稍候' : scanButtonTitle", html)
        self.assertIn("<Icons.LoaderCircle", html)
        self.assertIn("animate-spin", html)

    def test_monitor_mobile_holding_cards_keep_risk_actions_visible(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('md:hidden space-y-3', html)
        self.assertIn('aria-label={`${row.name}：${canOperateSimulation ? holdingActionLabel : \'只读\'}`}', html)
        self.assertIn('hidden md:table', html)

    def test_backtest_start_exposes_busy_feedback_and_blocks_duplicates(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        backtest_view = html[html.index("const ViewBacktest") : html.index("// ==========================================\n        // 主入口组件")]

        self.assertIn("const [isStartingBacktest, setIsStartingBacktest] = useState(false);", backtest_view)
        self.assertIn("const backtestStartText = isStartingBacktest ? '回测中' : '启动引擎';", backtest_view)
        self.assertIn("disabled={isStartingBacktest}", backtest_view)
        self.assertIn("setIsStartingBacktest(true);", backtest_view)
        self.assertIn("setIsStartingBacktest(false);", backtest_view)

    def test_monitor_stat_labels_running_strategy(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('StatBlock label="运行策略"', html)
        self.assertNotIn('StatBlock label="当前策略"', html)

    def test_monitor_header_omits_context_eyebrow(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        title_index = html.index("收盘复盘台")
        header_start = html.rfind("<PageHeader", 0, title_index)
        monitor_header = html[header_start : html.index("stats={", title_index)]
        self.assertNotIn("eyebrow=", monitor_header)
        self.assertNotIn("本地策略原型", monitor_header)

    def test_monitor_header_explains_close_scan_timing(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("基于历史日线和收盘数据执行扫描；每个交易日收盘后生成明日观察清单，不作为盘中实时买卖提醒。", html)

    def test_monitor_notice_shows_provider_order_and_token_status_without_token_input(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("providerOrder: data.providerOrder || []", html)
        self.assertIn("configured: data.configured || {}", html)
        self.assertIn("const providerOrderNotice =", html)
        self.assertIn("const tushareNotice =", html)
        self.assertIn("Tushare 已使用本地 token 配置", html)
        self.assertIn("Tushare 未配置本地 token", html)
        self.assertNotIn("TUSHARE_TOKEN", html)
        self.assertNotIn("type=\"password\"", html)

    def test_monitor_provider_labels_match_history_daily_data_goal(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("AKShare 历史日线", html)
        self.assertIn("BaoStock 历史日线备用", html)
        self.assertIn("新浪行情兜底", html)

    def test_monitor_notice_explains_data_confidence_tier(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const dataSourceTier =", html)
        self.assertIn("数据可信层级：历史日线源", html)
        self.assertIn("数据可信层级：行情兜底源", html)
        self.assertIn("数据可信层级：演示数据", html)

    def test_monitor_notice_summarizes_provider_fallback_without_raw_errors(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const providerFallbackNotice =", html)
        self.assertIn("本次已从 AKShare 切换至备用数据源", html)
        self.assertIn("BaoStock 当前不可用", html)
        self.assertIn("item.toLowerCase().includes('baostock')", html)
        self.assertIn("${providerFallbackNotice}", html)
        self.assertNotIn("${(remoteData?.warnings || []).join(' ')}", html)

    def test_monitor_scan_status_is_in_funnel_card_actions(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        funnel_card = html[html.index("策略漏斗总览") : html.index("第 0 步：市场环境")]
        self.assertIn("title={<><Icons.Activity className=\"mr-2 text-zinc-400\" size={16}/>策略漏斗总览</>}", html)
        self.assertIn("actions={", funnel_card)
        self.assertIn("{scanDateLabel}", funnel_card)
        self.assertIn("{scanDateValue}", funnel_card)

    def test_monitor_scan_date_is_readonly_until_history_records_exist(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('const latestScanDate = remoteData?.tradeDate || remoteData?.providerDate || localDemoDate;', html)
        self.assertIn("const scanDateLabel = remoteData ? '扫描日期' : awaitingLocalScan ? '扫描状态' : '演示日期';", html)
        self.assertIn("const scanDateValue = remoteData ? latestScanDate : awaitingLocalScan ? '待扫描' : currentDate;", html)
        self.assertIn("const scanDateTitle = remoteData ? '最新扫描日期' : awaitingLocalScan ? '尚未执行扫描' : '本地演示日期';", html)
        self.assertIn("{scanDateLabel}", html)
        self.assertIn("{scanDateValue}", html)
        self.assertIn("待扫描", html)
        self.assertNotIn("<select value={currentDate}", html)
        self.assertNotIn("dateOptions.map", html)
        self.assertNotIn('label: "2026-05-20 本地演示"', html)
        self.assertNotIn('label: "2026-05-19 历史复盘"', html)

    def test_monitor_scan_uses_provider_date_from_api(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('const scanDate = data.tradeDate || data.providerDate || localDemoDate;', html)
        self.assertIn("setCurrentDate(scanDate);", html)
        self.assertIn("providerDate: data.providerDate,", html)
        self.assertIn("tradeDate: scanDate", html)
        self.assertNotIn('setCurrentDate("2026-05-20");', html)

    def test_local_monitor_waits_for_manual_scan(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const pendingScanData =", html)
        self.assertIn("const awaitingLocalScan = apiStatus.status === 'online' && isLiveDate && !remoteData;", html)
        self.assertIn("第 1 步确认运行策略，第 2 步执行扫描，第 3 步查看并选择观察标的", html)
        self.assertIn("尚未执行本地扫描", html)
        self.assertNotIn("handleRunScan({ silent: true", html)

    def test_signal_list_has_board_filter_without_changing_scan_total(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const STOCK_BOARD_OPTIONS =", html)
        self.assertIn("const stockBoardOf = (code) =>", html)
        self.assertIn("const [signalBoardFilter, setSignalBoardFilter] = useStickyState('all', 'lq_signalBoardFilter');", html)
        self.assertIn("const filteredSignals = signalBoardFilter === 'all' ? signals : signals.filter(row => stockBoardOf(row.id) === signalBoardFilter);", html)
        self.assertIn("当前显示", html)
        self.assertIn("板块", html)
        self.assertIn("{filteredSignals.length}", html)
        self.assertIn("{signals.length}", html)
        self.assertIn("filteredSignals.map(row =>", html)
        self.assertIn("当前板块暂无符合条件标的", html)

    def test_signal_board_filter_uses_custom_dark_menu_and_shared_pills(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('const META_PILL_CLASS = "inline-flex h-9 items-center gap-2 rounded-lg border border-zinc-800/80 bg-[#111216] px-3 text-sm shadow-inner shadow-black/20";', html)
        self.assertIn('const BOARD_FILTER_GROUP_CLASS = "flex items-center gap-3 flex-wrap justify-end";', html)
        self.assertIn("const [isBoardMenuOpen, setIsBoardMenuOpen] = useState(false);", html)
        self.assertIn("aria-haspopup=\"listbox\"", html)
        self.assertIn("role=\"listbox\"", html)
        self.assertIn("role=\"option\"", html)
        self.assertIn("top-[calc(100%+6px)]", html)
        self.assertNotIn("<select value={signalBoardFilter}", html)

    def test_local_scan_results_are_saved_and_restored_by_strategy(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const SCAN_DB_NAME = 'leek-strategy-scans';", html)
        self.assertIn("const SCAN_STORE_NAME = 'scanRecords';", html)
        self.assertIn("const scanRecordKey = (strategyId) => `strategy:${strategyId}`;", html)
        self.assertIn("const saveScanRecord = async ({ strategyId, strategyName, data }) =>", html)
        self.assertIn("const loadLatestScanRecord = async (strategyId) =>", html)
        self.assertIn("key: scanRecordKey(strategyId)", html)
        self.assertIn("strategyId: appliedStrategy.id", html)
        self.assertIn("strategyName: appliedStrategy.name", html)
        self.assertIn("saveScanRecord({", html)
        self.assertIn("loadLatestScanRecord(appliedStrategy.id)", html)
        self.assertIn("setRemoteData(record.data);", html)
        self.assertIn("setCurrentDate(record.data.tradeDate || record.data.providerDate || localDemoDate);", html)

    def test_holding_actions_do_not_follow_scan_date_readonly_state(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const canOperateHolding = capabilities.canChangePortfolio;", html)
        self.assertIn("const canOperateSimulation = capabilities.canChangePortfolio && currentProvider !== 'mock';", html)
        self.assertIn("const holdingActionDate = latestScanDate;", html)
        self.assertIn("if (!canOperateHolding) return onShowToast('收盘快照为只读，不能离场');", html)
        self.assertIn("exit: holdingActionDate,", html)

        holding_card = html[html.index("当前持仓风控") : html.index("{positions.length === 0")]
        self.assertIn("disabled={!canOperateSimulation}", holding_card)
        self.assertIn("const holdingActionLabel = row.status === 'warning' ? '记录离场' : row.status === 'danger' ? '记录止损' : '';", holding_card)
        self.assertIn("canOperateSimulation ? holdingActionLabel : '只读'", holding_card)
        self.assertIn("canOperateSimulation ? '记录离场' : '只读'", html)
        self.assertIn("canOperateSimulation ? '记录止损' : '只读'", html)
        self.assertNotIn("disabled={!isLiveDate}", holding_card)
        self.assertNotIn("isLiveDate ? '离场'", holding_card)
        self.assertNotIn("isLiveDate ? '斩仓'", holding_card)

    def test_monitor_cards_align_header_with_content_edges(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn('headerClass = "px-4 md:px-6 py-3"', html)
        funnel_card = html[html.index("策略漏斗总览") : html.index("第 0 步：市场环境")]
        self.assertIn('headerClass="px-4 py-3"', funnel_card)
        self.assertIn('bodyClass="p-4 space-y-4"', funnel_card)
        self.assertIn("w-full min-w-0", html)
        self.assertIn("flex items-center gap-3 flex-wrap justify-end shrink-0", html)

    def test_monitor_scan_button_clicks_even_when_scan_is_unavailable(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const canRunScan = Boolean(appliedStrategy) && capabilities.canScan;", html)
        self.assertIn("disabled={scanButtonDisabled}", html)
        self.assertIn("const scanButtonDisabled = hasStaticScan || isScanning;", html)
        self.assertIn("aria-disabled={!canRunScan || scanButtonDisabled}", html)
        self.assertIn("!appliedStrategy ? '请先在策略页应用一个策略'", html)
        self.assertNotIn("button onClick={handleRunScan} disabled={!canRunScan || isScanning}", html)

    def test_static_snapshot_mode_uses_read_only_controls(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const scanButtonText = hasStaticScan ? '只读快照' : isScanning ? '扫描中' : '执行扫描';", html)
        self.assertIn("const scanButtonDisabled = hasStaticScan || isScanning;", html)
        self.assertIn("disabled={scanButtonDisabled}", html)
        self.assertIn("hasStaticScan ? 'GitHub Pages 使用固定演示数据；真实扫描请下载后启动本地服务'", html)

        funnel_card = html[html.index("策略漏斗总览") : html.index("第 0 步：市场环境")]
        self.assertIn("hasStaticScan ? (", funnel_card)
        self.assertIn(">观察日期</span>", funnel_card)
        self.assertIn("{staticDate || '--'}", funnel_card)
        self.assertIn(": (", funnel_card)
        self.assertIn("{scanDateValue}", funnel_card)
        self.assertNotIn("<select value={currentDate}", funnel_card)

    def test_monitor_header_does_not_duplicate_data_source_notice(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const currentProvider =", html)
        self.assertIn("const dataSourceLabel = dataSourceName(currentProvider);", html)
        self.assertIn("数据源：${dataSourceLabel}", html)
        monitor_actions = html[html.index("actions={") : html.index("stats={", html.index("actions={"))]
        self.assertNotIn(">数据源</span>", monitor_actions)
        self.assertNotIn("当前数据源", monitor_actions)

    def test_top_bar_shows_copyright_and_research_disclaimer(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("© 2026 LINPO LAB · 仅供研究观察，不构成投资建议", html)
        top_bar = html[html.index("h-14 border-b border-zinc-800/60") : html.index("<div className=\"flex-1 flex overflow-hidden", html.index("h-14 border-b border-zinc-800/60"))]
        self.assertIn("justify-between", top_bar)
        self.assertIn("hidden lg:block", top_bar)

    def test_toast_timer_is_reset_between_messages(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("const toastTimerRef = useRef(null);", html)
        self.assertIn("if (toastTimerRef.current) clearTimeout(toastTimerRef.current);", html)
        self.assertIn("toastTimerRef.current = setTimeout(() => setToast(''), 3000);", html)


if __name__ == "__main__":
    unittest.main()

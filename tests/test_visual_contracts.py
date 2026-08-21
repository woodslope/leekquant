from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VisualContractsTest(unittest.TestCase):
    def test_table_cards_align_header_with_table_cell_edges(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        history_card = html[html.index("历史交易明细库") : html.index("</Card>", html.index("历史交易明细库"))]
        self.assertIn('headerClass="px-6 py-3"', history_card)
        self.assertIn('bodyClass="p-0 overflow-x-auto"', history_card)
        self.assertIn('<th className="py-3 px-6 font-normal">代码名称</th>', history_card)

        backtest_card = html[html.index("回测记录</>") : html.index("</Card>", html.index("回测记录</>"))]
        self.assertIn('headerClass="px-4 py-3"', backtest_card)
        self.assertIn('bodyClass="p-0 overflow-x-auto"', backtest_card)
        self.assertIn('<th className="py-3 px-4 font-normal">回测名称</th>', backtest_card)

    def test_strategy_editor_header_matches_wide_body_padding(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        strategy_editor = html[html.index('bodyClass="p-4 md:p-8"') - 220 : html.index("未选择策略")]

        self.assertIn('headerClass="px-4 md:px-8 py-3"', strategy_editor)
        self.assertIn('bodyClass="p-4 md:p-8"', strategy_editor)

    def test_strategy_library_header_matches_nested_card_content_on_mobile(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        strategy_library = html[html.index("策略库</>") : html.index("</Card>", html.index("策略库</>"))]

        self.assertIn('headerClass="px-6 py-3"', strategy_library)
        self.assertIn('bodyClass="p-3 space-y-3 overflow-y-auto"', strategy_library)

    def test_main_page_headers_omit_eyebrow_labels(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")

        for title in ["收盘复盘台", "历史交易复盘", "策略规则配置", "回测任务大厅"]:
            title_index = html.index(title)
            header_start = html.rfind("<PageHeader", 0, title_index)
            header_end = html.index("stats={", title_index)
            page_header = html[header_start:header_end]
            self.assertNotIn("eyebrow=", page_header)

    def test_history_trade_records_can_be_cleared_with_confirmation(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        history_view = html[html.index("const ViewHistory") : html.index("// ==========================================\n        // 子视图：4. 回测页")]

        self.assertIn("const handleClearHistory = () =>", history_view)
        self.assertIn("确定清空全部历史交易记录吗？此操作只会清除本浏览器里的模拟交易历史，无法撤回。", history_view)
        self.assertIn("setHistoryTrades([]);", history_view)
        self.assertIn("历史交易记录已清空", history_view)
        self.assertIn("清空记录", history_view)
        self.assertIn("暂无历史交易记录", history_view)

    def test_project_ui_style_guide_captures_visual_contracts(self):
        guide = ROOT / "UI_STYLE_GUIDE.md"

        self.assertTrue(guide.exists())
        text = guide.read_text(encoding="utf-8")
        self.assertIn("视觉合同", text)
        self.assertIn("Card", text)
        self.assertIn("执行扫描", text)
        self.assertIn("390px", text)


if __name__ == "__main__":
    unittest.main()

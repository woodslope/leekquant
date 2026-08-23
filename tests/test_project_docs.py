from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProjectDocsTest(unittest.TestCase):
    def test_backtest_task_pool_exists_with_prioritized_items(self):
        path = ROOT / "BACKTEST_TASKS.md"

        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("严格回测任务池", text)
        self.assertIn("P0", text)
        self.assertIn("逐日扫描", text)
        self.assertIn("持仓", text)
        self.assertIn("离场", text)
        self.assertIn("收益统计", text)

    def test_readme_documents_one_click_local_start(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("双击 `双击启动.command`", readme)
        self.assertIn("bash start.sh", readme)
        self.assertIn("http://127.0.0.1:8765/index.html", readme)
        self.assertNotIn("未包含本地双击启动脚本", readme)
        self.assertNotIn("start.sh", gitignore)
        self.assertNotIn("双击启动.command", gitignore)

    def test_readme_documents_configurable_data_sources(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("核心目标是 A 股收盘后策略复盘与次日观察", readme)
        self.assertIn("AKShare -> BaoStock -> 新浪行情兜底 -> mock", readme)
        self.assertIn("LEEK_PROVIDER_ORDER", readme)
        self.assertIn("TUSHARE_TOKEN", readme)
        self.assertIn(".env.example", readme)
        self.assertIn("浏览器不会保存 token", readme)
        self.assertIn("Tushare token", readme)
        self.assertIn("TUSHARE_TOKEN=", env_example)
        self.assertIn(".env", gitignore)

    def test_readme_matches_scheduled_close_scan_contract(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/close-scan.yml").read_text(encoding="utf-8")

        self.assertIn("GitHub 收盘快照版", readme)
        self.assertIn("工作日 16:37", readme)
        self.assertIn("只读", readme)
        self.assertIn('cron: "37 8 * * 1-5"', workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertNotIn("GitHub Actions 不再定时生成行情", readme)

    def test_frontend_runtime_is_local_and_version_locked(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        package = (ROOT / "package.json").read_text(encoding="utf-8")

        self.assertIn('href="assets/app.css"', html)
        self.assertIn('src="assets/vendor/react.production.min.js"', html)
        self.assertNotIn("cdn.tailwindcss.com", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertIn('"react": "18.3.1"', package)
        self.assertIn('"tailwindcss": "3.4.17"', package)


if __name__ == "__main__":
    unittest.main()

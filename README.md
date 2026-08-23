# 韭菜策略 A 股策略原型

这是一个 A 股策略监控原型，目标是验证「策略配置 -> 收盘扫描 -> 信号展示 -> 模拟持仓 -> 回测导入」这条产品流程。

项目已经完成了单页前端、本地 Python API、AKShare 免费数据源尝试接入、BaoStock 历史日线备用源、新浪行情兜底、SQLite 缓存、mock 数据降级、基础扫描/回测接口，以及 GitHub Pages 可读取的收盘静态数据生成流程。它更适合用于产品流程演示、页面截图、策略规则讨论和收盘后轻量复盘，不建议作为真实交易依据。

## 项目归属

本项目归属 LINPO LAB，用于 A 股策略产品原型、收盘复盘流程验证和相关内容展示。

## 产品定义

当前项目按两个形态推进：

- 本地原型版：本机启动 Python 服务，前端调用 `/api/*`，适合演示完整交互、模拟持仓和新建回测。
- GitHub 收盘快照版：前端放在 GitHub Pages，读取仓库内的 `public-data/*.json`，用于在线展示和截图。

GitHub 收盘快照版不是实时行情系统。它由 Close Scan 工作流在工作日收盘后更新一次，页面始终以只读方式展示最新收盘结果。需要编辑策略、执行扫描、管理模拟持仓或回测时，请下载项目并启动本地服务。

核心目标是 A 股收盘后策略复盘与次日观察；核心数据是历史日线和收盘数据，不是盘中实时行情。

只跑收盘数据后，系统要求会明显降低：不需要盘口、分钟线、实时推送、券商客户端和交易通道，只需要免费源能提供日线/收盘行情。但它也因此只能用于复盘和观察，不能表达为盘中买卖提醒。

## 当前能力

- 配置策略规则：支持大盘开关、信号发现、入场确认、离场规则。
- 监控收盘信号：本地 API 可扫描市场；GitHub Pages 模式可读取收盘静态 JSON；GitHub 收盘静态生成时，AKShare 不可用会先尝试 BaoStock 历史日线备用源，再尝试新浪行情兜底，仍失败才降级到 mock 数据。
- 管理模拟交易：前端支持模拟买入、离场、历史交易记录和纪律离场展示。
- 创建基础回测：可以生成回测记录，并把回测配置导入策略库。
- 本地缓存数据：市场快照和个股日 K 会写入 SQLite，减少重复请求。
- 本地保存扫描记录：本地 API 扫描完成后，浏览器会按运行策略把最近一次结果写入 IndexedDB，刷新页面或切换回该策略时可恢复查看。
- 生成静态结果：`scripts/generate_public_data.py` 会输出 `public-data/latest-scan.json`、`run-status.json`、`market-snapshot.json` 和按日期归档的历史结果。

## 界面风格约定

这个页面面向国内 A 股散户用户和产品截图传播，不按英文金融终端或海外 SaaS 仪表盘处理。

- 文案默认使用简体中文，只有 `AKShare`、股票代码、接口名等必要专有名词保留英文。
- 视觉保持深色、克制、工具型，不使用营销页式大标题、渐变装饰或过强按钮高亮。
- 左上角品牌标识使用“韭菜束”图形，不使用通用叶菜 emoji 或无关植物图形。
- 顶部导航采用低调状态线，选中底线使用品牌绿，不使用突兀的浮起按钮。
- 页面统一使用紧凑页头、四列指标块、深色卡片和 8px 圆角，避免每个页面各做一套层级。
- 提示条统一为低饱和黄色警示样式，左侧使用图标，右侧保留关闭按钮。
- 指标标签优先写成“运行策略、扫描信号、模拟持仓、市场开关”等用户可理解的词。
- 规则编号、版本号、技术缩写不直接暴露给普通用户；需要展示时转成中文解释。
- 截图发布时要保留“原型演示 / 数据源状态 / 不作为真实交易依据”的边界提示。
- 更具体的卡片、按钮、表格、视觉合同和验证规则见 `UI_STYLE_GUIDE.md`。

### 组件规范

- 页面框架：顶部导航高度固定为 56px，选中态只使用中性底色和品牌绿底边线，不使用浮起按钮；主页面由页面框架统一纵向滚动，避免卡片内部无必要地截断内容。
- 页头：所有主页面统一使用紧凑页头、标题、说明和四列指标块；不单独新增大标题区。
- 页头指标：指标块只保留上方标签和主要数值，不放第三行辅助说明；需要解释时合并进标签或页面说明，避免占用垂直空间。
- 卡片：主卡片和内层面板统一使用深色底、细边框、8px 圆角和克制阴影；不使用渐变装饰。
- 提示条：统一黄色警示条，左侧警示图标，中间说明文字，右侧关闭按钮；不再使用文字标签区分样式。
- 按钮：主操作使用蓝色或绿色实底，危险操作使用红色，普通操作使用灰色文字或描边；统一使用 6px 圆角，不使用发光阴影。
- 表格：表头、行高、分割线保持一致；股票代码、日期、收益等数据可使用等宽字体，中文表头不使用英文式大写和过宽字距；状态信息优先使用徽标，不使用彩色 emoji 圆点；密集表格里的详情、导入、删除等操作使用紧凑 icon 按钮，不使用彩色文字链接堆叠。
- 文案：界面文案默认中文，面向普通 A 股用户解释，不直接暴露英文 SaaS 标签和技术缩写。

## 当前边界

- 当前主要是产品原型，不是完整量化交易系统。
- 免费数据源不稳定，AKShare、BaoStock 和新浪接口都可能因为网络、远端服务或字段变化失败。
- GitHub 收盘快照版只读展示收盘结果，不支持盘中实时扫描、策略编辑、模拟交易、回测任务或账户交易。
- 回测还不是严格的逐日历史回测，部分逻辑使用当前横截面或样本数据兜底。
- 部分策略因子来自行情快照的近似推导，例如资金流、MACD、RSI、北向资金等，不能等同于真实指标计算。
- 策略、持仓、历史交易等前端状态主要存储在浏览器 `localStorage`；本地扫描记录存储在浏览器 `IndexedDB`。这些都只属于当前浏览器，不适合当作跨设备、长期可靠的数据仓库。

## 为什么暂停推进

项目的主要难点不在页面，而在数据可信度和回测可信度。

要把它从原型推进到可用工具，需要解决稳定数据源、真实指标计算、历史行情口径、复权、停牌、涨跌停、手续费、滑点、仓位管理、重复信号和真实离场规则等问题。这些工作量明显大于 UI 和接口原型本身。

因此当前版本保留为可运行的本地原型，用于展示产品思路和整理后续方向。

## GitHub 收盘快照版

这个版本的运行方式是：

```txt
GitHub Actions 工作日收盘后运行 Close Scan
        ↓
写入 public-data/*.json
        ↓
GitHub Pages 前端只读展示
```

核心文件：

```txt
config/default-strategy.json        默认收盘扫描策略
scripts/generate_public_data.py     静态数据生成脚本
.github/workflows/close-scan.yml    工作日收盘生成、校验并提交快照
public-data/latest-scan.json        页面读取的最新扫描结果
public-data/run-status.json         最近一次任务状态
public-data/history/YYYY-MM-DD.json 按交易日归档的扫描结果
```

本地生成一次静态数据：

```bash
python3 scripts/generate_public_data.py --provider mock
```

使用免费源尝试生成：

```bash
python3 scripts/generate_public_data.py --provider auto
```

`auto` 会优先尝试 AKShare；如果 AKShare 未安装、网络失败或接口异常，会继续尝试 BaoStock 历史日线备用源，再尝试新浪行情兜底；所有真实数据源都失败时才自动降级到样本数据，并在 JSON 的 `warnings` 字段里说明。

GitHub Actions 在工作日 16:37（北京时间）执行，真实数据源失败时会降级到 mock，校验 JSON 后仅提交 `public-data/`。手动触发用于维护验证。

使用文档规定的 `127.0.0.1:8765` 地址时，页面连接本地 `/api/health`；其他地址默认直接读取 `public-data/latest-scan.json`，不会产生预期外的 API 404。

## 前端资源

页面运行不依赖 CDN。React、ReactDOM 和 Babel 使用锁定版本的本地资源，Tailwind 在发布前生成本地 CSS。修改 `index.html` 中的类名或 `src/styles.css` 后运行：

```bash
npm install
npm run build:ui
```

首次运行浏览器回归测试时安装 Chromium，再执行四档视口用例：

```bash
npx playwright install chromium
npm run test:ui
```

## 后续重启建议

优先级建议：

1. P0：明确定位，是继续做产品演示，还是做真实辅助交易工具。
2. P1：把前后端重复的策略规则收敛到后端，前端只负责配置和展示。
3. P1：用个股历史 K 线计算真实 MA、MACD、RSI、量比、突破、止损等指标。
4. P1：重做回测数据流，按交易日逐日扫描、入场、持仓、离场和统计收益。
5. P2：把策略、回测、交易历史保存到 SQLite，而不是只放在浏览器本地。
6. P2：补充规则、缓存、数据源降级和回测的最小测试集。
7. P3：如果继续长期迭代，再把单文件前端迁移到正式前端工程。

## 启动

不要直接双击 `index.html` 使用完整功能；直接打开文件时，页面无法访问本地 API 和 SQLite 缓存。

macOS 上推荐双击 `双击启动.command`。脚本会自动创建 `.venv`、安装依赖、启动本地 Python API，并打开：

```txt
http://127.0.0.1:8765/index.html
```

如果系统拦截双击脚本，可以在终端运行：

```bash
bash start.sh
```

手动启动方式仍然可用：

```bash
python3 -m pip install -r requirements.txt
python3 server/app.py
```

然后打开：

```txt
http://127.0.0.1:8765/index.html
```

## 数据源配置

默认按 `AKShare -> BaoStock -> 新浪行情兜底 -> mock` 的顺序尝试。本地 API 和 GitHub 收盘静态数据生成共用这条备用链路。这个顺序服务于“历史日线复盘”目标：AKShare 和 BaoStock 优先承担历史日线/收盘数据，新浪只作为行情兜底，不作为核心复盘源。安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

如果免费源没安装、网络不可用、接口临时失败，系统会自动继续尝试下一个免费源；全部失败时才降级到 `MockProvider`，页面仍然能使用样本数据，并在响应或 JSON 的 `warnings` 字段里说明。

本地可以通过环境变量或 `.env` 调整数据源顺序。仓库提供 `.env.example`，复制一份为 `.env` 后按需修改：

```bash
cp .env.example .env
```

示例：

```bash
LEEK_PROVIDER_ORDER=tushare,akshare,baostock,sina,mock
TUSHARE_TOKEN=你的本地 token
```

`.env` 已被 `.gitignore` 忽略，不会提交到 GitHub。浏览器不会保存 token；前端只会显示 Tushare 是否已在本地后端配置、当前数据源顺序和降级 warning。

如果要让 GitHub Actions 也使用 Tushare token，必须把 `TUSHARE_TOKEN` 放到 GitHub Secrets，再在 workflow 里注入环境变量；不要把 token 写进代码或静态页面。没有 token 时，Tushare 会初始化失败并按顺序降级到后续免费源。

## 本地缓存

数据会缓存在本机 SQLite：

```txt
data/cache.sqlite
```

这个文件不会提交到 GitHub。首次请求会从可用免费源拉数据并写入 SQLite；后续请求优先读缓存。

缓存策略：

- 市场快照：5 分钟 TTL，过期后自动刷新。
- 个股日 K：按 `code + trade_date` 存储；再次请求同一区间时优先读本地，缺失部分自动增量补齐。
- AKShare 不可用时：继续尝试 BaoStock 历史日线备用源和新浪行情兜底；所有真实数据源都不可用时使用 mock 数据补齐，接口响应会返回 `provider`、`providerOrder`、`configured` 和 `warnings`。

浏览器侧还会把本地扫描后的最近结果按运行策略保存到 IndexedDB。这个保存只用于刷新页面、切换策略后恢复查看，不会上传到 GitHub，也不会影响 GitHub Pages 的收盘静态数据。

## API

```txt
GET  /api/health
GET  /api/a/market/snapshot
GET  /api/a/stocks/:code/daily?start=20200101&end=20260521
POST /api/a/scan
POST /api/a/backtest
```

`POST /api/a/scan` 入参：

```json
{
  "config": {},
  "executedSignalIds": [],
  "positionIds": []
}
```

`POST /api/a/backtest` 入参：

```json
{
  "name": "未命名回测",
  "range": "2025-01-01 ~ 2026-01-01",
  "config": {}
}
```

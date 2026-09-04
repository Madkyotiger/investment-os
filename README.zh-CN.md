# Investment OS 中文说明

[English](README.md)

Investment OS 把市场数据和来源材料整理成研究问题、证据缺口、反方解释和短简报。它适合希望提高研究纪律，但不想把投资判断交给系统的人和 Agent。

这是公开评估版本：不荐股，不给仓位建议，也不执行交易。

Investment OS 从设计上就是多市场系统。原有 `daily` watchlist 路径继续覆盖美股、港股、市场代理资产、宏观背景和其他已配置来源；可选的 `global-research` 组合继续保留 OpenBB、FinanceToolkit 与 SEC/EDGAR 研究能力。`a-share-daily` 只是新增的 A 股通道，不替代这些路径，也不限制以后接入其他市场或信息源。

## 它解决什么问题

大多数投资工具擅长给数据或给答案。Investment OS 更关心答案之前的研究质量：

- 发生了什么，数据是否足够新；
- 现有证据有多强，还有哪些缺口；
- 除了当前解释，还有什么反方解释；
- 下一步应该查哪份来源；
- 什么证据会削弱当前判断。

系统输出研究问题和核验路径，最终判断仍由人完成。

## 当前可用

- 无需账户、API Key 或网络的离线演示；
- 覆盖宏观、公司事件、主题、市场表现及中美市场的来源框架；
- 区分来源元数据、单一来源数据、交叉核验数据和正文阅读；
- 生成研究问题、反方解释、下一步查证来源和证伪条件；
- 没有足够变化时保持安静的简报渲染器；
- 无需 Tushare Token 的 `investment-os a-share-daily`：支持 A 股个股、stock/ETF/index 分流、行情多源回退、机构持股披露、龙虎榜、大宗交易、交易所两融，以及读者简报与审计包分层；
- 按需调用的公开专家/媒体 Catalog，以及根据主题、地区、观点角色、访问权限和数量上限生成最小抓取计划的 `source-plan`；
- 阻止交易指令和内部过程泄漏到读者输出的边界测试。

它不是券商客户端、投资组合管理器、交易机器人或自动投顾。定时运行和消息推送不在这个公开仓库内。

## 快速开始

需要 Python 3.11 或 3.12，以及 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/Madkyotiger/investment-os.git
cd investment-os
uv sync --frozen --extra dev
uv run investment-os doctor
uv run investment-os demo --out demo-output
uv run pytest -q
```

离线演示会生成：

```text
demo-output/
├── market-metrics.csv
├── market-report.md
├── cxo_daily_brief.md
├── cxo_ranked_candidates.json
└── cxo_brief_quality_scan.json
```

演示通过，说明本地安装、输出路径、排序、简报渲染和边界扫描可以一起工作；它不能证明实时数据源当前可用。

## 按需生成专家与媒体来源计划

共享 Catalog 不是订阅名单，也不会默认把所有来源常驻扫描。调用方必须先给出具体研究问题和明确的访问权限：

```bash
uv run investment-os source-plan \
  --catalog configs/public_source_catalog.json \
  --request configs/source_request.sample.yaml \
  --out .local/source-plan.json
```

输出只是抓取计划，不是证据。专家和媒体内容只能作为发现、背景、机制、共识或反方输入；重要事实仍须回到一手或可审计来源。每个 request 都必须带 `candidate_source_ids` allowlist，避免共享 Catalog 后续扩容时静默扩大某位读者的来源池。标记为 `explicit_need_only` 的来源，必须同时点名 source ID，并明确设置 `allow_explicit_need_only: true`。缺少访问权限时会 fail closed；不可访问或未配置的通道不会被伪装成可抓取入口。

## 无 Key 的 A 股机构观察

这条路径不要求 Tushare Token：

```bash
uv run --frozen --extra china investment-os doctor --probe china-keyless
uv run --frozen --extra china investment-os a-share-daily \
  --config configs/a-share-watchlist.sample.yaml \
  --out .local/a-share-daily \
  --strict
```

它生成四个文件：给人读的 `brief.md`，以及用于复核的 `evidence-ledger.csv`、`coverage-matrix.md`、`source-receipt.json`。`no_event` 表示来源读取成功，但观察窗口内没有该标的事件；`source_error` 表示来源没有读到。两者不能混写。

AKShare 是无 Key 适配层。个股行情会从东方财富回退到新浪、腾讯，不再误走 ETF 接口。机构持股、龙虎榜和大宗交易属于便利性二手证据；沪深交易所两融数据通过适配器读取官方公开数据，但两融仍不能被写成“机构净流入”。Tushare 只是可选二源；没有 `TUSHARE_TOKEN` 不会让无 Key 路径降级。

新鲜度门槛仍是 5 个自然日。A 股长假期间，`--strict` 可能在新交易日数据出现前 fail closed；系统不会把 stale 数据改标成 fresh。

## Agent 安装

Agent 可以直接运行公开评估，不改动全局 Python 或系统配置：

```bash
uvx --from git+https://github.com/Madkyotiger/investment-os.git \
  investment-os demo --out ./investment-os-demo
```

如果 Agent 在本地仓库中工作，请遵循 [`AGENTS.md`](AGENTS.md) 和 [`docs/AGENT_INSTALL.md`](docs/AGENT_INSTALL.md)。

## Agent Skill

可移植 Skill 位于 [`skills/investment-research/`](skills/investment-research/)。把整个目录复制或链接到 Agent 的 Skill 搜索路径，再调用 `investment-research`。它补的是研究纪律和来源门槛，不会替你配置凭证、实时数据、定时任务、消息推送或交易执行。

## 可选实时行情检查

用隔离环境运行 `market` 依赖，避免把可选包长期装进项目 `.venv`：

```bash
cp configs/watchlist.sample.yaml configs/watchlist.local.yaml
uv run --frozen --isolated --link-mode copy --extra market \
  investment-os run \
  --config configs/watchlist.local.yaml \
  --out live-output \
  --strict
```

`--strict` 会在所有标的都没有足够新、可用的数据时返回非零状态。有输出文件，不等于抓到了可用数据。

示例 watchlist 中标记为 `source: china` 的标的会在这次 market-only 检查里保留为明确的数据缺口，不会被误发给 Yahoo。

如果要作为日常运行环境使用，只把 `market` 依赖长期装进项目 `.venv`，并把“包能导入”和“数据通道可用”分开检查：

```bash
uv sync --frozen --extra dev --extra market
cp .env.example .env
# 把 .env 中的 SEC 占位身份改成真实联系身份。
set -a; source .env; set +a
uv run investment-os doctor --probe daily
```

无人值守的本地运行可调用 `scripts/run_daily_local.sh`。脚本优先读取 `${XDG_CONFIG_HOME:-$HOME/.config}/investment-os/runtime.env`（也可用 `INVESTMENT_OS_ENV_FILE` 指定），没有时才回退到仓库内被忽略的 `.env`。

`doctor` 会分别报告包是否 `importable`、通道是否 `configured`、实时 `live_probe` 是否成功。OpenBB、FinanceToolkit、edgartools、AKShare、Tushare 都不是美股/港股 `investment-os daily` 的必要依赖；只有 `a-share-daily` 需要 AKShare，Tushare 仍为可选。Stooq 只是 best-effort 二源：代码路径正确或 HTTP 200 都不算成功，必须实际解析出可用 CSV；否则 daily 继续标记为单一来源，不假装完成交叉核验。

SEC 请求需要有效身份字符串。它不是 API secret，但真实联系信息仍应只放在被忽略的本地环境文件里：

```bash
export SEC_EDGAR_IDENTITY="Your Name your-email@example.com"
```

## 可选依赖组合

公开的 lockfile 把实时行情、全球研究数据商和中国数据商拆成独立组合。下面的命令只安装到临时隔离环境，不会扩大项目 `.venv`：

```bash
uv run --no-project python scripts/verify_dependency_profiles.py market
uv run --no-project python scripts/verify_dependency_profiles.py global-research china
```

这些检查只验证 lockfile 和必要包能否正常导入，不请求实时数据。第一次运行可能需要下载依赖，之后由 `uv` 缓存加速。

只有启用 Tushare 可选实时二源时，才需要环境变量：

```bash
export TUSHARE_TOKEN="..."
```

不要把凭证或真实持仓提交到仓库。凭证应放在环境变量或已忽略的本地文件中。

## 研究边界

Investment OS 可以回答：

- 哪些事实发生了变化；
- 证据强度如何；
- 还有什么替代解释；
- 下一份应该核验的来源是什么；
- 什么会推翻或削弱当前假设。

它不能告诉你买入、卖出、持有、调整仓位或执行交易。市场数据可能过期、不完整、延迟、修订或错误。来源元数据只能证明一份材料存在，不能证明对材料的解读正确。

## 公开仓库边界

公开仓库包含代码、合成测试数据、示例配置、测试和运行文档，不包含：

- 个人资料或真实持仓；
- 私有研究材料和原始来源抓取；
- 凭证、交付渠道或定时任务；
- 内部回执和本地项目历史。

每次向公开仓库提交前运行公开发布检查：

```bash
uv run python scripts/public_release_guard.py
```

## 当前状态

`0.2.1` 保留 `0.2.0` 的无 Key A 股路径，并修复 UTC 换日边界的新鲜度判断：现在以调用方显式运行时间对应的 Asia/Shanghai 市场日期为准。它适合安装和真人复核评估，不适合无人值守生产运行。定时运行和下游分发由外部运行时负责，不在本仓库范围内。

## License

MIT，见 [`LICENSE`](LICENSE)。

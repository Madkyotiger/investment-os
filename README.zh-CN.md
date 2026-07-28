# Investment OS 中文说明

[English](README.md)

Investment OS 把市场数据和来源材料整理成研究问题、证据缺口、反方解释和短简报。它适合希望提高研究纪律，但不想把投资判断交给系统的人和 Agent。

这是公开评估版本：不荐股，不给仓位建议，也不执行交易。

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

## Agent 安装

Agent 可以直接运行公开评估，不改动全局 Python 或系统配置：

```bash
uvx --from git+https://github.com/Madkyotiger/investment-os.git \
  investment-os demo --out ./investment-os-demo
```

如果 Agent 在本地仓库中工作，请遵循 [`AGENTS.md`](AGENTS.md) 和 [`docs/AGENT_INSTALL.md`](docs/AGENT_INSTALL.md)。

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

部分 SEC 路径需要有效身份字符串：

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

Tushare 实时连接需要环境变量：

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

`0.1.0` 适合安装和评估，不适合无人值守生产运行。下一步是让真人短期试用真实日报，确认它确实提高了研究和判断质量。定时运行和下游分发由外部运行时负责，不在本仓库范围内。

## License

MIT，见 [`LICENSE`](LICENSE)。

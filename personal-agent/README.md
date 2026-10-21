# 每日自动投研数据推送 Agent

工作日收盘后自动抓取 A 股个股行情与资金流、盘点本地文件资产、生成资金面分析报告并邮件推送。
macOS 上用 launchd 定时，**从取数到收件箱全程无人值守**。

做这个的起因很朴素：投研要的是连续观察，但每天手动看盘、手动记笔记坚持不下来。
所以把它写成一条流水线，让数据每天准时出现在我邮箱里。

## 它现在在跑

- 已累计触发 **28 次**，成功投递 **17 封**报告（其余为 SMTP 或网络异常，均有日志记录与重试）。
- 数据源：同花顺公开行情接口（`d.10jqka.com.cn`，JSONP 返回），默认标的 300475，可换任意 A 股代码。
- 调度：macOS LaunchAgent，周一至周五 15:30 自动执行。

## 报告长什么样

每天收到的是一份 Markdown，结构固定：

```markdown
# 个人自动化 agent 分析报告
- 生成时间：2026-10-20T07:41:35+00:00
- 外部数据：本次新增 1 条 / 抓取 6 条

## 外部输入摘要
- 香农芯创 20261020 收盘 114.44（ths:300475:20261020）

## 数据源分析
- 观察期内收盘价：128.65 → 114.44，累计涨跌 -11.05%
- 上涨 2 天，下跌 3 天，整体呈下跌走势
- 最新交易日主力资金净流入 1159 万元
- 超大单+大单净额 1159 万元，中单+小单净额 -7414 万元

### 一句话结论
- 主力净流入、中小单净流出，资金向大单集中。
```

「一句话结论」由规则引擎生成（主力 / 中小单净额方向组合 → 结论模板），不是大模型写的——
**这样每条结论都能追溯到具体数字，也不会产生幻觉**。

## 目录结构

```text
personal-agent/
├── run.py                  # 命令行入口
├── config.example.json     # 配置模板（复制为 config.json 后填写）
├── agent/
│   ├── ingest.py           # ① 抓取行情与资金流，SHA1 去重后落盘
│   ├── inventory.py        # ② 扫描本地文件，生成分类资产地图
│   ├── analyze.py          # ③ 规则引擎分析，输出 Markdown 报告
│   ├── notify.py           # ④ 邮件投递（smtplib + SSL）
│   └── schedule.py         # 生成 macOS LaunchAgent 配置
├── dashboard.py            # 本地可视化面板
├── web/                    # 简易 Web 界面
├── data/                   # 抓取结果（gitignore）
└── output/                 # 报告、日志、定时任务配置（gitignore）
```

## 快速开始

```bash
git clone <this repo> && cd homepage-demo/personal-agent
cp config.example.json config.json     # 填入自己的标的与邮箱
export AGENT_EMAIL_PASSWORD='你的 SMTP 授权码'
python3 run.py ingest                  # ① 抓数据
python3 run.py inventory               # ② 盘本地文件
python3 run.py analyze                 # ③ 出报告
python3 run.py run                     # 三步连跑 + 尝试发邮件
```

改 `config.json` 里的 `external_source.code` 就能换标的；`inventory.roots` 控制扫描范围。

## 定时部署（macOS）

```bash
python3 run.py schedule
cp output/com.user.personal-agent.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.personal-agent.plist
launchctl enable gui/$(id -u)/com.user.personal-agent
launchctl kickstart gui/$(id -u)/com.user.personal-agent   # 立即触发一次，验证用
```

> 旧教程里的 `launchctl load` 在新版 macOS 上会报 `Load failed: 5: Input/output error`，用上面的 `bootstrap` + `enable`。
> 改配置后需 `bootout` 再重新 `bootstrap`。

## 几个设计取舍

- **不调大模型。** 行情结论靠规则 + 阈值，零调用成本、零延迟、可解释；真要用 LLM 总结，替换 `analyze.py` 的结论段即可。
- **全标准库。** `urllib` 抓数、`smtplib` 发信、`hashlib` 去重，没有第三方依赖，换台 Mac 拉下来就能跑。
- **抓取幂等。** 每条行情按内容 SHA1 去重，重复运行不会污染历史序列。
- **失败留痕。** 异常写进 `output/agent.error.log`，不发静默失败——SMTP 失败那几次就是靠日志定位的。

## 隐私

`data/`、`output/`、`config.json` 均在 `.gitignore` 中，邮箱密码通过环境变量 `AGENT_EMAIL_PASSWORD` 传入，不入库。

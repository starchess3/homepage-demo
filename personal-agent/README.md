# 个人自动化 agent

这是一个把作业三道题串起来的最小可运行项目：

1. 定期抓取一条外部数据（默认使用 RSS，可替换成 API 或网页源）。
2. 遍历本机文件，生成「数据与技能地图」。
3. 把外部输入和本地地图结合，定时启动分析，并把报告发送到邮箱。

## 目录结构

```text
personal-agent/
├── config.json          # 数据源、扫描范围、邮箱、定时配置
├── run.py               # 命令行入口
├── agent/
│   ├── ingest.py        # ① 外部数据抓取与去重
│   ├── inventory.py     # ② 本地资产盘点
│   ├── analyze.py       # ③ 生成分析报告
│   ├── notify.py        # 邮件投递
│   └── schedule.py      # 生成 macOS LaunchAgent 定时配置
├── data/                # 抓取结果与资产地图
└── output/              # 分析报告、日志、定时配置
```

## 运行

```bash
cd /Users/zhouxingli/personal-agent
python3 run.py ingest       # 抓取外部数据
python3 run.py inventory    # 盘点本地文件
python3 run.py analyze      # 生成报告
python3 run.py run          # 依次执行上面三步并尝试发邮件
python3 run.py schedule     # 生成定时任务配置
```

## 配置说明

`config.json` 里最需要改的是：

- `external_source.type/url`：数据源。`rss` 走 RSS，`api` 走返回 JSON 的接口。
- `inventory.roots`：要盘点哪些目录；`exclude_dirs` 是要排除的目录。
- `email`：发信参数；密码不写进文件，而是用环境变量 `AGENT_EMAIL_PASSWORD` 传入。
- `schedule.interval_seconds`：任务间隔，默认 6 小时。

## 邮件配置示例

先编辑 `config.json` 的 `email` 字段，例如：

```json
{
  "enabled": true,
  "smtp_host": "smtp.qq.com",
  "smtp_port": 587,
  "username": "你的邮箱",
  "from": "你的邮箱",
  "to": "接收邮箱"
}
```

然后运行：

```bash
export AGENT_EMAIL_PASSWORD='你的 SMTP 授权码'
python3 run.py run
```

## 定时任务

运行 `python3 run.py schedule` 后，按提示执行：

```bash
cp output/com.user.personal-agent.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.personal-agent.plist
launchctl enable gui/$(id -u)/com.user.personal-agent
```

> 旧教程里的 `launchctl load` 在新版 macOS 上已经失效，会报
> `Load failed: 5: Input/output error`，请用上面的 `bootstrap` + `enable`。

如果改了配置需要重新加载，先卸载再安装：

```bash
launchctl bootout gui/$(id -u)/com.user.personal-agent
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.personal-agent.plist
launchctl enable gui/$(id -u)/com.user.personal-agent
```

立即手动触发一次（用于验证）：

```bash
launchctl kickstart gui/$(id -u)/com.user.personal-agent
```

查看状态：

```bash
launchctl print gui/$(id -u)/com.user.personal-agent
```

卸载：

```bash
launchctl bootout gui/$(id -u)/com.user.personal-agent
```

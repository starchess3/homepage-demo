from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def notify(config: dict, report_path: Path) -> None:
    email = config["email"]
    if not email.get("enabled"):
        print(f"邮件未启用，报告保存在 {report_path}")
        return

    password = os.environ.get(email.get("password_env", ""), "")
    if not password and email.get("password_file"):
        password_file = Path(email["password_file"]).expanduser()
        if password_file.exists():
            password = password_file.read_text(encoding="utf-8").strip()

    required = [email.get("smtp_host"), email.get("username"), email.get("from"), email.get("to"), password]
    if not all(required):
        print("邮件配置不完整，跳过发送；请填写 SMTP 信息并设置密码环境变量。")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = "个人自动化 agent 分析报告"
    message["From"] = email["from"]
    message["To"] = email["to"]
    body = report_path.read_text(encoding="utf-8")
    message.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(email["smtp_host"], int(email["smtp_port"]), timeout=30) as server:
        server.starttls()
        server.login(email["username"], password)
        server.sendmail(email["from"], [email["to"]], message.as_string())
    print(f"报告已发送到 {email['to']}")

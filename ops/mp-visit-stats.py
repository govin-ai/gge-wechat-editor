#!/usr/bin/env python3
"""Build a private daily visit report from this site's Nginx access logs."""

import argparse
import gzip
import html
import json
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("Asia/Shanghai")
LOG_LINE = re.compile(
    r'^(\S+) \S+ \S+ \[([^]]+)\] "(\S+) (\S+) HTTP/[^\"]+" '
    r'(\d{3}) \S+ "[^\"]*" "([^\"]*)"'
)
BOT = re.compile(
    r'bot|crawl|spider|slurp|headless|lighthouse|curl|wget|python-requests|'
    r'httpclient|go-http-client|uptimerobot|monitor|facebookexternalhit|'
    r'preview|semrush|ahrefs|petalbot', re.I
)
DAY = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def count_visits(log_dir):
    views = defaultdict(int)
    people = defaultdict(set)
    for log_file in sorted(log_dir.glob("mp.ggelabs.access.log*")):
        opener = gzip.open if log_file.suffix == ".gz" else open
        with opener(log_file, "rt", encoding="utf-8", errors="replace") as lines:
            for line in lines:
                match = LOG_LINE.match(line)
                if not match:
                    continue
                ip, timestamp, method, target, status, user_agent = match.groups()
                if method != "GET" or status not in {"200", "304"}:
                    continue
                if target.split("?", 1)[0] not in {"/", "/index.html"}:
                    continue
                if not user_agent or BOT.search(user_agent):
                    continue
                try:
                    day = datetime.strptime(timestamp, "%d/%b/%Y:%H:%M:%S %z")
                    day = day.astimezone(TIMEZONE).date().isoformat()
                except ValueError:
                    continue
                views[day] += 1
                people[day].add((ip, user_agent))
    return {day: {"visitors": len(people[day]), "views": count}
            for day, count in views.items()}


def save_atomically(destination, content):
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    try:
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def render_page(days, generated_at):
    recent = sorted(days, reverse=True)[:30]
    rows = "\n".join(
        f"<tr><td>{html.escape(day)}</td>"
        f"<td>{days[day]['visitors']}</td><td>{days[day]['views']}</td></tr>"
        for day in recent
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <title>每日访问统计 · G哥公众号排版</title>
  <style>
    :root {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #f5f3ff; background: #090818; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 28px 18px; }}
    main {{ max-width: 760px; margin: 0 auto; }}
    a {{ color: #b59dff; }}
    h1 {{ font-size: clamp(25px, 5vw, 36px); margin: 32px 0 10px; }}
    p {{ color: #aaa6c1; line-height: 1.7; }}
    .card {{ margin-top: 25px; border: 1px solid #353052; border-radius: 16px; overflow: hidden; background: #151329; }}
    table {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }}
    th, td {{ padding: 14px 18px; text-align: right; border-bottom: 1px solid #302b48; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ color: #c4b0ff; font-size: 14px; }}
    tr:last-child td {{ border-bottom: 0; }}
    .note {{ font-size: 13px; }}
  </style>
</head>
<body>
  <main>
    <a href="/">← 返回排版工具</a>
    <h1>每日访问统计</h1>
    <p>mp.ggelabs.com · 按北京时间统计 · 最近 30 天</p>
    <div class="card"><table>
      <thead><tr><th>日期</th><th>访客估算</th><th>页面浏览</th></tr></thead>
      <tbody>{rows}</tbody>
    </table></div>
    <p class="note">访客估算按每天相同 IP 与浏览器标识去重，并过滤常见爬虫。共享网络、频繁换网等情况会影响人数准确度。</p>
    <p class="note">每小时更新一次 · 最后更新：{html.escape(generated_at)}</p>
  </main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=Path("/var/log/nginx"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("/var/www/mp.ggelabs.com/stats"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data_file = args.output_dir / "data.json"
    previous = json.loads(data_file.read_text(encoding="utf-8")) if data_file.exists() else {}
    days = {day: {"visitors": int(counts["visitors"]), "views": int(counts["views"])}
            for day, counts in previous.items() if DAY.fullmatch(day)}
    days.update(count_visits(args.log_dir))
    now = datetime.now(TIMEZONE)
    days.setdefault(now.date().isoformat(), {"visitors": 0, "views": 0})
    save_atomically(data_file, json.dumps(days, ensure_ascii=False, sort_keys=True) + "\n")
    save_atomically(args.output_dir / "index.html",
                    render_page(days, now.strftime("%Y-%m-%d %H:%M")))
    print(f"统计已更新：{len(days)} 天")


if __name__ == "__main__":
    main()

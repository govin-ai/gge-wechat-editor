#!/bin/bash
# 双击运行：在本机启动 G哥公众号排版，并自动用浏览器打开
cd "$(dirname "$0")"
PORT=8080
while lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; do PORT=$((PORT+1)); done
URL="http://localhost:$PORT"
echo "G哥公众号排版 已启动：$URL"
echo "关闭这个窗口即可停止。"
( sleep 1; open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL" ) &
if command -v python3 >/dev/null 2>&1; then
  python3 -m http.server $PORT --bind 127.0.0.1
else
  npx --yes http-server -p $PORT -a 127.0.0.1 -c-1
fi

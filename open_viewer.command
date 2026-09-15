#!/bin/zsh
cd "$(dirname "$0")"
if ! test -x .venv/bin/python; then
  print '缺少分析环境，请按 README.md 安装依赖。'
  exit 1
fi
if ! curl -fsS http://127.0.0.1:8879/api/status >/dev/null 2>&1; then
  nohup .venv/bin/python src/serve.py --port 8879 >qa/server.log 2>&1 &
  for attempt in {1..20}; do
    if curl -fsS http://127.0.0.1:8879/api/status >/dev/null 2>&1; then break; fi
    sleep 0.25
  done
fi
if ! curl -fsS http://127.0.0.1:8879/api/status >/dev/null 2>&1; then
  print '工具启动失败，请查看 qa/server.log；README.md 中有重新运行步骤。'
  exit 1
fi
open http://127.0.0.1:8879

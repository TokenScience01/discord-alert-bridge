#!/bin/zsh
cd "$(dirname "$0")"
open "http://127.0.0.1:8765"
exec python3 -u admin.py
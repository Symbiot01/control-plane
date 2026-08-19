#!/bin/bash
set -euo pipefail

exec uvicorn app.main:app --host 0.0.0.0 --port 8000

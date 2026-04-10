#!/usr/bin/env bash
set -euo pipefail

python -m app.cli.import_docs --source-dir data/docs
python -m app.cli.eval run --dataset baseline_v1 --snapshot default
uvicorn app.main:app --host 0.0.0.0 --port 8000

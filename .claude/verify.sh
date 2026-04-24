#!/usr/bin/env bash
# AiNews step verifier.
# Usage: bash .claude/verify.sh [step-id]
# Defaults to 'smoke' when no id given. exit 0 = pass.

set -u
step="${1:-smoke}"
cd "$(dirname "$0")/.." || exit 2

PY=.venv/bin/python
[ -x "$PY" ] || PY="$(command -v python3 || true)"
[ -z "$PY" ] && { echo "[verify] python not found"; exit 2; }

case "$step" in
  smoke|all|"")
    "$PY" -m src.main --dry-run
    ;;
  syntax)
    "$PY" -m py_compile src/*.py && echo "syntax OK"
    ;;
  collect|*collect*)
    "$PY" -c "from src.collect import collect_all; r=collect_all(dry_run=True); assert isinstance(r, list); print(f'collect OK: {len(r)} items')"
    ;;
  classify|*classify*)
    "$PY" -c "from src.classify import classify_articles; classify_articles([]); print('classify OK (empty input)')"
    ;;
  format|*format*)
    "$PY" -c "import src.format_kakao; print('format import OK')"
    ;;
  kakao|*kakao*)
    "$PY" -c "import src.kakao_send, src.kakao_auth; print('kakao imports OK')"
    ;;
  *)
    echo "[verify] id '$step' — no module-specific case, running smoke"
    "$PY" -m src.main --dry-run
    ;;
esac

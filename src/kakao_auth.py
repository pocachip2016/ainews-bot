"""카카오 access_token 자동 갱신."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TOKENS_PATH = ROOT / "data" / "tokens.json"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SAFETY_MARGIN = 300  # 만료 5분 전이면 미리 갱신
REFRESH_TOKEN_DEFAULT_TTL = 60 * 24 * 3600  # 카카오 기본 60일
REFRESH_TOKEN_WARN_DAYS = 7


def _load_tokens() -> dict:
    if not TOKENS_PATH.exists():
        raise FileNotFoundError(
            f"{TOKENS_PATH} 가 없습니다. docs/kakao_auth_guide.md 참조하여 1회 발급하세요."
        )
    return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))


def _save_tokens(data: dict) -> None:
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(TOKENS_PATH, 0o600)
    except OSError:
        pass


def get_access_token() -> str:
    tokens = _load_tokens()
    now = int(time.time())
    if tokens.get("access_token") and tokens.get("expires_at", 0) - SAFETY_MARGIN > now:
        return tokens["access_token"]

    rest_key = os.environ["KAKAO_REST_KEY"]
    refresh_token = tokens["refresh_token"]
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_key,
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    new = resp.json()

    tokens["access_token"] = new["access_token"]
    tokens["expires_at"] = now + int(new.get("expires_in", 21600))
    if new.get("refresh_token"):
        tokens["refresh_token"] = new["refresh_token"]
        tokens["refresh_token_expires_at"] = now + int(
            new.get("refresh_token_expires_in", REFRESH_TOKEN_DEFAULT_TTL)
        )
    elif not tokens.get("refresh_token_expires_at"):
        # 초기 발급 시 저장 안 된 경우: 보수적으로 60일 후 만료 추정
        tokens["refresh_token_expires_at"] = now + REFRESH_TOKEN_DEFAULT_TTL
    _save_tokens(tokens)
    _warn_if_refresh_token_expiring(tokens)
    return tokens["access_token"]


def _warn_if_refresh_token_expiring(tokens: dict) -> None:
    exp = tokens.get("refresh_token_expires_at", 0)
    remaining_days = (exp - int(time.time())) / 86400
    if remaining_days <= REFRESH_TOKEN_WARN_DAYS:
        msg = (
            f"⚠️ 카카오 refresh_token 만료 {remaining_days:.0f}일 전입니다.\n"
            "재인증이 필요합니다: docs/kakao_auth_guide.md STEP 5부터 진행하세요."
        )
        print(f"[kakao_auth] {msg}", file=sys.stderr)
        try:
            from src.kakao_send import send_kakao_memo  # noqa: PLC0415
            send_kakao_memo({
                "object_type": "text",
                "text": msg,
                "link": {"web_url": "https://www.google.com", "mobile_web_url": "https://www.google.com"},
            })
        except Exception as e:
            print(f"[kakao_auth] 경고 알림 전송 실패: {e}", file=sys.stderr)

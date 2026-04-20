"""카카오톡 '나에게 보내기' 메시지 전송."""

from __future__ import annotations

import json
import sys
from typing import Any

import requests

from src.kakao_auth import get_access_token

SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def send_kakao_memo(template_object: dict[str, Any]) -> dict:
    access_token = get_access_token()
    resp = requests.post(
        SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"[kakao] send failed {resp.status_code}: {resp.text}", file=sys.stderr)
        resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    msg = {
        "object_type": "text",
        "text": "AI 뉴스 봇 스모크 테스트입니다.",
        "link": {"web_url": "https://example.com", "mobile_web_url": "https://example.com"},
    }
    print(send_kakao_memo(msg))

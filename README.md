# AI 뉴스 아침 카카오톡 봇 — 아키텍처

전체 아키텍처를 도식과 흐름 두 관점에서 정리.

## 4개 시스템의 역할

```
┌─────────────────────────────────────────────────────────────────┐
│                        역할 분담 (trust boundary)               │
├─────────────────────────────────────────────────────────────────┤
│ 로컬 (~/Work/AiNews)   │ 개발 + 수동 테스트 전용                │
│ GitHub (public repo)    │ 코드 단일 원천. 시크릿·상태 절대 X    │
│ Google Drive (ainews/)  │ 시크릿 + 상태의 장기 보관소           │
│ Claude Cloud (원격)     │ stateless 실행자. 매 새벽 05:30 KST   │
└─────────────────────────────────────────────────────────────────┘
```

## 매일 새벽 자동 실행 시나리오

```
                         05:30 KST (20:30 UTC)
                                 │
                                 ▼
          ┌─────────────────────────────────────────┐
          │  Claude Cloud 원격 에이전트 (stateless) │
          │  트리거 프롬프트 실행 (todo.md STEP 2)  │
          └─────────────────────────────────────────┘
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     │                           │                           │
     ▼ (1) 코드 pull             ▼ (2) 시크릿·상태 pull      ▼ (3) RSS fetch
  ┌──────────┐             ┌──────────────────┐         ┌──────────┐
  │ GitHub   │             │ Google Drive     │         │ RSS/웹   │
  │ clone    │             │ secrets.json     │         │ 12 피드  │
  │ main     │             │ tokens.json      │         └──────────┘
  └──────────┘             │ seen.json        │
                           │ (modifiedTime    │
                           │  최신 버전 선택) │
                           └──────────────────┘
                                 │
              (로컬 샌드박스에 .env + data/*.json 복원)
                                 │
                                 ▼
          ┌─────────────────────────────────────────┐
          │   python -m src.main                    │
          │   ┌─────────────────────────────────┐   │
          │   │ collect.py   (RSS → 24h 필터)   │   │
          │   │        ↓                        │   │
          │   │ classify.py (Gemini API 호출)   │◀──┼── Gemini
          │   │        ↓                        │   │
          │   │ format_kakao.py                 │   │
          │   │        ↓                        │   │
          │   │ kakao_auth.py (토큰 갱신)       │◀──┼── Kakao OAuth
          │   │        ↓                        │   │
          │   │ kakao_send.py  ─────────────────┼───┼──▶ 카카오톡 "나와의 채팅"
          │   │        ↓                        │   │
          │   │ mark_seen (seen.json append +   │   │
          │   │           30일 초과 퇴출)       │   │
          │   └─────────────────────────────────┘   │
          └─────────────────────────────────────────┘
                                 │
                                 ▼ (4) 상태 파일 갱신본 push back
                     ┌──────────────────────────┐
                     │ Google Drive             │
                     │  tokens.json (new ver)   │
                     │  seen.json   (new ver)   │
                     │  ※ MCP create_file 이라  │
                     │    동명 파일이 누적됨    │
                     └──────────────────────────┘
                                 │
                                 ▼ 에이전트 종료
```

## 로컬 개발 사이클 (수동 실행)

```
  개발자 ── Edit ──▶ ~/Work/AiNews/src/*.py
                         │
                         ├─▶ python -m src.main (--dry-run)   ← 즉시 검증
                         │        └ 로컬 .env + data/*.json 사용
                         │          (Drive 안 건드림)
                         │
                         └─▶ git commit + push ─▶ GitHub/main
                                                     │
                                                     └─ 다음 새벽 원격 에이전트가 clone
```

## 데이터·시크릿 흐름 요약

| 파일 | 원천 | 로컬 경로 | GitHub | Drive | 갱신 주체 |
|---|---|---|---|---|---|
| `src/*.py`, `config/*` | 개발자 | git-tracked | ✅ | ❌ | 수동 커밋 |
| `requirements.txt` | 개발자 | git-tracked | ✅ | ❌ | 수동 |
| `.env` (API keys) | 수동 작성 | gitignore | ❌ | `secrets.json`으로 보관 | 수동 |
| `data/tokens.json` | Kakao OAuth | gitignore, chmod 600 | ❌ | ✅ | **봇 자동 롤링 (60일 TTL)** |
| `data/seen.json` | `mark_seen()` | gitignore | ❌ | ✅ | **봇 자동 (30일 retention)** |
| 트리거 프롬프트 | Claude `/schedule` | — | `todo.md`에 문서화 | ❌ | 수동 |

## 왜 이렇게 나눴나 (설계 근거)

1. **GitHub에 시크릿 X** — public 저장소라도 안전하게 쓸 수 있게 `.gitignore`로 `.env`·`data/*.json` 차단.
2. **트리거 프롬프트에 시크릿 X** — Anthropic 측 스케줄 설정에 키를 하드코딩하지 않기 위해 Drive MCP 로 우회. 키 교체 시 Drive 파일 하나만 갱신하면 됨.
3. **stateless 실행 + 외부 상태 보관소 필요** — 원격 에이전트는 매 실행 새 컨테이너. `tokens.json`·`seen.json`을 다음 실행이 읽을 곳이 있어야 하며, 그게 Drive.
4. **MCP `update`/`delete` 부재 → 누적** — 중복 버전 쌓이지만 `modifiedTime` 최신 선택 규칙으로 정상 동작. 월 1회 수동 정리 권장.

## 실제 경계에서의 주의점

- **원격 에이전트는 `git clone`만 하고 push 권한 없음** → 코드 수정은 반드시 로컬 → GitHub 경로로만.
- **로컬 실행은 Drive를 읽지도 쓰지도 않음** → 오늘 로컬에서 돌려 `data/seen.json`이 28건으로 바뀌었어도, Drive에는 반영 X. 내일 원격 배치는 Drive의 이전 seen.json을 읽어옴.
- **migration 호환성** — `_load_seen()`이 list 형식 감지 시 dict로 자동 변환해, 원격 에이전트가 오래된 Drive seen.json(list 800B 버전)을 받아도 정상 동작하고, 다음 업로드는 dict 형식으로 들어감.
- **refresh_token 롤링** — 60일 유효. 매일 최소 1회라도 실행되면 자동 연장. 60일 연속 장애 시만 수동 재발급.

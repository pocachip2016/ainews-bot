# AI 뉴스 아침 카카오톡 봇

## Context

매일 아침 출근 전에 AI 업계의 주요 뉴스를 한눈에 파악하고 싶은 요구. 빈 폴더에서 신규 시작.

요구사항 정리:
- **수집**: 국내 IT 뉴스, 해외 테크 매체, AI 회사 공식 블로그, arXiv/Hacker News 등 **모든 주요 소스**
- **분류**: **중요도(Top/일반/참고) 순**으로 그루핑하되 각 항목에 **카테고리·출처**를 함께 표기
- **요약**: Claude API(`claude-sonnet-4-6`) 1순위 → 실패 시 단순 제목+링크 fallback (OpenAI는 2차 대안)
- **발송**: 카카오 **"나에게 보내기"** REST API (무료, 본인 토큰만 필요)
- **시간**: 새벽에 실행(예: 05:30 KST)하여 아침에 **최종 완성된 메시지 1건**만 수신
- **소스 수 제한**: RSS 피드를 **최대 10~12개로 캡**하고 피드당 최신 기사 **최대 5건**만 사용 → 실행 시간·품질 안정화
- **Windows Claude 버전에서 별도 개발 없이 가능한가?**도 검토

## Claude 윈도 버전에서 별도 개발 없이 할 수 있는가? — 결론: 부분적으로만 가능

| 방식 | 자동 뉴스 수집 | 자동 요약 | 자동 카카오 발송 | 정해진 시각 자동 실행 | 평가 |
|---|---|---|---|---|---|
| Claude Desktop + MCP 서버만 | O (rss MCP) | O | △ (kakao MCP 없음 → HTTP MCP 대체) | **X** (데스크톱 앱이 대화창을 자동으로 열지 않음) | 스케줄이 불가능해 "아침 자동 발송" 요건 미충족 |
| Claude Desktop + Windows 작업 스케줄러 | O | O | △ | △ (앱은 띄울 수 있으나 대화를 자동 전송 불가) | 매일 수동 트리거 필요 |
| **Claude Code `/schedule` (CronCreate) remote agent** | O (WebFetch/WebSearch) | O | O (curl·HTTP) | **O** (cron으로 매일 07:30 실행) | **권장 — 코드 거의 없음** |
| n8n 자체호스팅 (로우코드) | O (RSS 노드) | O (HTTP 노드) | O (HTTP 노드) | O (Cron 노드) | 대안 — GUI로만 구성 |
| Python 스크립트 + cron/작업스케줄러 | O | O | O | O | 코드 100~200줄 필요 |

→ **권장: Claude Code의 스케줄 에이전트(`/schedule`) 방식.** 프롬프트 + 최소 보조 스크립트만으로 동작하고, 사용자가 매일 아침 직접 뭔가를 열지 않아도 자동 발송됨. 장애 시 n8n으로 이식 가능한 구조로 설계.

---

## ⭐ 옵션 A (무개발 / 권장 1순위): Claude Code 슬래시 커맨드 + /schedule

**Python 코드 0줄.** Claude Code가 이미 가진 내장 도구(WebFetch, Bash, 모델 호출, CronCreate)만으로 동작.

### 성능 우려는 해소됨 — 새벽 실행 + 소스 캡
- 실행 시각: **05:30 KST 새벽** (Claude Code `CronCreate`가 원격에서 실행하므로 사용자 PC 전원과 무관)
- RSS 피드: `.ainews/sources.txt`에 **최대 10~12개만** 선정 등록
- 각 피드당 **최신 5건까지만** 파싱 → 총 후보 기사 ≤ 60건
- Claude가 중요도 분류 후 **Top 5 / 일반 5 / 참고 5 = 최대 15건**만 메시지로 구성
- 전체 실행 시간 예상 **2~3분** → 아침 7시 전에 전송 완료

### 필요한 1회성 수작업 (개발 아님 — 카카오 정책상 누구나 해야 함)
1. 카카오 개발자 콘솔에서 앱 생성 + Redirect URI + `talk_message` 동의 설정
2. 브라우저로 인가 코드 1회 발급 → `curl` 한 번 실행해 **refresh_token 획득**
3. `~/Work/AiNews/.ainews/tokens.json`에 refresh_token 저장 (권한 600)
4. `.env`에 `KAKAO_REST_KEY=...` 저장

→ 상세 절차는 별도 문서 `docs/kakao_auth_guide.md` 참고.

### 파일 구조 (3개뿐)
```
/home/ktalpha/Work/AiNews/
├── .env                              # KAKAO_REST_KEY (gitignore)
├── .ainews/
│   ├── tokens.json                   # refresh_token, access_token, expires_at (gitignore)
│   ├── sources.txt                   # RSS URL 10~12개 (한 줄에 하나)
│   └── seen.json                     # 중복 방지용 URL 해시 (gitignore)
└── .claude/
    └── commands/
        └── morning-ainews.md         # 슬래시 커맨드 하나 = 봇 본체
```

### 슬래시 커맨드 `.claude/commands/morning-ainews.md` (개념)
```markdown
---
description: AI 뉴스를 수집·요약해 카카오톡 나에게 전송
---

다음 순서로 작업을 실행하세요.

1. `.ainews/sources.txt`에서 RSS URL 목록(최대 12개)을 읽습니다.
2. 각 URL을 WebFetch로 가져와 **최근 24시간 기사 중 피드당 최대 5건**만 추립니다.
   `.ainews/seen.json`에 있는 URL은 제외합니다.
3. **AI/ML 관련 기사만 필터링**한 뒤 중요도 3단계로 분류합니다.
   AI 관련 판단 기준: LLM·생성형AI·머신러닝·딥러닝·AI 칩/하드웨어·AI 정책/규제·
   AI 스타트업/투자·AI 응용(에이전트·로보틱스·자율주행 등). 순수 일반 IT(예: 모바일 신제품,
   일반 보안 이슈, AI 무관 스타트업)는 **제외**합니다.
   - TOP: 최대 5건 (업계 주요 발표·대형 모델 출시·정책)
   - 일반: 최대 5건
   - 참고: 최대 5건 (연구·arXiv·기타)
   각 항목에 [출처/카테고리] 태그와 한국어 2~3문장 요약을 붙입니다.
4. 결과를 카카오톡 list 템플릿 JSON으로 포맷합니다(필요시 2개 메시지로 분할).
5. Bash로 access_token 유효성 확인 → 만료됐으면
   KAKAO_REST_KEY + refresh_token으로 갱신해 tokens.json 업데이트.
6. `curl`로 https://kapi.kakao.com/v2/api/talk/memo/default/send 에
   Bearer 토큰과 template_object를 POST.
7. 성공 시 seen.json에 오늘 보낸 URL 해시를 append.
8. 전송 결과 요약을 콘솔에 출력.
```

Claude가 이 프롬프트를 실행할 때마다 **WebFetch/Bash/Write 내장 도구만으로 전 과정 수행**. 별도 Python/Node 런타임 불필요.

### 자동 스케줄링: Claude Code `CronCreate`
```
/schedule "매일 05:30 KST에 /morning-ainews 실행"
```
내부적으로 `30 20 * * *` UTC로 등록 → 매일 새벽 remote agent가 슬래시 커맨드 실행 → 아침에 카카오톡 1건 수신.

### 장점
- ✅ **스크립트 0줄**, 카카오 앱 등록과 refresh_token 발급만 끝나면 즉시 동작
- ✅ 프롬프트만 수정해 소스·포맷·스타일 즉시 변경 가능
- ✅ Windows에서도 Claude Code CLI만 있으면 동일하게 작동
- ✅ 새벽 실행 + 소스 캡으로 실행 시간·품질 모두 안정화

### 운영 중 품질이 흔들리면 옵션 B로 점진 이관
옵션 A에서 만든 `sources.txt`와 `tokens.json`은 그대로 재사용 가능.

---

## 권장 아키텍처 (옵션 B 상세 — 스크립트 기반)

```
┌──────────────────────┐
│ Claude Code 스케줄러 │  매일 07:30 KST 트리거
│ (/schedule cron)     │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ collect.py           │  RSS 여러 개 + HN/arXiv JSON fetch → articles.json
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Claude (sonnet-4-6)  │  중요도 분류 + 카테고리 태깅 + 한국어 요약
│ (Anthropic SDK)      │  (실패 시 title+url fallback)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ kakao_send.py        │  액세스 토큰 refresh → memo/default/send
└──────────────────────┘
```

## 파일 구조 (신규)

```
/home/ktalpha/Work/AiNews/
├── .env                     # ANTHROPIC_API_KEY, KAKAO_REST_KEY, KAKAO_REFRESH_TOKEN (gitignore)
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt         # anthropic, feedparser, requests, python-dotenv
├── config/
│   └── sources.yaml         # RSS/피드 URL 목록 (카테고리 태그 포함)
├── src/
│   ├── collect.py           # 소스별 기사 수집 → 중복 제거 → 최근 24h 필터
│   ├── classify.py          # Claude 호출: 중요도(top/normal/fyi) + 카테고리 태깅 + 요약
│   ├── format_kakao.py      # 카카오톡 메시지 템플릿 (text link 타입)
│   ├── kakao_auth.py        # refresh_token → access_token 갱신 및 저장
│   ├── kakao_send.py        # /v2/api/talk/memo/default/send 호출
│   └── main.py              # 파이프라인: collect → classify → format → send
├── data/
│   ├── tokens.json          # 카카오 access/refresh token (600 권한, gitignore)
│   └── seen.json            # 이미 전송한 기사 URL 해시 (중복 방지)
└── schedule/
    └── cron.md              # Claude Code /schedule 등록 방법
```

## 구현 단계

### 1단계: 소스 목록 정의 (`config/sources.yaml`)
카테고리 태그를 소스에 선부여하여 LLM 부담 감소.
```yaml
- name: OpenAI Blog
  url: https://openai.com/news/rss.xml
  type: rss
  category: 기업·제품
  region: global
- name: Anthropic News
  url: https://www.anthropic.com/news/rss
  category: 기업·제품
- name: AI타임스
  url: https://www.aitimes.com/rss/allArticle.xml
  category: 국내
- name: TechCrunch AI
  url: https://techcrunch.com/category/artificial-intelligence/feed/
- name: Hacker News (AI keyword)
  url: https://hnrss.org/newest?q=AI+OR+LLM
- name: arXiv cs.AI
  url: http://export.arxiv.org/rss/cs.AI
```

### 2단계: 수집 (`src/collect.py`)
- `feedparser`로 각 피드 파싱
- 최근 24시간 기사만, URL 해시로 `data/seen.json`과 대조해 중복 제거
- 결과: `[{title, url, source, category, published, summary_raw}]`

### 3단계: 분류·요약 (`src/classify.py`)
- 수집된 기사 전체를 한 번의 Claude 호출로 일괄 처리 (프롬프트 캐싱 활용)
- 모델: `claude-sonnet-4-6` (권장 — 분류·한국어 요약 품질·비용 균형 최적)
  - 대안: 비용 최소화 시 `claude-haiku-4-5-20251001`, 최고 품질 필요 시 `claude-opus-4-7`
- **1단계: AI 관련성 필터** — RSS 소스가 일반 IT 매체(TechCrunch, HN 등)를 포함하므로
  LLM·생성형AI·ML·AI 칩·AI 정책·AI 응용 기사만 통과시킴
- **2단계: 중요도 분류 + 한국어 2~3문장 요약**
- 응답 JSON 스키마:
```json
{
  "top": [{"title": "...", "url": "...", "source": "...", "category": "...", "summary_ko": "2~3문장"}],
  "normal": [...],
  "fyi": [...]
}
```
- 호출 실패 시 fallback: 제목·출처·링크만으로 구성

### 4단계: 카카오 메시지 포맷 (`src/format_kakao.py`)
카카오 "나에게 보내기"는 `text` 타입 기준 **본문 최대 200자 + 링크 1개**. 긴 본문은 `feed`/`list` 템플릿이 필요하거나, **여러 번 나눠 전송**.
- 전략: `list` 템플릿으로 중요도별 섹션 (최대 5개 항목) → 초과 분은 `text` 메시지로 추가 발송
- 또는 간단히 `text` 템플릿 여러 번 (중요도 그룹 단위)
```
🌅 AI 뉴스 브리핑 · 04/20(월)

🔥 TOP
• [OpenAI/기업] GPT-X 공개… 추론 3배 향상
  https://...
• [국내/정책] AI기본법 시행령 입법예고
  https://...

📰 일반
• [Anthropic/기업] ...
...

💡 참고
• [arXiv/연구] ...
```

### 5단계: 카카오 인증 (`src/kakao_auth.py`, `src/kakao_send.py`)
- **사전 준비 (1회성, 사용자 수작업)**:
  1. [카카오 개발자 콘솔](https://developers.kakao.com)에서 앱 생성
  2. 플랫폼 → 사이트 도메인 등록 (로컬 OK)
  3. 카카오 로그인 활성화 + Redirect URI 설정
  4. 동의 항목: **"카카오톡 메시지 전송(talk_message)"** 체크
  5. 인가코드 발급 → `refresh_token`, `access_token` 최초 발급해 `data/tokens.json` 저장
- 런타임: `refresh_token`으로 `access_token` 자동 갱신 (만료 6시간)
- 전송 API: `POST https://kapi.kakao.com/v2/api/talk/memo/default/send`
  - `template_object` (JSON 문자열): `{"object_type":"list", ...}`

### 6단계: 파이프라인 (`src/main.py`)
```python
def run():
    articles = collect_all(sources)
    classified = classify_with_claude(articles)  # fallback 내장
    messages = format_for_kakao(classified)
    for msg in messages:
        send_kakao_memo(msg)
    mark_seen(articles)
```

### 7단계: 스케줄 등록 (`schedule/cron.md`)
두 가지 중 택1:
- **A) Claude Code `/schedule`**: `CronCreate`로 `0 22 * * *` UTC (= 07:00 KST)에 remote agent가 `python src/main.py` 실행
- **B) 로컬 cron / Windows 작업 스케줄러**: 가장 단순, 머신이 켜져 있어야 함

운영 안정성을 위해 **A 권장** (원격 실행, 로그 확인 가능).

## 재사용할 외부 리소스 / 패키지

- `anthropic` SDK — Claude API 호출, 프롬프트 캐싱
- `feedparser` — RSS/Atom 파싱
- `requests` — Kakao REST 호출
- `python-dotenv` — 환경변수 관리
- Claude Code `CronCreate` — 스케줄러 (별도 서버 불필요)

## 검증 방법 (end-to-end)

1. **카카오 인증 스모크 테스트**
   ```bash
   python -c "from src.kakao_send import send_kakao_memo; send_kakao_memo({'object_type':'text','text':'테스트','link':{'web_url':'https://example.com'}})"
   ```
   → 카카오톡 "나에게 보내기" 채팅방에 테스트 메시지 수신 확인
2. **수집 단독 실행**: `python -m src.collect` → `articles.json`에 20~50건 수집 확인
3. **분류 단독 실행**: `python -m src.classify < articles.json` → top/normal/fyi 구조 JSON 출력
4. **전체 파이프라인 1회 수동 실행**: `python src/main.py --dry-run` (전송 없이 콘솔 출력) → `python src/main.py` (실제 전송)
5. **스케줄러 등록 후 다음 날 아침 수신 확인**, Claude Code `CronList`로 실행 로그 확인

## 사용자 확인이 필요한 선행 작업

1. 카카오 개발자 계정 앱 등록 + `talk_message` 권한 동의 + refresh_token 1회 발급
2. Anthropic API 키 발급
3. 발송 시각 확정 (기본 07:30 KST 제안)
4. RSS 소스 목록 최종 확인 (필요 시 추가·제거)

# 원격 에이전트 자동화 설정 TODO (Google Drive 방식)

목표: 매일 05:30 KST에 Anthropic 클라우드에서 AI 뉴스 봇이 자동 실행되어 카카오톡으로 전송.

---

## 전체 흐름

```
[Anthropic 클라우드 cron 트리거]
  → 매일 20:30 UTC (= 05:30 KST)
  → 원격 에이전트 실행
  → GitHub에서 코드 clone (시크릿 없음)
  → Google Drive MCP로 secrets.json / tokens.json / seen.json 읽기
  → 로컬 .env 및 data/*.json 생성
  → python -m src.main 실행
  → 실행 후 갱신된 tokens.json / seen.json 을 Drive에 업로드
  → 카카오톡 "나에게 보내기" 전송 완료
```

시크릿과 상태 파일은 모두 **개인 Google Drive `ainews/` 폴더**에 보관.
트리거 프롬프트 자체에는 시크릿이 들어가지 않음.

---

## 완료된 항목

- [x] `.gitignore`에 `.env`, `data/tokens.json`, `data/seen.json` 포함
- [x] GitHub 저장소 생성 (`pocachip2016/ainews-bot`)
- [x] `git init` 및 로컬 초기 커밋 (`2cef524 Initial commit`)
- [x] Google Drive `ainews/` 폴더 생성 (ID: `1o2r1jmGPer1nEZZyaumLsa2Xz5Loq-iV`)
- [x] Drive에 3개 파일 업로드
  - `secrets.json` — `GOOGLE_API_KEY`, `KAKAO_REST_KEY`
  - `tokens.json`  — 카카오 access/refresh token
  - `seen.json`    — 중복 방지 URL 해시

---

## STEP 1: GitHub push

아직 원격에 push 되지 않은 상태.

```bash
cd ~/Work/AiNews
git push -u origin main
```

> 첫 push 시 GitHub 인증 필요 (PAT 또는 `gh auth login`).

---

## STEP 2: 원격 트리거 등록

Claude Code 세션에서:

```
/schedule
```

또는 Claude에게:
> "아래 트리거 프롬프트를 매일 20:30 UTC(= 05:30 KST)에 실행되는 원격 트리거로 등록해줘"

### 트리거 프롬프트 (그대로 복사)

```
당신은 AI 뉴스 봇 파이프라인을 실행하는 원격 에이전트입니다.
다음 단계를 순서대로 수행하고, 중간 실패 시 즉시 중단하고 오류를 보고하세요.

== 1. 코드 clone ==
shell:
  git clone https://github.com/pocachip2016/ainews-bot.git
  cd ainews-bot
  mkdir -p data

== 2. Google Drive 에서 시크릿 · 상태 파일 로드 ==
Google Drive `ainews` 폴더 (folder id: 1o2r1jmGPer1nEZZyaumLsa2Xz5Loq-iV) 에서
다음 3개 파일의 '가장 최근 버전'을 가져옵니다.

각 파일마다:
  1) mcp__claude_ai_Google_Drive__search_files 호출
     query: "title = '<FILE>' and '1o2r1jmGPer1nEZZyaumLsa2Xz5Loq-iV' in parents and trashed = false"
     pageSize: 10
  2) 반환된 files 중 modifiedTime 이 가장 늦은 항목 선택
  3) mcp__claude_ai_Google_Drive__read_file_content 로 내용 읽기

파일별 저장 위치:
  - secrets.json → 내용은 {"GOOGLE_API_KEY":"...","KAKAO_REST_KEY":"..."} JSON.
    파싱하여 로컬 .env 파일에 다음 형식으로 저장:
      KAKAO_REST_KEY=<값>
      GOOGLE_API_KEY=<값>
  - tokens.json  → 로컬 data/tokens.json 에 원본 그대로 저장 (chmod 600)
  - seen.json    → 로컬 data/seen.json 에 원본 그대로 저장

== 3. Python 환경 준비 ==
shell:
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt

== 4. 봇 실행 ==
shell:
  .venv/bin/python -m src.main

stdout / stderr 를 모두 캡처해 보고하세요.
실패 시 traceback 포함.

== 5. 갱신된 상태 파일 Drive 에 업로드 ==
실행 완료 후 로컬 data/tokens.json 과 data/seen.json 은 새 값으로 갱신되어 있습니다.
각 파일을 base64 인코딩하고 mcp__claude_ai_Google_Drive__create_file 로 업로드:
  - parentId: "1o2r1jmGPer1nEZZyaumLsa2Xz5Loq-iV"
  - mimeType: "application/json"
  - disableConversionToGoogleType: true
  - title: "tokens.json"  또는  "seen.json"
  - content: base64 (파일 바이트를 base64로 변환)

(※ MCP 가 update/delete 를 지원하지 않아 동일 이름의 파일이 새로 생성됩니다.
  다음 실행 시 modifiedTime 최신 기준으로 읽으므로 정상 동작.
  월 1회 수동으로 오래된 중복을 Drive 에서 정리하면 깔끔합니다.)

== 6. 완료 보고 ==
한 줄 요약: 수집 N건 / top X normal Y fyi Z / 메시지 M개 전송 / 성공 여부.
```

---

## STEP 3: 수동 테스트

트리거 등록 후:
- [ ] 트리거 상세 페이지에서 **"지금 실행"** 클릭
- [ ] 실행 로그에서 6단계 모두 성공 확인
- [ ] 카카오톡 "나와의 채팅"에 메시지 수신 확인
- [ ] Drive `ainews/` 폴더에 새 `tokens.json`, `seen.json` 버전이 추가되었는지 확인

등록 후 관리: <https://claude.ai/code/scheduled>

---

## STEP 4: 장기 운영

### refresh_token 갱신
- 카카오 refresh_token 유효기간: **60일**
- 봇은 자동으로 갱신된 refresh_token 을 tokens.json 에 기록하고 Drive 에 다시 올립니다.
- **매일 1회라도 실행되면 자동 갱신되므로 수동 개입 불필요.**
- 60일간 한 번도 실행 실패 없이 돌면 영구 유지.

### Drive 파일 정리 (월 1회 권장)
- drive.google.com → `ainews/` 폴더 → `tokens.json` / `seen.json` 중복 파일 중 최신 1개만 남기고 삭제

### 시크릿 교체 시
- Drive `ainews/secrets.json` 파일만 새 값으로 업데이트하면 다음 실행부터 자동 반영.

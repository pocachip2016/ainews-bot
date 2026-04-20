# GitHub + 원격 에이전트 자동화 설정 TODO

목표: 매일 05:30 KST에 Anthropic 클라우드에서 AI 뉴스 봇이 자동 실행되어 카카오톡으로 전송.

---

## 전체 흐름 개요

```
[Anthropic 클라우드 cron 트리거]
  → 매일 20:30 UTC (= 05:30 KST)
  → 원격 에이전트 실행
  → GitHub에서 코드 clone
  → 트리거 프롬프트의 시크릿으로 .env / tokens.json 생성
  → python -m src.main 실행
  → 카카오톡 "나에게 보내기" 전송 완료
```

시크릿(API 키, 토큰)은 GitHub이 아닌 **Anthropic 서버의 트리거 프롬프트**에 암호화 저장됩니다.

---

## STEP 1: .gitignore 최종 확인

- [ ] `.env` 가 .gitignore에 포함됐는지 확인
- [ ] `data/tokens.json` 이 .gitignore에 포함됐는지 확인
- [ ] `data/seen.json` 이 .gitignore에 포함됐는지 확인

```bash
cat .gitignore
```

---

## STEP 2: GitHub 저장소 생성

- [ ] GitHub에서 새 private 저장소 생성
  - 이름 예시: `ainews-bot`
  - **Private** 권장 (시크릿 실수 push 방지)
  - README 없이 빈 저장소로 생성

---

## STEP 3: 로컬 git 초기화 및 push

```bash
cd ~/Work/AiNews

# git 초기화
git init

# 스테이징 (.env, tokens.json 등 gitignore 항목은 자동 제외)
git add -A
git status   # ← 여기서 .env / tokens.json 이 포함 안 됐는지 반드시 확인!

# 첫 커밋
git commit -m "Initial commit: AI news bot"

# GitHub 원격 연결 (YOUR_USERNAME, YOUR_REPO 를 실제 값으로 교체)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

---

## STEP 4: 원격 트리거 프롬프트 준비

원격 에이전트는 매 실행 시 빈 환경에서 시작하므로, 트리거 프롬프트가 아래 내용을 수행해야 합니다.

### 트리거 프롬프트 구조 (Claude Code `/schedule` 또는 RemoteTrigger API)

```
다음 단계를 순서대로 실행하세요.

1. 아래 내용으로 .env 파일을 생성합니다:
   GOOGLE_API_KEY=<실제_구글_API_키>
   KAKAO_REST_KEY=<실제_카카오_REST_키>

2. 아래 내용으로 data/tokens.json 파일을 생성합니다 (디렉토리가 없으면 생성):
   {
     "access_token": "",
     "refresh_token": "<실제_리프레시_토큰>",
     "expires_at": 0
   }

3. Python 가상환경을 만들고 의존성을 설치합니다:
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt

4. 봇을 실행합니다:
   .venv/bin/python -m src.main

5. 실행 결과를 출력합니다.
```

### 현재 시크릿 값 (트리거 등록 시 아래 값으로 채워넣기)

| 항목 | 값 |
|---|---|
| GOOGLE_API_KEY | `.env` 파일의 GOOGLE_API_KEY 값 |
| KAKAO_REST_KEY | `dcc8cf3fd8b8279990f449e7091fb8f3` |
| kakao refresh_token | `data/tokens.json` 의 refresh_token 값 |

> ⚠️ refresh_token 유효기간: **60일**. 만료 전에 트리거 프롬프트를 업데이트해야 합니다.

---

## STEP 5: 원격 트리거 등록

Claude Code 세션에서 실행:

```
/schedule
```

또는 Claude Code 에게 요청:
> "매일 05:30 KST (= 20:30 UTC)에 GitHub 저장소 YOUR_USERNAME/YOUR_REPO 를 clone해서 AI 뉴스 봇을 실행하는 원격 트리거를 등록해줘"

등록 후 확인: https://claude.ai/code/scheduled

---

## STEP 6: 동작 검증

- [ ] 트리거 등록 후 "지금 실행" 버튼으로 1회 수동 테스트
- [ ] 카카오톡 "나와의 채팅"에서 메시지 수신 확인
- [ ] https://claude.ai/code/scheduled 에서 실행 로그 확인

---

## STEP 7: refresh_token 만료 관리

- refresh_token 유효기간: **60일**
- 만료 약 1주일 전에 아래 과정으로 갱신:
  1. 로컬에서 `python -m src.main` 1회 실행 → tokens.json 갱신됨
  2. `data/tokens.json`의 새 refresh_token 을 트리거 프롬프트에 업데이트
  3. https://claude.ai/code/scheduled 에서 트리거 수정

---

## 완료 체크리스트

- [ ] STEP 1: .gitignore 확인
- [ ] STEP 2: GitHub private 저장소 생성
- [ ] STEP 3: git init → push
- [ ] STEP 4: 트리거 프롬프트 시크릿 값 채우기
- [ ] STEP 5: 원격 트리거 등록
- [ ] STEP 6: 수동 테스트 → 카카오톡 수신 확인
- [ ] STEP 7: refresh_token 60일 캘린더 알림 설정

# 카카오 "나에게 보내기" 인증 완전 가이드

본인 카카오톡에 메시지를 보내기 위한 **1회성 설정 + refresh_token 발급** 절차.
소요 시간: 약 15~20분. 개발자 등록비 없음.

---

## 전체 흐름

```
1. 카카오 개발자 등록
2. 애플리케이션 생성 → REST API 키 확보
3. 플랫폼(Web) 등록 + Redirect URI 설정
4. 카카오 로그인 활성화 + 동의항목(talk_message) 설정
5. 브라우저로 "인가 코드" 1회 발급
6. 인가 코드 → access_token + refresh_token 교환
7. tokens.json 저장
8. 테스트 메시지로 검증
```

`access_token`은 6시간 만료, `refresh_token`은 약 60일 유효.
봇이 매일 돌면 refresh_token이 계속 갱신되므로 **사실상 영구적**.

---

## STEP 1: 카카오 개발자 등록

1. https://developers.kakao.com 접속
2. 우측 상단 **로그인** → 본인 카카오 계정으로 로그인
3. 최초 접속 시 **개발자 약관 동의** → 필수 항목 체크 → **동의하고 계속하기**
4. 전화번호 인증 완료

---

## STEP 2: 애플리케이션 생성 + REST API 키 확인

1. 상단 **내 애플리케이션** 클릭
2. **애플리케이션 추가하기** 클릭
3. 입력:
   - 앱 이름: `AI News Bot` (아무 이름 가능)
   - 사업자명: 본인 이름
4. **저장**
5. 생성된 앱 클릭 → **앱 설정 > 앱 키**
6. **REST API 키** 복사 (이후 `KAKAO_REST_KEY`로 사용)

```bash
# 프로젝트 루트에서 실행
cp .env.example .env
# .env 파일을 열고 KAKAO_REST_KEY=복사한_키 로 수정
```

---

## STEP 3: 플랫폼(Web) 등록 + Redirect URI 설정

1. 앱 내부 좌측 메뉴 **앱 설정 > 플랫폼**
2. **Web 플랫폼 등록** → 사이트 도메인: `https://localhost:3000` 입력 → **저장**
3. 좌측 메뉴 **제품 설정 > 카카오 로그인**
4. **활성화 설정: ON**으로 토글
5. **Redirect URI 등록** → **추가** → `https://localhost:3000/oauth` → **저장**

> 이 URL은 실제 서버가 없어도 됩니다. 브라우저 주소창에서 `code=` 파라미터만 확인하면 됩니다.

---

## STEP 4: 동의항목(talk_message) 설정

1. 좌측 메뉴 **제품 설정 > 카카오 로그인 > 동의항목**
2. **"카카오톡 메시지 전송"** (ID: `talk_message`) 찾기
3. 우측 **설정** 클릭
4. **"이용 중 동의"** 선택
5. 동의 목적: `매일 아침 AI 뉴스 브리핑 메시지 전송` 입력
6. **저장**

---

## STEP 5: 인가 코드 발급 (브라우저에서 1회)

아래 URL을 **브라우저 주소창에 붙여넣고 엔터** (REST_API_KEY를 본인 값으로 교체):

```
https://kauth.kakao.com/oauth/authorize?response_type=code&client_id=REST_API_KEY&redirect_uri=https://localhost:3000/oauth&scope=talk_message
```

1. 카카오 로그인 화면 → **본인 계정으로 로그인**
2. 동의 화면 → "카카오톡 메시지 전송" 체크 → **동의하고 계속하기**
3. 브라우저가 `https://localhost:3000/oauth?code=XXXX...` 주소로 이동
   → **"사이트에 연결할 수 없음" 오류가 정상**
4. 주소창의 `code=` 뒤 값 전체 복사 (`&`가 있으면 그 앞까지만)

> **인가 코드는 10분 후 만료** — 바로 STEP 6 진행

---

## STEP 6: 인가 코드 → 토큰 교환

터미널에서 실행 (AUTH_CODE를 방금 복사한 코드로 교체):

```bash
source .env

curl -X POST "https://kauth.kakao.com/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded;charset=utf-8" \
  -d "grant_type=authorization_code" \
  -d "client_id=${KAKAO_REST_KEY}" \
  -d "redirect_uri=https://localhost:3000/oauth" \
  -d "code=AUTH_CODE_HERE"
```

성공 응답 예시:
```json
{
  "access_token": "abcd...xyz",
  "token_type": "bearer",
  "expires_in": 21599,
  "refresh_token": "AAAA...ZZZZ",
  "refresh_token_expires_in": 5183999,
  "scope": "talk_message"
}
```

---

## STEP 7: tokens.json 저장

```bash
cp .ainews/tokens.json.example .ainews/tokens.json
chmod 600 .ainews/tokens.json
```

`.ainews/tokens.json`을 편집기로 열어 위 응답 값 입력:
- `access_token`: 응답의 access_token
- `refresh_token`: 응답의 refresh_token
- `expires_at`: 현재 Unix 시각 + 21599 (`date +%s`로 현재 시각 확인 후 더하기)

현재 Unix 시각 확인:
```bash
date +%s
```

---

## STEP 8: 테스트 메시지 전송

```bash
source .env
ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('.ainews/tokens.json'))['access_token'])")

curl -s -X POST "https://kapi.kakao.com/v2/api/talk/memo/default/send" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  --data-urlencode 'template_object={
    "object_type": "text",
    "text": "✅ AI 뉴스 봇 연결 테스트 성공!",
    "link": {
      "web_url": "https://www.google.com",
      "mobile_web_url": "https://www.google.com"
    },
    "button_title": "확인"
  }'
```

응답: `{"result_code":0}` → 카카오톡 앱의 **"나와의 채팅"**에서 메시지 확인.

---

## 자주 발생하는 오류

| 코드 | 원인 | 해결 |
|---|---|---|
| `KOE101` | REST API 키 오타/공백 | 키 재복사 |
| `KOE320` | Redirect URI 불일치 | 콘솔 등록 값과 완전히 동일하게 |
| `KOE303` | 인가 코드 10분 만료 | STEP 5부터 재시도 |
| `-402` | talk_message 동의 미설정 | STEP 4 확인 후 STEP 5부터 재인증 |
| `-401` | access_token 만료 | refresh_token으로 갱신 |
| `KOE322` | refresh_token 60일 만료 | STEP 5부터 재인가 |

---

## 보안 체크리스트

- [ ] `.env` 가 `.gitignore`에 포함됐는가
- [ ] `.ainews/tokens.json` 이 `.gitignore`에 포함됐는가
- [ ] `chmod 600 .ainews/tokens.json` 실행했는가
- [ ] REST API 키를 공개 저장소에 올리지 않았는가

---
description: AI 뉴스 수집·요약 후 카카오톡 나에게 전송
---

오늘의 AI 뉴스를 수집하여 중요도별로 분류·요약하고, 카카오톡 나에게 보내기로 전송합니다.
**반드시 아래 단계를 순서대로 빠짐없이 실행하세요.**

---

## STEP 1: 환경 변수 및 토큰 로드

```bash
cat .env
```
```bash
cat .ainews/tokens.json
```

`KAKAO_REST_KEY`, `access_token`, `refresh_token`, `expires_at` 값을 메모해 두세요.

---

## STEP 2: access_token 유효성 확인 및 갱신

`expires_at`(Unix timestamp)과 현재 시각(`date +%s`)을 비교합니다.
현재 시각이 `expires_at`보다 크거나 같으면(만료됨) 아래 명령으로 갱신합니다.

```bash
source .env
REFRESH_TOKEN=$(python3 -c "import json; print(json.load(open('.ainews/tokens.json'))['refresh_token'])")
NEW_TOKEN=$(curl -s -X POST "https://kauth.kakao.com/oauth/token" \
  -d "grant_type=refresh_token&client_id=${KAKAO_REST_KEY}&refresh_token=${REFRESH_TOKEN}")
echo "$NEW_TOKEN"
```

응답에서 `access_token`과 `expires_in`을 읽어 tokens.json을 업데이트합니다.
응답에 `refresh_token`이 포함된 경우 그것도 갱신합니다.

업데이트 예시 (python3 인라인 사용):
```bash
python3 -c "
import json, time
d = json.load(open('.ainews/tokens.json'))
d['access_token'] = '여기에_새_access_token'
d['expires_at'] = int(time.time()) + 21599
json.dump(d, open('.ainews/tokens.json', 'w'), indent=2)
print('tokens.json 업데이트 완료')
"
```

---

## STEP 3: 뉴스 수집

```bash
cat .ainews/sources.txt
```
```bash
cat .ainews/seen.json
```

포맷: `이름|카테고리|URL` (# 으로 시작하는 줄은 주석 — 무시)

각 소스 URL을 **WebFetch 도구**로 가져옵니다.
각 피드에서 다음 조건으로 기사를 추립니다:
- `<pubDate>` 또는 `<published>` 기준 **오늘 날짜 기사** (최근 24~30시간)
- 피드당 **최대 5건**
- `seen.json`의 `seen` 배열에 있는 URL은 **건너뜁니다**

각 기사에서 추출할 필드:
- `title`: 기사 제목
- `url`: 링크 (`<link>` 태그)
- `published`: 발행 시각
- `source`: sources.txt의 이름 필드
- `category`: sources.txt의 카테고리 필드
- `summary_raw`: `<description>` 또는 `<summary>` (HTML 태그 제거)

수집한 기사 목록을 내부적으로 정리하세요. (신규 기사가 0건이면 STEP 7로 건너뜀)

---

## STEP 4: 중요도 분류 및 한국어 요약

수집된 기사를 다음 기준으로 분류하세요:

**🔥 TOP** (최대 5건)
- 주요 AI 기업(OpenAI·Anthropic·Google·Meta·MS 등)의 중요 발표
- 대형 모델 출시 또는 기술 혁신
- 한국 AI 정책·규제 중요 동향

**📰 일반** (최대 5건)
- 일반 업계 뉴스, 제품 업데이트, 기업 동향

**💡 참고** (최대 5건)
- 연구 논문(arXiv), 기술 블로그, Hacker News 기사

각 기사에 **한국어 요약 1~2문장**을 추가합니다. (원문이 영어면 번역 요약)
제목도 한국어로 자연스럽게 번역하되, 고유명사·모델명은 영어 유지.

총 선정 기사: TOP 최대 5 + 일반 최대 5 + 참고 최대 5 = **최대 15건**

---

## STEP 5: 카카오톡 메시지 구성 및 전송

메시지를 **최대 2개**로 분할하여 전송합니다.

**메시지 1**: 🔥 TOP + 📰 일반 (최대 5건, list 템플릿)
**메시지 2**: 💡 참고 (최대 5건, list 템플릿) — 참고 기사가 없으면 생략

list 템플릿 JSON 구조:
```json
{
  "object_type": "list",
  "header_title": "🌅 AI 뉴스 브리핑 · MM/DD(요일)",
  "header_link": {
    "web_url": "https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtdHZHZ0pMVWlnQVAB",
    "mobile_web_url": "https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtdHZHZ0pMVWlnQVAB"
  },
  "contents": [
    {
      "title": "[출처] 기사 제목 (45자 이내)",
      "description": "한국어 요약 1~2문장 (80자 이내)",
      "link": {
        "web_url": "https://기사URL",
        "mobile_web_url": "https://기사URL"
      }
    }
  ]
}
```

`title` 필드: `[출처/카테고리] 번역된_기사_제목` 형식, 45자를 초과하면 잘라냄.
`description` 필드: 한국어 요약, 80자를 초과하면 잘라냄.
`contents` 배열: 최대 5개 항목.

전송 명령 (메시지 1):
```bash
ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('.ainews/tokens.json'))['access_token'])")
TEMPLATE_JSON='여기에_위에서_구성한_JSON을_한_줄로_직렬화'

curl -s -X POST "https://kapi.kakao.com/v2/api/talk/memo/default/send" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  --data-urlencode "template_object=${TEMPLATE_JSON}"
```

응답이 `{"result_code":0}` 이면 성공.
실패 시 오류 코드를 확인하고 원인을 진단합니다.

메시지 2도 동일한 방식으로 전송합니다.

---

## STEP 6: seen.json 업데이트

이번에 전송한 모든 기사 URL을 `seen.json`의 `seen` 배열에 추가합니다.

```bash
python3 -c "
import json
seen = json.load(open('.ainews/seen.json'))
new_urls = [
    '여기에URL1',
    '여기에URL2',
]
seen['seen'] = (seen['seen'] + new_urls)[-2000:]  # 최대 2000건 유지
json.dump(seen, open('.ainews/seen.json', 'w'), ensure_ascii=False, indent=2)
print(f'seen.json 업데이트: 총 {len(seen[\"seen\"])}건')
"
```

---

## STEP 7: 완료 보고

다음 형식으로 결과를 출력하세요:

```
✅ 전송 완료: 2026-MM-DD
   🔥 TOP    : X건
   📰 일반   : X건
   💡 참고   : X건
   📨 메시지 : X개 전송
```

신규 기사가 0건인 경우:
```bash
ACCESS_TOKEN=$(python3 -c "import json; print(json.load(open('.ainews/tokens.json'))['access_token'])")
curl -s -X POST "https://kapi.kakao.com/v2/api/talk/memo/default/send" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  --data-urlencode 'template_object={"object_type":"text","text":"📭 오늘 수집된 신규 AI 뉴스가 없습니다.","link":{"web_url":"https://www.google.com"}}'
```

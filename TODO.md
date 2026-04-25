# TODO — AiNews

> **세션 재개 프롬프트**: "TODO.md 확인하고 `## Now`부터 이어서 진행해"

## Now (진행 중, 1~3개)
<!-- 지금 당장 작업 중인 것 -->

## Next (이번 마일스톤)
<!-- 다음 작업 -->

## Later (백로그)
<!-- 언젠가 할 것 -->

## Done (최근 5개만)
- [x] `GOOGLE_API_KEY` TabGet과 분리 — AiNews 전용 키 발급·적용 (쿼터 충돌 방지)
- [x] 05:30 KST 카톡 미수신 버그 수정 — grounding 모델 `gemini-2.0-flash` → `gemini-2.5-flash-lite` 교체
- [x] 파이프라인 오류 시 Kakao 🚨 알림 전송 (이전: 무음 종료)
- [x] `--dry-run` 모드에서 API 미호출 (샘플 데이터 반환)
- [x] feedparser RSS → Gemini grounding 전환

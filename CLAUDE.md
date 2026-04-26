@../CLAUDE.md

## Purpose
AiNews — Gemini grounding 기반 AI 뉴스 수집/발행 봇.

## Stack
- 수집: Gemini grounding (`gemini-2.5-flash-lite` + `google_search` tool) — `GOOGLE_API_KEY` (AI Studio)
- 분류·요약: Gemini (`gemini-2.5-flash-lite`) — 동일 키
- 발송: 카카오톡 나에게 보내기 (`KAKAO_REST_KEY` + `data/tokens.json`)
- 스케줄: 매일 05:30 KST (cron 또는 Claude Code remote schedule)

## Active Work
- Branch: main
- 최근: 파이프라인 오류 알림 추가, grounding 모델을 `gemini-2.5-flash-lite`로 교체, AiNews 전용 `GOOGLE_API_KEY` 분리

## Where to look
- 상세 TODO: `@TODO.md`
- 아키텍처/설계: `docs/` (있는 경우)
- 진행 중 plan: `@plans/` (task slug 디렉토리 참조)

## Verification
- 단위 테스트 부재. 검증은 `bash .claude/verify.sh [step-id]` 로 일원화 — `smoke` 은 `python -m src.main --dry-run`, 모듈별(`collect`/`classify`/`format`/`kakao`) 임포트·동작 체크 지원.

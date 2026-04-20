# 스케줄 등록

## A) Claude Code 원격 스케줄 (권장)

Claude Code 세션에서:

```
/schedule "매일 05:30 KST에 cd /home/ktalpha/Work/AiNews && python -m src.main 실행"
```

내부적으로 `30 20 * * *` UTC cron으로 등록됩니다.
`CronList` 로 확인, `CronDelete` 로 제거.

## B) 로컬 cron (PC가 켜져 있어야 함)

```bash
crontab -e
```

```
30 5 * * * cd /home/ktalpha/Work/AiNews && /usr/bin/python3 -m src.main >> /tmp/ainews.log 2>&1
```

## C) Windows 작업 스케줄러

- 트리거: 매일 05:30
- 동작: `python.exe`, 인수 `-m src.main`, 시작 위치 `C:\...\AiNews`

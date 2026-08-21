# 헬스장/필라테스 노쇼 방지 AI 리마인더 시스템 (MVP)

예약 24시간 전 / 3시간 전 자동 리마인더 발송을 트리거하고, 회원의 노쇼 이력을
기반으로 규칙 기반 위험도 스코어를 계산해 메시지에 반영하는 실동작 MVP입니다.

실제 SMS/카카오톡 API 연동은 하지 않고, 발송 시점에 **콘솔 로그 + 로컬 파일
(`logs/reminders.log`)에 "발송 시뮬레이션" 기록**을 남기는 것으로 구조를 증명합니다.

## 아키텍처

```
seed_data.py     # 샘플 회원/예약 데이터 시딩 (회원 5명, 예약 12건)
db.py            # SQLite 데이터 계층 (members, bookings, reminder_log)
risk.py          # 노쇼 위험도 규칙 기반 스코어링 엔진
reminder.py      # 리마인더 메시지 생성 + '발송 시뮬레이션' 로깅 (중복 발송 방지)
scheduler.py     # APScheduler 기반 주기적 체크 + 트리거 로직 (CLI 진입점)
risk_report.py   # 예정 예약 전체의 위험도를 표로 출력하는 리포트 스크립트
data/gym.db      # SQLite DB 파일 (seed_data.py 실행 시 생성/초기화됨)
logs/reminders.log  # 발송 시뮬레이션 로그 파일
```

### 데이터 모델 (SQLite)
- `members`: id, name, phone
- `bookings`: id, member_id, booking_time, status(`scheduled`/`attended`/`noshow`/`cancelled`), created_at
- `reminder_log`: id, booking_id, reminder_type(`24h`/`3h`), sent_at, risk_score, risk_level, message
  → 같은 예약에 대해 같은 타입의 리마인더가 **중복 발송되지 않도록** 이 테이블로 체크합니다.

### 스케줄러 로직 (`scheduler.check_and_send_reminders`)
1. `status='scheduled'`인 모든 예약을 조회
2. 각 예약에 대해 `hours_until = 예약시각 - 현재시각` 계산
3. `0 < hours_until <= 24` 이고 24h 리마인더 미발송 → 24h 리마인더 발송
4. `0 < hours_until <= 3` 이고 3h 리마인더 미발송 → 3h 리마인더 발송
5. 실제 운영에서는 APScheduler(`BlockingScheduler`)가 이 함수를 짧은 주기(예: 5~10분)로
   반복 호출하며, 예약이 24시간/3시간 임계값을 통과하는 순간 정확히 1회씩 리마인더가 발송됩니다.

### 노쇼 위험도 스코어링 (`risk.compute_risk`, 규칙 기반, 0~100점)
- **최근 90일(3개월) 전체 노쇼율** — 가중치 60%
- **예약과 같은 요일의 노쇼율 패턴** — 가중치 40%
- 라플라스 스무딩(`SMOOTHING=2`)을 적용해 이력이 적은 신규 회원이 극단적인
  점수(0점/100점)로 튀지 않도록 방지
- 최근 취소(cancelled) 이력이 잦으면 소폭 가산점(+최대 10점)
- 등급: `LOW`(0-29) / `MEDIUM`(30-59) / `HIGH`(60-100)
- `HIGH` 등급이면 리마인더 메시지에 "⚠️ 노쇼 위험도 높음 - 스탭 유선 확인 권장" 문구가 자동 추가됩니다.

## 설치

```bash
cd ~/dev/gym-noshow-reminder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 사용법

### 1) 샘플 데이터 시딩 (회원 5명, 예약 12건 생성 — DB 초기화됨)
```bash
python seed_data.py
```

### 2) 노쇼 위험도 리포트 확인
```bash
python risk_report.py
```

### 3) 리마인더 체크를 1회만 즉시 실행 (스케줄러 없이)
```bash
python scheduler.py --once
```

### 4) APScheduler로 주기적 체크 데모 실행
```bash
# 10초 주기로 체크, 40초 후 자동 종료 (데모용 파라미터)
python scheduler.py --interval 10 --duration 40
```
실운영에서는 `--duration` 없이 상시 구동하며 `--interval`을 300~600초(5~10분) 정도로 설정하면 됩니다.

### 5) 발송 로그 확인
```bash
cat logs/reminders.log
```

## 데모 시나리오

`seed_data.py`는 다음과 같은 5명의 회원과 다양한 상황을 시딩합니다:

| 회원 | 특징 | 예정 예약 시점 | 예상 결과 |
|---|---|---|---|
| 김민수 | 예정 예약과 같은 요일에 최근 3개월 3회 중 2회 노쇼 | 약 24시간 후 | 요일 패턴 반영 → MEDIUM 등급, 24h 리마인더 발송 |
| 박지은 | 항상 출석(이력 2회 모두 attended) | 약 2시간 50분 후 | LOW 등급, 24h+3h 리마인더 둘 다 발송 |
| 이서연 | 노쇼/출석 혼합 이력 | 약 5시간 후 (24h/3h 윈도우 밖) | MEDIUM 등급이지만 이번 체크 주기에서는 미발송 대상(24h 이내 진입 시 발송) |
| 최준호 | 잦은 취소 이력만 있음(예정 예약 없음) | - | 취소 가산점 로직 검증용 |
| 정하늘 | 신규 회원, 이력 전무 | 약 22시간 후 | 스무딩 적용으로 극단값 없이 MEDIUM 근처로 산출 |

### 실제 실행 결과 예시

`python risk_report.py` 출력:
```
회원명      예약일시                    점수 등급           전체노쇼율      요일노쇼율     이력건수
------------------------------------------------------------------------------
박지은      2026-08-21 20:55        21 LOW          15.0%      30.0%        2
이서연      2026-08-21 23:05        36 MEDIUM       40.0%      30.0%        2
정하늘      2026-08-22 16:05        30 MEDIUM       30.0%      30.0%        0
김민수      2026-08-22 18:00        52 MEDIUM       52.0%      52.0%        3
```

`python scheduler.py --once` 출력 (발송 시뮬레이션):
```
[2026-08-21 18:05:17] SEND_SIMULATED type=24h booking_id=8 member=박지은 phone=010-2222-3333 risk_score=21 risk_level=LOW msg="[리마인더] 박지은님, 내일(...) 수업 예약이 있습니다. 불참 시 미리 취소 부탁드려요!"
[2026-08-21 18:05:17] SEND_SIMULATED type=3h  booking_id=8 member=박지은 ...
[2026-08-21 18:05:17] SEND_SIMULATED type=24h booking_id=11 member=이서연 ...
[2026-08-21 18:05:17] SEND_SIMULATED type=24h booking_id=12 member=정하늘 ...
[2026-08-21 18:05:17] SEND_SIMULATED type=24h booking_id=7  member=김민수 risk_score=52 risk_level=MEDIUM ...
[18:05:17] 체크 완료: 예정 예약 4건 중 신규 발송 5건
```

동일 명령을 다시 실행하면 `reminder_log` 테이블 덕분에 **신규 발송 0건**으로
중복 발송이 방지되는 것을 확인할 수 있습니다.

## 확장 아이디어 (실제 서비스 전환 시)
- `reminder.send_reminder()` 내부에서 콘솔/파일 로깅 대신 실제 SMS(NHN Toast, 알리고 등) / 카카오 알림톡 API 호출로 교체
- `risk.py`의 규칙 기반 스코어링을 로지스틱 회귀 등 경량 ML 모델로 고도화 (충분한 데이터 축적 후)
- 노쇼 확정 처리(수업 종료 후 출석 체크 안 된 예약을 자동으로 `noshow` 처리)하는 배치 잡 추가
- 위험도 `HIGH` 회원 대상 노쇼 방지 인센티브(리마인더 문구 강화, 보증금 정책 등) 연동

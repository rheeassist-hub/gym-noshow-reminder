"""
노쇼 방지 리마인더 스케줄러.

핵심 로직 (check_and_send_reminders):
  - status='scheduled' 인 모든 예약을 조회
  - 각 예약에 대해 "지금부터 수업까지 남은 시간(hours_until)"을 계산
  - 0 < hours_until <= 24  이고 아직 24h 리마인더 미발송  -> 24h 리마인더 발송
  - 0 < hours_until <= 3   이고 아직 3h  리마인더 미발송   -> 3h  리마인더 발송
  - 발송 시점에 risk.compute_risk() 로 노쇼 위험도를 계산해 메시지/로그에 포함

실제 운영에서는 APScheduler가 이 체크 함수를 짧은 주기(예: 5~10분)로
반복 실행하며, 예약이 24시간/3시간 임계값을 "막 통과하는 순간" 리마인더가
정확히 1회 발송되도록 보장한다 (reminder_log 테이블로 중복 방지).
"""
import argparse
import time
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

import db
import reminder


def check_and_send_reminders():
    now = datetime.now()
    upcoming = db.get_upcoming_bookings()
    sent_count = 0

    if not upcoming:
        print(f"[{now:%H:%M:%S}] 체크: 예정된 예약 없음")
        return sent_count

    for booking in upcoming:
        booking_time = datetime.fromisoformat(booking["booking_time"])
        hours_until = (booking_time - now).total_seconds() / 3600

        if hours_until <= 0:
            continue  # 이미 지난 예약 (별도 노쇼 처리 로직에서 다룸)

        if hours_until <= 24:
            result = reminder.send_reminder(booking, "24h")
            if result:
                sent_count += 1

        if hours_until <= 3:
            result = reminder.send_reminder(booking, "3h")
            if result:
                sent_count += 1

    print(f"[{now:%H:%M:%S}] 체크 완료: 예정 예약 {len(upcoming)}건 중 신규 발송 {sent_count}건")
    return sent_count


def run_scheduler(interval_seconds: int = 10, duration_seconds: int = 40):
    """
    데모용: interval_seconds 주기로 체크 작업을 실행하며,
    duration_seconds 이후 자동 종료한다.
    (실운영에서는 duration 제한 없이 상시 구동)
    """
    scheduler = BlockingScheduler()
    scheduler.add_job(check_and_send_reminders, "interval", seconds=interval_seconds, id="reminder_check")

    print(f"스케줄러 시작 (체크 주기 {interval_seconds}초, {duration_seconds}초 후 자동 종료)")
    check_and_send_reminders()  # 시작 즉시 1회 체크

    start = time.time()

    def _watchdog():
        if time.time() - start >= duration_seconds:
            print("데모 시간 종료 - 스케줄러 종료")
            scheduler.shutdown(wait=False)

    scheduler.add_job(_watchdog, "interval", seconds=2, id="watchdog")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="노쇼 리마인더 스케줄러")
    parser.add_argument("--once", action="store_true", help="스케줄러 없이 체크 1회만 실행")
    parser.add_argument("--interval", type=int, default=10, help="체크 주기(초)")
    parser.add_argument("--duration", type=int, default=40, help="데모 실행 시간(초)")
    args = parser.parse_args()

    if args.once:
        check_and_send_reminders()
    else:
        run_scheduler(interval_seconds=args.interval, duration_seconds=args.duration)

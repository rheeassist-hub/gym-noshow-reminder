"""
모든 예정 예약에 대한 노쇼 위험도 스코어를 계산해 표로 출력하는 리포트 스크립트.
데모/검증용: `python risk_report.py`
"""
from datetime import datetime

import db
import risk


def main():
    upcoming = db.get_upcoming_bookings()
    if not upcoming:
        print("예정된 예약이 없습니다.")
        return

    print(f"{'회원명':<8} {'예약일시':<20} {'점수':>5} {'등급':<7} {'전체노쇼율':>10} {'요일노쇼율':>10} {'이력건수':>8}")
    print("-" * 78)
    for b in upcoming:
        bt = datetime.fromisoformat(b["booking_time"])
        r = risk.compute_risk(b["member_id"], bt)
        print(
            f"{b['name']:<8} {bt.strftime('%Y-%m-%d %H:%M'):<20} {r['score']:>5} {r['level']:<7} "
            f"{r['overall_rate']*100:>9.1f}% {r['weekday_rate']*100:>9.1f}% {r['total_history']:>8}"
        )


if __name__ == "__main__":
    main()

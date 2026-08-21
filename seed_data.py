"""
샘플 데이터 시딩 스크립트.
- 5명의 회원, 총 10건의 예약(과거 이력 6건 + 예정 예약 4건)을 생성한다.
- 과거 이력은 노쇼/출석/취소가 섞이도록 하여 위험도 스코어링이 유의미하게 나오게 한다.
- 예정 예약은 "지금 시점" 기준으로 24시간 이내 / 3시간 이내 / 먼 미래로 나눠
  스케줄러가 실제로 리마인더를 트리거하는 모습을 시연할 수 있게 한다.
"""
from datetime import datetime, timedelta

import db


def _dt_on_weekday(base: datetime, weekday: int, weeks_ago: int, hour: int = 19) -> datetime:
    """base 기준 weeks_ago주 전, 지정 요일(weekday, 0=월)의 특정 시각을 반환"""
    d = base - timedelta(weeks=weeks_ago)
    diff = (d.weekday() - weekday) % 7
    d = d - timedelta(days=diff)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


def _same_weekday_past(reference: datetime, weeks_ago: int) -> datetime:
    """reference와 같은 요일이 되도록 weeks_ago주 전 시각을 반환 (요일 패턴 매칭 데모용)"""
    return reference - timedelta(weeks=weeks_ago)


def seed(reset: bool = True):
    db.init_db(reset=reset)
    now = datetime.now()

    # ---------- 회원 ----------
    kim = db.get_or_create_member("김민수", "010-1111-2222")   # 월요일 노쇼 잦음 -> 고위험
    park = db.get_or_create_member("박지은", "010-2222-3333")  # 성실한 회원 -> 저위험
    lee = db.get_or_create_member("이서연", "010-3333-4444")   # 노쇼/출석 혼합 -> 중위험
    choi = db.get_or_create_member("최준호", "010-4444-5555")  # 잦은 취소 -> 중위험
    jung = db.get_or_create_member("정하늘", "010-5555-6666")  # 신규 회원, 이력 없음 -> 데이터 부족

    bookings_created = []

    # 1) 김민수: 다가오는 수업과 "같은 요일"에 최근 3개월간 3회 중 2회 노쇼
    #    -> 요일별 패턴 스코어가 실제로 반영되도록, 예정 예약(upcoming_kim)과
    #       동일 요일 기준으로 과거 이력을 생성한다.
    upcoming_kim = now + timedelta(hours=23, minutes=55)
    b1 = db.add_booking(kim, _same_weekday_past(upcoming_kim, weeks_ago=2), status="noshow")
    b2 = db.add_booking(kim, _same_weekday_past(upcoming_kim, weeks_ago=5), status="noshow")
    b3 = db.add_booking(kim, _same_weekday_past(upcoming_kim, weeks_ago=8), status="attended")

    # 박지은: 항상 출석
    b4 = db.add_booking(park, now - timedelta(days=10), status="attended")
    b5 = db.add_booking(park, now - timedelta(days=20), status="attended")

    # 최준호: 취소가 잦음
    b6 = db.add_booking(choi, now - timedelta(days=7), status="cancelled")

    bookings_created += [b1, b2, b3, b4, b5, b6]

    # ---------- 예정 예약 (총 4건, status=scheduled) ----------
    # 1) 김민수: 다가오는 수업 - 23시간 55분 후 (24시간 리마인더 트리거 대상)
    booking_kim = db.add_booking(kim, upcoming_kim, status="scheduled")

    # 2) 박지은: 2시간 50분 후 수업 (3시간 리마인더 트리거 대상, 24h는 이미 지남으로 간주)
    upcoming_park = now + timedelta(hours=2, minutes=50)
    booking_park = db.add_booking(park, upcoming_park, status="scheduled")

    # 3) 이서연: 혼합 이력 + 5시간 후 수업 (아직 24h/3h 윈도우 밖 -> 이번 체크에서는 발송 안 됨)
    lee_h1 = db.add_booking(lee, now - timedelta(days=15), status="noshow")
    lee_h2 = db.add_booking(lee, now - timedelta(days=25), status="attended")
    upcoming_lee = now + timedelta(hours=5)
    booking_lee = db.add_booking(lee, upcoming_lee, status="scheduled")

    # 4) 정하늘: 신규 회원, 22시간 후 수업 (이력 없음 -> 스무딩으로 저~중위험 처리)
    upcoming_jung = now + timedelta(hours=22)
    booking_jung = db.add_booking(jung, upcoming_jung, status="scheduled")

    bookings_created += [
        booking_kim, booking_park, lee_h1, lee_h2, booking_lee, booking_jung,
    ]

    print(f"시딩 완료: 회원 5명, 예약 {len(bookings_created)}건 생성")
    print(f"  - 김민수(고위험 예상) 예정 예약: {upcoming_kim.isoformat()} (24h 윈도우)")
    print(f"  - 박지은(저위험 예상) 예정 예약: {upcoming_park.isoformat()} (3h 윈도우)")
    print(f"  - 이서연(중위험 예상) 예정 예약: {upcoming_lee.isoformat()} (윈도우 밖)")
    print(f"  - 정하늘(신규,데이터부족) 예정 예약: {upcoming_jung.isoformat()} (24h 윈도우)")


if __name__ == "__main__":
    seed()

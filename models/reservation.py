# models/reservation.py
# 예약 관련 데이터 모델과 타입을 정의합니다.

from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ReservationStatus(Enum):
    """예약 상태를 나타내는 열거형"""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


@dataclass
class ReservationData:
    """예약 정보를 담는 데이터 클래스"""
    title: str
    room_id: str
    room_name: str
    start_dt: datetime
    end_dt: datetime
    team_id: str
    team_name: str
    booker_id: str
    #participants: List[str]
    page_id: Optional[str] = None
    recurring_id: Optional[str] = None
    booking_date: Optional[str] = None
    #is_recurring: bool = False
    #recurring_weeks: int = 4  # 기본 4주

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "title": self.title,
            "room_id": self.room_id,
            "room_name": self.room_name,
            "start_dt": self.start_dt,
            "end_dt": self.end_dt,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "booker_id": self.booker_id,
            #"participants": self.participants,
            "page_id": self.page_id,
            "recurring_id": self.recurring_id,
            "booking_date": self.booking_date,
            #"is_recurring": self.is_recurring,
            #"recurring_weeks": self.recurring_weeks
        }

    @property
    def duration_minutes(self) -> int:
        """예약 시간(분) 반환"""
        return int((self.end_dt - self.start_dt).total_seconds() / 60)

    @property
    def date_str(self) -> str:
        """날짜 문자열 반환 (YYYY-MM-DD)"""
        return self.start_dt.strftime("%Y-%m-%d")

    @property
    def time_range_str(self) -> str:
        """시간 범위 문자열 반환 (HH:MM ~ HH:MM)"""
        return f"{self.start_dt.strftime('%H:%M')} ~ {self.end_dt.strftime('%H:%M')}"


@dataclass
class ReservationModalData:
    """모달에서 사용하는 예약 데이터"""
    title: str = ""
    room_id: str = ""
    date: str = ""
    start_time: str = ""
    end_time: str = ""
    team_id: str = ""
    #participants: List[str] = None
    page_id: str = ""
    #is_recurring: bool = False
    #recurring_weeks: str = "4"  # 기본 4주

    # def __post_init__(self):
    #     if self.participants is None:
    #         self.participants = [] 
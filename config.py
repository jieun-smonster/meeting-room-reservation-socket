# config.py
# 프로젝트의 모든 설정 정보를 중앙에서 관리합니다.

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class NotionConfig:
    """Notion 관련 설정"""
    api_key: str
    database_id: str
    api_call_delay: float = 0.4
    
    @classmethod
    def from_env(cls) -> "NotionConfig":
        """환경변수에서 설정을 로드합니다."""
        return cls(
            api_key=os.environ["NOTION_API_KEY"],
            database_id=os.environ["NOTION_DATABASE_ID"]
        )


@dataclass  
class SlackConfig:
    """Slack 관련 설정"""
    bot_token: str
    app_token: str
    notification_channel: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "SlackConfig":
        """환경변수에서 설정을 로드합니다."""
        return cls(
            bot_token=os.environ["SLACK_BOT_TOKEN"],
            app_token=os.environ["SLACK_APP_TOKEN"],
            notification_channel=os.environ.get("SLACK_NOTIFICATION_CHANNEL")
        )


class AppConfig:
    """애플리케이션 전체 설정"""
    
    # 회의실 정보 (Notion DB와 동기화 필요)
    MEETING_ROOMS: Dict[str, Dict[str, Any]] = {
        "room_1": {"name": "세미나실", "is_default": True}
    }
    
    # 팀 정보 (Notion DB와 동기화 필요)
    TEAMS: Dict[str, str] = {
        "team_marketing": "전략",
        "team_system": "시스템", 
        "team_operation": "운영",
        "team_franchise": "가맹",
        "team_management": "경영",
        "team_etc": "미지정",
    }
    
    # Notion 데이터베이스 속성 매핑
    NOTION_PROPS: Dict[str, str] = {
        "title": "이름",            # Notion 페이지의 제목 속성
        "room_name": "회의실",      # 회의실 이름 (Select 타입 권장)
        "start_time": "시작시각",    # 시작 시간 (Date 타입)
        "end_time": "종료시각",      # 종료 시간 (Date 타입)
        "team_name": "주관 팀명",    # 주관 팀 (Select 타입 권장)
        "participants": "참석자",   # 참석자 (Person 타입)
        "booker": "예약자",         # 예약자 (Person 타입)
        "booking_date": "예약일",   # 예약 날짜 (Date 타입)
        "recurring_id": "반복 ID", # 반복 예약 ID (Text 타입)
    }
    
    # 반복 예약 설정
    RECURRING_WEEKS: int = 12
    
    # 참석자 표시 설정
    MAX_VISIBLE_PARTICIPANTS: int = 3
    
    @classmethod
    def get_default_room_id(cls) -> Optional[str]:
        """기본 회의실 ID를 반환합니다."""
        for room_id, room_info in cls.MEETING_ROOMS.items():
            if room_info.get("is_default"):
                return room_id
        return None


# 전역 설정 인스턴스들
def get_notion_config() -> NotionConfig:
    """Notion 설정을 반환합니다."""
    return NotionConfig.from_env()


def get_slack_config() -> SlackConfig:
    """Slack 설정을 반환합니다.""" 
    return SlackConfig.from_env()

 

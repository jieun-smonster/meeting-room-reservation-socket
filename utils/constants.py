# utils/constants.py
# 프로젝트 전체에서 사용하는 상수들을 정의합니다.

from enum import Enum


class SlackCommands:
    """Slack 슬래시 커맨드 상수"""
    RESERVATION = "/회의실예약"
    QUERY = "/회의실조회"


class DateFormats:
    """날짜 형식 상수"""
    ISO_DATE = "%Y-%m-%d"
    KOREAN_DATE = "%Y년 %m월 %d일"
    TIME_24H = "%H:%M"
    DATETIME_ISO = "%Y-%m-%d %H:%M"


class SlackBlocks:
    """Slack 블록 타입 상수"""
    SECTION = "section"
    DIVIDER = "divider"
    CONTEXT = "context"
    ACTIONS = "actions"


class SlackElements:
    """Slack 엘리먼트 타입 상수"""
    BUTTON = "button"
    STATIC_SELECT = "static_select"
    DATEPICKER = "datepicker"
    TIMEPICKER = "timepicker"
    MULTI_USERS_SELECT = "multi_users_select"
    PLAIN_TEXT_INPUT = "plain_text_input"


class ButtonStyles:
    """버튼 스타일 상수"""
    PRIMARY = "primary"
    DANGER = "danger"


class CallbackIds:
    """콜백 ID 상수"""
    RESERVATION_SUBMIT = "reservation_modal_submit"
    RESERVATION_EDIT = "reservation_edit_submit"


class ActionIds:
    """액션 ID 상수"""
    EDIT_RESERVATION = "edit_reservation"
    CANCEL_RESERVATION = "cancel_reservation"


class ErrorMessages:
    """에러 메시지 상수"""
    INVALID_DATE_FORMAT = (
        "❌ 날짜 형식이 올바르지 않습니다.\n"
        "사용법: `/회의실조회 [오늘|내일|주간|YYYY-MM-DD]`\n"
        "예시: `/회의실조회`, `/회의실조회 오늘`, `/회의실조회 2024-01-15`"
    )
    MODAL_OPEN_FAILED = "Modal을 여는 데 실패했습니다"
    RESERVATION_QUERY_FAILED = "😥 예약 현황을 조회하는 중 오류가 발생했습니다"
    RESERVATION_PROCESSING_FAILED = "😥 예약 현황 조회 중 예상치 못한 오류가 발생했습니다"
    RESERVATION_CREATE_FAILED = "예약 처리 중 오류가 발생했습니다"
    RESERVATION_UPDATE_FAILED = "예약 수정 중 오류가 발생했습니다"
    RESERVATION_INFO_LOAD_FAILED = "😥 예약 정보를 불러오는 중 오류가 발생했습니다"
    EDIT_MODAL_FAILED = "😥 예약 수정 Modal을 여는 데 실패했습니다"
    RESERVATION_CANCEL_FAILED = "😥 예약 취소 중 오류가 발생했습니다"
    MESSAGE_SEND_FAILED = "오류 메시지 전송 실패"


class SuccessMessages:
    """성공 메시지 상수"""
    RESERVATION_CANCELLED = "✅ 예약이 정상적으로 취소되었습니다."
    RESERVATION_COMPLETED = "✅ 회의실 예약 완료"
    RESERVATION_UPDATED = "✏️ 회의실 예약 수정 완료"


class QueryOptions:
    """조회 옵션 상수"""
    TODAY_KR = "오늘"
    TODAY_EN = "today"
    TOMORROW_KR = "내일" 
    TOMORROW_EN = "tomorrow"
    WEEKLY = "주간"


class TimeEmojis:
    """시간 관련 이모지 상수"""
    DEFAULT = "🕐"  # 단순하게 하나의 시계 이모지만 사용


class WeekdayTranslation:
    """요일 번역 상수"""
    MAPPING = {
        'Monday': '월요일',
        'Tuesday': '화요일', 
        'Wednesday': '수요일',
        'Thursday': '목요일',
        'Friday': '금요일',
        'Saturday': '토요일',
        'Sunday': '일요일'
    }


class NotionConstants:
    """Notion 관련 상수"""
    API_CALL_DELAY = 0.4  # API 호출 간 최소 지연 시간(초) 
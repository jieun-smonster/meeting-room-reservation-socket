# utils/date_utils.py
# 날짜 관련 유틸리티 함수들을 제공합니다.

from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def get_current_date():
    """현재 날짜를 YYYY-MM-DD 형식으로 반환합니다."""
    return datetime.now().strftime('%Y-%m-%d')

def get_korean_weekday(date_str):
    """날짜 문자열을 받아 요일을 반환합니다."""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        return weekdays[date_obj.weekday()]
    except ValueError:
        return ''

def get_time_emoji(time_str):
    """시간 문자열에 맞는 시계 이모지를 반환합니다."""
    return '🕐'  # 단순하게 하나의 시계 이모지만 사용

def get_next_10min_time():
    """현재 시간 기준으로 다음 10분 단위 시간을 반환합니다."""
    now = datetime.now()
    # 현재 시간에서 10분 후
    future_time = now + timedelta(minutes=10)
    
    # 10분 단위로 반올림
    minutes = future_time.minute
    rounded_minutes = ((minutes + 9) // 10) * 10  # 올림 처리
    
    if rounded_minutes >= 60:
        future_time = future_time.replace(hour=future_time.hour + 1, minute=0)
    else:
        future_time = future_time.replace(minute=rounded_minutes)
    
    return future_time.strftime('%H:%M')

def get_date_range_for_day(target_date):
    """특정 날짜의 시작과 끝 시간을 반환합니다."""
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # 타임존 정보가 없으면 추가
    if start_of_day.tzinfo is None:
        start_of_day = start_of_day.astimezone()
    if end_of_day.tzinfo is None:
        end_of_day = end_of_day.astimezone()
    
    return start_of_day, end_of_day

class DateParser:
    """날짜 파싱 관련 유틸리티 클래스"""
    
    @staticmethod
    def parse_query_date(text: str):
        """
        조회 명령어 텍스트를 파싱하여 날짜와 표시용 문자열을 반환합니다.
        
        Args:
            text: 사용자 입력 텍스트
            
        Returns:
            Tuple[Optional[datetime], str]: (파싱된 날짜, 표시용 문자열)
        """
        text = text.strip()
        
        if not text or text in ["오늘", "today"]:
            return datetime.now(), "오늘"
            
        elif text in ["내일", "tomorrow"]:
            return datetime.now() + timedelta(days=1), "내일"
            
        elif text == "주간":
            return None, "앞으로 7일간"
            
        else:
            # YYYY-MM-DD 형식으로 파싱 시도
            try:
                target_date = datetime.strptime(text, "%Y-%m-%d")
                return target_date, target_date.strftime("%Y년 %m월 %d일")
            except ValueError:
                raise ValueError("날짜 형식이 올바르지 않습니다")
    
    @staticmethod
    def is_weekly_query(text: str) -> bool:
        """주간 조회인지 확인"""
        return text.strip() == "주간" 
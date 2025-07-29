# exceptions.py
# 프로젝트에서 사용할 사용자 정의 예외를 정의합니다.

class ValidationError(Exception):
    """입력값 유효성 검사 실패 시 발생하는 예외"""
    pass

class ConflictError(Exception):
    """예약 시간 중복 등 충돌 발생 시 사용하는 예외"""
    
    def __init__(self, message: str, conflicting_reservations: list = None):
        """
        Args:
            message: 기본 에러 메시지
            conflicting_reservations: 충돌된 예약 정보 리스트
        """
        super().__init__(message)
        self.conflicting_reservations = conflicting_reservations or []
    
    def get_detailed_message(self) -> str:
        """충돌된 예약 정보를 포함한 상세 메시지를 반환합니다."""
        if not self.conflicting_reservations:
            return str(self)
        
        # 날짜별로 그룹화하여 중복 표시 방지
        date_groups = {}
        for reservation in self.conflicting_reservations:
            date_key = reservation.get('start_date', '날짜 정보 없음')
            if date_key not in date_groups:
                date_groups[date_key] = []
            date_groups[date_key].append(reservation)
        
        base_message = "예약 시간이 겹칩니다\n\n"
        
        # 날짜별로 정렬된 순서로 표시
        for date_key in sorted(date_groups.keys()):
            reservations = date_groups[date_key]
            
            # 날짜 헤더
            if date_key != '날짜 정보 없음':
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                    korean_date = date_obj.strftime('%Y년 %m월 %d일')
                    
                    # 요일 추가
                    weekdays = ['월', '화', '수', '목', '금', '토', '일']
                    korean_weekday = weekdays[date_obj.weekday()]
                    date_header = f"{korean_date} ({korean_weekday})"
                except:
                    date_header = f"{date_key}"
            else:
                date_header = f"{date_key}"
            
            base_message += f"📅 {date_header}\n"
            
            for reservation in reservations:
                time_info = f"{reservation['start_time']} ~ {reservation['end_time']}"
                team_info = f"[{reservation['team_name']}]"
                title_info = f"{reservation['title']}"
                
                base_message += f"  {time_info} {team_info} {title_info}\n"
            
            base_message += "\n"
        
        base_message += "다른 시간을 선택해주세요"
        return base_message

class NotionError(Exception):
    """Notion API 관련 작업 실패 시 발생하는 예외"""
    pass

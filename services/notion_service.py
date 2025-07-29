# services/notion_service.py
# Notion API와 통신하는 모든 로직을 담당합니다.

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from notion_client import Client

from config import get_notion_config, AppConfig
from models.reservation import ReservationData
from utils.logger import LoggerMixin, get_logger
from utils.error_handler import handle_exceptions
from utils.date_utils import get_date_range_for_day
from exceptions import NotionError

logger = get_logger(__name__)


class NotionService(LoggerMixin):
    """Notion API 서비스 클래스"""
    
    def __init__(self):
        """Notion 서비스 초기화"""
        self.config = get_notion_config()
        self.client = Client(auth=self.config.api_key)
        self.props = AppConfig.NOTION_PROPS
    
    @handle_exceptions(default_message="Notion DB 조회에 실패했습니다")
    def get_conflicting_reservations(
        self, 
        start_dt: datetime, 
        end_dt: datetime, 
        room_name: str, 
        exclude_page_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        주어진 시간과 겹치는 모든 예약을 조회합니다.
        
        Args:
            start_dt: 시작 시간
            end_dt: 종료 시간
            room_name: 회의실 이름
            exclude_page_id: 제외할 페이지 ID (수정 시 자기 자신 제외)
            
        Returns:
            List[Dict[str, Any]]: 충돌하는 예약 목록
            
        Raises:
            NotionError: Notion API 에러 발생 시
        """
        self._ensure_timezone(start_dt, end_dt)
        
        filter_conditions = self._build_conflict_filter(start_dt, end_dt, room_name)
        
        try:
            response = self.client.databases.query(
                database_id=self.config.database_id,
                filter=filter_conditions
            )
            results = response.get("results", [])
            
            # 자기 자신은 충돌 검사에서 제외
            if exclude_page_id:
                results = [res for res in results if res["id"] != exclude_page_id]
            
            self.log_info(f"충돌 검사 완료: {len(results)}개 찾음", 
                         room=room_name, 
                         time_range=f"{start_dt} ~ {end_dt}")
            return results
            
        except Exception as e:
            self.log_error(f"Notion DB 조회 중 오류", room=room_name)
            raise NotionError(f"Notion DB 조회에 실패했습니다: {e}")
    
    def parse_conflicting_reservations(self, conflicts: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        충돌된 예약 정보를 사용자 친화적인 형태로 파싱합니다.
        
        Args:
            conflicts: Notion에서 반환된 충돌 예약 목록
            
        Returns:
            List[Dict[str, str]]: 파싱된 충돌 예약 정보
        """
        parsed_conflicts = []
        
        for conflict in conflicts:
            try:
                props = conflict.get("properties", {})
                
                # 제목 추출
                title = "제목 없음"
                if self.props["title"] in props:
                    title_prop = props[self.props["title"]]
                    if title_prop.get("title"):
                        title = title_prop["title"][0]["text"]["content"]
                
                # 팀명 추출
                team_name = "팀 정보 없음"
                if self.props["team_name"] in props:
                    team_prop = props[self.props["team_name"]]
                    if team_prop.get("rich_text"):
                        team_name = team_prop["rich_text"][0]["text"]["content"]
                
                # 시작 시간 및 날짜 추출
                start_time = "시간 정보 없음"
                start_date = "날짜 정보 없음"
                start_dt = None
                if self.props["start_time"] in props:
                    start_prop = props[self.props["start_time"]]
                    if start_prop.get("date", {}).get("start"):
                        start_dt = datetime.fromisoformat(start_prop["date"]["start"].replace("Z", "+00:00"))
                        start_time = start_dt.strftime("%H:%M")
                        start_date = start_dt.strftime("%Y-%m-%d")
                
                # 종료 시간 추출
                end_time = "시간 정보 없음"
                if self.props["end_time"] in props:
                    end_prop = props[self.props["end_time"]]
                    if end_prop.get("date", {}).get("start"):
                        end_dt = datetime.fromisoformat(end_prop["date"]["start"].replace("Z", "+00:00"))
                        end_time = end_dt.strftime("%H:%M")
                
                parsed_conflicts.append({
                    "title": title,
                    "team_name": team_name,
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_date": start_date,
                    "start_dt": start_dt
                })
                
            except Exception as e:
                self.log_error(f"충돌 예약 파싱 실패: {e}")
                # 파싱 실패 시 기본 정보
                parsed_conflicts.append({
                    "title": "파싱 실패",
                    "team_name": "정보 없음",
                    "start_time": "정보 없음",
                    "end_time": "정보 없음",
                    "start_date": "정보 없음",
                    "start_dt": None
                })
        
        return parsed_conflicts
    
    @handle_exceptions(default_message="예약 생성에 실패했습니다")
    def create_reservation(self, reservation_data: ReservationData) -> Dict[str, Any]:
        """
        새로운 예약을 생성합니다.
        
        Args:
            reservation_data: 예약 정보
            
        Returns:
            Dict[str, Any]: 생성된 페이지 정보
            
        Raises:
            NotionError: Notion API 에러 발생 시
        """
        try:
            properties = self._build_reservation_properties(reservation_data)
            
            # 예약 생성 전 마지막으로 충돌 검사
            conflicts = self.get_conflicting_reservations(
                reservation_data.start_dt,
                reservation_data.end_dt,
                reservation_data.room_name
            )
            
            if conflicts:
                self.log_error("예약 생성 직전 충돌 발견",
                             room=reservation_data.room_name,
                             start=reservation_data.start_dt,
                             end=reservation_data.end_dt)
                raise NotionError("예약 생성 직전 시간 충돌이 발견되었습니다.")
            
            # Notion에 예약 생성
            response = self.client.pages.create(
                parent={"database_id": self.config.database_id},
                properties=properties
            )
            
            if not response or "id" not in response:
                self.log_error("Notion 응답에 page ID가 없음",
                             title=reservation_data.title,
                             room=reservation_data.room_name)
                raise NotionError("Notion에서 유효하지 않은 응답을 받았습니다.")
            
            self.log_info("예약 생성 성공", 
                         title=reservation_data.title,
                         room=reservation_data.room_name,
                         page_id=response["id"])
            return response
            
        except Exception as e:
            self.log_error("Notion 페이지 생성 중 오류",
                         title=reservation_data.title,
                         room=reservation_data.room_name,
                         error=str(e))
            raise NotionError(f"Notion 페이지 생성에 실패했습니다: {e}")
    
    @handle_exceptions(default_message="예약 조회에 실패했습니다")
    def get_reservations_by_date(self, target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        특정 날짜의 모든 예약을 조회합니다.
        
        Args:
            target_date: 조회할 날짜 (None이면 오늘)
            
        Returns:
            List[Dict[str, Any]]: 예약 목록
            
        Raises:
            NotionError: Notion API 에러 발생 시
        """
        if target_date is None:
            target_date = datetime.now()
        
        start_of_day, end_of_day = get_date_range_for_day(target_date)
        
        filter_conditions = {
            "and": [
                {
                    "property": self.props["start_time"],
                    "date": {"on_or_after": start_of_day.isoformat()}
                },
                {
                    "property": self.props["start_time"],
                    "date": {"on_or_before": end_of_day.isoformat()}
                }
            ]
        }
        
        try:
            response = self.client.databases.query(
                database_id=self.config.database_id,
                filter=filter_conditions,
                sorts=[
                    {
                        "property": self.props["start_time"],
                        "direction": "ascending"
                    }
                ]
            )
            
            results = response.get("results", [])
            self.log_info(f"날짜별 예약 조회 완료: {len(results)}개", 
                         date=target_date.strftime('%Y-%m-%d'))
            return results
            
        except Exception as e:
            self.log_error("날짜별 예약 조회 중 오류", date=target_date.strftime('%Y-%m-%d'))
            raise NotionError(f"Notion DB 조회에 실패했습니다: {e}")

    @handle_exceptions(default_message="예약 목록 조회에 실패했습니다")
    def get_upcoming_reservations(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """
        앞으로 N일간의 예약을 조회합니다.
        
        Args:
            days_ahead: 조회할 일수
            
        Returns:
            List[Dict[str, Any]]: 예약 목록
            
        Raises:
            NotionError: Notion API 에러 발생 시
        """
        now = datetime.now()
        if now.tzinfo is None:
            now = now.astimezone()
        
        end_date = now + timedelta(days=days_ahead)
        
        filter_conditions = {
            "and": [
                {
                    "property": self.props["start_time"],
                    "date": {"on_or_after": now.isoformat()}
                },
                {
                    "property": self.props["start_time"],
                    "date": {"on_or_before": end_date.isoformat()}
                }
            ]
        }
        
        try:
            response = self.client.databases.query(
                database_id=self.config.database_id,
                filter=filter_conditions,
                sorts=[
                    {
                        "property": self.props["start_time"],
                        "direction": "ascending"
                    }
                ]
            )
            
            results = response.get("results", [])
            self.log_info(f"향후 예약 조회 완료: {len(results)}개", days=days_ahead)
            return results
            
        except Exception as e:
            self.log_error("향후 예약 조회 중 오류", days=days_ahead)
            raise NotionError(f"Notion DB 조회에 실패했습니다: {e}")

    @handle_exceptions(default_message="예약 정보 조회에 실패했습니다")
    def get_reservation_by_id(self, page_id: str) -> Dict[str, Any]:
        """
        Page ID로 예약 정보를 조회합니다.
        
        Args:
            page_id: 페이지 ID
            
        Returns:
            Dict[str, Any]: 예약 정보
            
        Raises:
            NotionError: Notion API 에러 발생 시
        """
        try:
            response = self.client.pages.retrieve(page_id=page_id)
            self.log_info("예약 정보 조회 성공", page_id=page_id)
            return response
            
        except Exception as e:
            self.log_error("Notion 페이지 조회 중 오류", page_id=page_id)
            raise NotionError(f"Notion 페이지 조회에 실패했습니다: {e}")

    @handle_exceptions(default_message="예약 수정에 실패했습니다")
    def update_reservation(self, page_id: str, reservation_data: ReservationData) -> Dict[str, Any]:
        """
        기존 예약을 수정합니다.
        
        Args:
            page_id: 수정할 페이지 ID
            reservation_data: 새로운 예약 정보
            
        Returns:
            Dict[str, Any]: 수정된 페이지 정보
            
        Raises:
            NotionError: Notion API 에러 발생 시
        """
        try:
            properties = self._build_reservation_properties(reservation_data)
            
            response = self.client.pages.update(
                page_id=page_id,
                properties=properties
            )
            
            self.log_info("예약 수정 성공", 
                         page_id=page_id,
                         title=reservation_data.title,
                         room=reservation_data.room_name)
            return response
            
        except Exception as e:
            self.log_error("Notion 페이지 수정 중 오류", page_id=page_id)
            raise NotionError(f"Notion 페이지 수정에 실패했습니다: {e}")

    @handle_exceptions(default_message="예약 취소에 실패했습니다")
    def archive_page(self, page_id: str) -> Dict[str, Any]:
        """
        Notion 페이지를 보관(삭제) 처리합니다.
        
        Args:
            page_id: 보관할 페이지 ID
            
        Returns:
            Dict[str, Any]: 보관 처리 결과
            
        Raises:
            NotionError: Notion API 에러 발생 시
        """
        try:
            response = self.client.pages.update(page_id=page_id, archived=True)
            self.log_info("예약 취소 성공", page_id=page_id)
            return response
            
        except Exception as e:
            self.log_error("Notion 페이지 보관 중 오류", page_id=page_id)
            raise NotionError(f"Notion 페이지 보관에 실패했습니다: {e}")
    
    def get_reservations_in_range(self, start_dt: datetime, end_dt: datetime, room_id: str) -> List[Dict[str, Any]]:
        """
        특정 기간과 회의실의 예약을 조회합니다 (scheduler용).
        
        Args:
            start_dt: 시작 시간
            end_dt: 종료 시간
            room_id: 회의실 ID
            
        Returns:
            List[Dict[str, Any]]: 예약 목록
        """
        try:
            # room_id를 room_name으로 변환
            from config import AppConfig
            room_name = AppConfig.MEETING_ROOMS.get(room_id, {}).get("name", room_id)
            
            filter_conditions = {
                "and": [
                    {
                        "property": self.props["start_time"],
                        "date": {"on_or_after": start_dt.isoformat()}
                    },
                    {
                        "property": self.props["start_time"],
                        "date": {"on_or_before": end_dt.isoformat()}
                    },
                    {
                        "property": self.props["room_name"],
                        "rich_text": {"equals": room_name}
                    }
                ]
            }
            
            response = self.client.databases.query(
                database_id=self.config.database_id,
                filter=filter_conditions,
                sorts=[
                    {
                        "property": self.props["start_time"],
                        "direction": "ascending"
                    }
                ]
            )
            
            return response.get("results", [])
            
        except Exception as e:
            self.log_error("기간별 예약 조회 중 오류", room_id=room_id)
            raise NotionError(f"기간별 예약 조회에 실패했습니다: {e}")
    
    def _ensure_timezone(self, start_dt: datetime, end_dt: datetime) -> None:
        """타임존이 없는 경우 현재 타임존으로 설정"""
        if start_dt.tzinfo is None:
            start_dt = start_dt.astimezone()
        if end_dt.tzinfo is None:
            end_dt = end_dt.astimezone()
    
    def _build_conflict_filter(self, start_dt: datetime, end_dt: datetime, room_name: str) -> Dict[str, Any]:
        """
        충돌 검사를 위한 필터 조건 생성
        
        시간 충돌 조건:
        1. 기존 예약의 시작 시각이 새 예약의 종료 시각보다 빠르고 (기존.시작 < 새.종료)
        2. 기존 예약의 종료 시각이 새 예약의 시작 시각보다 늦은 경우 (기존.종료 > 새.시작)
        3. 단, 기존 예약의 종료 시각과 새 예약의 시작 시각이 같은 경우는 충돌로 보지 않음
        """
        return {
            "and": [
                {
                    "property": self.props["start_time"],
                    "date": {"before": end_dt.isoformat()}  # 기존.시작 < 새.종료
                },
                {
                    "property": self.props["end_time"],
                    "date": {"after": start_dt.isoformat()}  # 기존.종료 > 새.시작
                },
                {
                    "property": self.props["room_name"],
                    "rich_text": {"equals": room_name}
                }
            ]
        }
    
    def _build_reservation_properties(self, reservation_data: ReservationData) -> Dict[str, Any]:
        """예약 데이터를 Notion 속성 형태로 변환"""
        properties = {
            self.props["title"]: {"title": [{"text": {"content": reservation_data.title}}]},
            self.props["room_name"]: {"rich_text": [{"text": {"content": reservation_data.room_name}}]},
            self.props["start_time"]: {"date": {"start": reservation_data.start_dt.isoformat()}},
            self.props["end_time"]: {"date": {"start": reservation_data.end_dt.isoformat()}},
            self.props["team_name"]: {"rich_text": [{"text": {"content": reservation_data.team_name}}]},
        }

        """# 참석자 정보 추가
        if reservation_data.participants:
            properties[self.props["participants"]] = {
                "people": [{"id": p} for p in reservation_data.participants]
            }
        else:
            properties[self.props["participants"]] = {"people": []}
        
        # 반복 ID 추가 (있는 경우)
        if reservation_data.recurring_id:
            properties[self.props["recurring_id"]] = {
                "rich_text": [{"text": {"content": reservation_data.recurring_id}}]
            }
        """
        return properties


# 전역 서비스 인스턴스 (글로벌 함수들은 제거)
notion_service = NotionService()


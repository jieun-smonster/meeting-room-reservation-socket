# services/reservation_service.py
# 예약과 관련된 핵심 비즈니스 로직을 처리합니다.

import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from config import AppConfig
from models.reservation import ReservationData, ReservationModalData
from utils.logger import LoggerMixin, get_logger
from utils.error_handler import handle_exceptions
from utils.constants import NotionConstants
from exceptions import ValidationError, ConflictError, NotionError

from . import notion_service, slack_service

logger = get_logger(__name__)


class ReservationService(LoggerMixin):
    """예약 관리 서비스 클래스"""
    
    def __init__(self):
        """예약 서비스 초기화"""
        self.config = AppConfig()
    
    @handle_exceptions(default_message="모달 데이터 파싱에 실패했습니다")
    def parse_modal_data(self, view: Dict[str, Any], user_id: str) -> ReservationData:
        """
        모달 뷰 데이터를 ReservationData로 변환합니다.
        
        Args:
            view: Slack 모달 뷰 데이터
            user_id: 사용자 ID
            
        Returns:
            ReservationData: 파싱된 예약 데이터
            
        Raises:
            ValidationError: 입력 검증 실패 시
        """
        values = view["state"]["values"]
        
        try:
            # 필수 필드 추출
            title = values["title_block"]["title_input"]["value"]
            if not title or not title.strip():
                raise ValidationError("회의 제목을 입력해주세요.")
            
            # 회의실 정보
            selected_room = values["room_block"]["room_select"].get("selected_option")
            room_id = selected_room["value"] if selected_room else self.config.get_default_room_id()
            if not room_id or room_id not in self.config.MEETING_ROOMS:
                raise ValidationError("올바른 회의실을 선택해주세요.")
            room_name = self.config.MEETING_ROOMS[room_id]["name"]
            
            # 날짜 및 시간
            date_str = values["date_block"]["datepicker_action"]["selected_date"]
            start_time_str = values["start_time_block"]["start_time_action"]["selected_time"]
            end_time_str = values["end_time_block"]["end_time_action"]["selected_time"]
            
            start_dt = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M")
            
            if start_dt >= end_dt:
                raise ValidationError("종료 시간은 시작 시간보다 나중이어야 합니다.")
            
            # 팀 정보
            selected_team = values["team_block"]["team_select"].get("selected_option")
            if not selected_team:
                raise ValidationError("주관 팀을 선택해주세요.")
            team_id = selected_team["value"]
            if team_id not in self.config.TEAMS:
                raise ValidationError("올바른 팀을 선택해주세요.")
            team_name = self.config.TEAMS[team_id]
            
            # 참석자 (선택사항)
            participants = values["participants_block"]["participants_select"].get("selected_users", [])
            
            # 반복 설정 (선택사항)
            is_recurring = bool(values["recurring_block"]["recurring_checkbox"].get("selected_options"))
            
            # ReservationData 객체 생성
            return ReservationData(
                title=title.strip(),
                room_id=room_id,
                room_name=room_name,
                start_dt=start_dt,
                end_dt=end_dt,
                team_id=team_id,
                team_name=team_name,
                booker_id=user_id,
                participants=participants,
                booking_date=datetime.now().isoformat(),
                is_recurring=is_recurring
            )
            
        except (KeyError, TypeError, ValueError) as e:
            self.log_warning(f"Modal 데이터 파싱 오류: {e}", user_id=user_id)
            raise ValidationError("제출된 예약 정보에 오류가 있습니다. 모든 필수 항목을 올바르게 입력했는지 확인해주세요.")

    @handle_exceptions(default_message="예약 생성에 실패했습니다")
    def create_new_reservation(self, view: Dict[str, Any], user_id: str) -> None:
        """
        신규 예약을 생성합니다.
        
        Args:
            view: Slack 모달 뷰 데이터
            user_id: 사용자 ID
            
        Raises:
            ValidationError: 입력 검증 실패 시
            ConflictError: 시간 중복 시
            NotionError: Notion API 에러 시
        """
        # 모달 데이터 파싱
        reservation_data = self.parse_modal_data(view, user_id)
        
        # 시간 중복 검사
        conflicts = notion_service.get_conflicting_reservations(
            reservation_data.start_dt, 
            reservation_data.end_dt, 
            reservation_data.room_name
        )
        if conflicts:
            # 충돌된 예약 정보 파싱
            parsed_conflicts = notion_service.parse_conflicting_reservations(conflicts)
            raise ConflictError(
                "해당 시간은 이미 다른 예약과 겹칩니다.",
                conflicting_reservations=parsed_conflicts
            )

        # Notion에 예약 생성
        page = notion_service.create_reservation(reservation_data)
        reservation_data.page_id = page["id"]

        # 사용자에게 성공 알림
        slack_service.send_confirmation_message(user_id, reservation_data.to_dict())

        # 반복 예약 처리
        if reservation_data.is_recurring:
            self._create_recurring_reservations(reservation_data, user_id)
            
        self.log_info("예약 생성 완료", 
                     user_id=user_id,
                     title=reservation_data.title,
                     room=reservation_data.room_name,
                     page_id=reservation_data.page_id)
    
    def _create_recurring_reservations(self, base_reservation: ReservationData, user_id: str) -> None:
        """
        반복 예약을 생성합니다.
        
        Args:
            base_reservation: 기준 예약 데이터
            user_id: 사용자 ID
        """
        recurring_id = str(uuid.uuid4())
        base_reservation.recurring_id = recurring_id
        
        # 원본 예약에 반복 ID 업데이트
        notion_service.client.pages.update(
            page_id=base_reservation.page_id, 
            properties={
                notion_service.props["recurring_id"]: {"rich_text": [{"text": {"content": recurring_id}}]}
            }
        )
        time.sleep(NotionConstants.API_CALL_DELAY)

        created_count = 0
        for week_offset in range(1, self.config.RECURRING_WEEKS + 1):
            try:
                # 다음 주 예약 데이터 생성
                next_reservation = ReservationData(
                    title=base_reservation.title,
                    room_id=base_reservation.room_id,
                    room_name=base_reservation.room_name,
                    start_dt=base_reservation.start_dt + timedelta(weeks=week_offset),
                    end_dt=base_reservation.end_dt + timedelta(weeks=week_offset),
                    team_id=base_reservation.team_id,
                    team_name=base_reservation.team_name,
                    booker_id=base_reservation.booker_id,
                    participants=base_reservation.participants,
                    recurring_id=recurring_id,
                    booking_date=base_reservation.booking_date
                )
                
                # 충돌 검사
                conflicts = notion_service.get_conflicting_reservations(
                    next_reservation.start_dt, 
                    next_reservation.end_dt, 
                    next_reservation.room_name
                )
                
                if not conflicts:
                    time.sleep(NotionConstants.API_CALL_DELAY)
                    notion_service.create_reservation(next_reservation)
                    created_count += 1
                else:
                    self.log_warning(f"반복 예약 충돌로 생략: {week_offset}주차", 
                                   user_id=user_id,
                                   week=week_offset)
                    
            except Exception as e:
                self.log_error(f"반복 예약 생성 실패: {week_offset}주차", 
                             user_id=user_id, 
                             week=week_offset)
        
        if created_count > 0:
            slack_service.send_message(user_id, f"✅ 총 {created_count}개의 반복 예약을 추가로 생성했습니다.")
            self.log_info(f"반복 예약 생성 완료: {created_count}개", 
                         user_id=user_id,
                         count=created_count)

    @handle_exceptions(default_message="예약 정보 파싱에 실패했습니다")
    def parse_reservation_for_modal(self, reservation: Dict[str, Any]) -> ReservationModalData:
        """
        Notion 예약 정보를 모달 초기 데이터 형태로 변환합니다.
        
        Args:
            reservation: Notion에서 가져온 예약 정보
            
        Returns:
            ReservationModalData: 모달용 예약 데이터
        """
        try:
            properties = reservation.get("properties", {})
            modal_data = ReservationModalData()
            
            # 제목 추출
            title_prop = properties.get(self.config.NOTION_PROPS["title"], {})
            if title_prop.get("title"):
                modal_data.title = title_prop["title"][0]["text"]["content"]
            
            # 회의실 정보 추출 및 변환
            room_prop = properties.get(self.config.NOTION_PROPS["room_name"], {})
            if room_prop.get("rich_text"):
                room_name = room_prop["rich_text"][0]["text"]["content"]
                # room_name으로 room_id 찾기
                for room_id, room_info in self.config.MEETING_ROOMS.items():
                    if room_info["name"] == room_name:
                        modal_data.room_id = room_id
                        break
            
            # 시간 정보 추출
            start_prop = properties.get(self.config.NOTION_PROPS["start_time"], {})
            end_prop = properties.get(self.config.NOTION_PROPS["end_time"], {})
            
            if start_prop.get("date") and end_prop.get("date"):
                start_time = datetime.fromisoformat(start_prop["date"]["start"].replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end_prop["date"]["start"].replace("Z", "+00:00"))
                
                modal_data.date = start_time.strftime("%Y-%m-%d")
                modal_data.start_time = start_time.strftime("%H:%M")
                modal_data.end_time = end_time.strftime("%H:%M")
            
            # 팀 정보 추출 및 변환
            team_prop = properties.get(self.config.NOTION_PROPS["team_name"], {})
            if team_prop.get("rich_text"):
                team_name = team_prop["rich_text"][0]["text"]["content"]
                # team_name으로 team_id 찾기
                for team_id, team_name_config in self.config.TEAMS.items():
                    if team_name_config == team_name:
                        modal_data.team_id = team_id
                        break
            
            # 참석자 추출
            participants_prop = properties.get(self.config.NOTION_PROPS["participants"], {})
            if participants_prop.get("people"):
                participants = []
                for person in participants_prop["people"]:
                    if person.get("id"):
                        participants.append(person["id"])
                modal_data.participants = participants
            
            return modal_data
            
        except Exception as e:
            self.log_error(f"예약 정보 파싱 중 오류: {e}")
            return ReservationModalData()

    @handle_exceptions(default_message="예약 수정에 실패했습니다")
    def update_existing_reservation(self, view: Dict[str, Any], user_id: str, page_id: str) -> None:
        """
        기존 예약을 수정합니다.
        
        Args:
            view: Slack 모달 view 데이터
            user_id: 사용자 ID
            page_id: 수정할 예약의 Notion 페이지 ID
        """
        values = view["state"]["values"]
        
        # timepicker 방식으로 값 읽기
        title = values["title_block"]["title_input"]["value"]
        room_id = values["room_block"]["room_select"]["selected_option"]["value"]
        date_str = values["date_block"]["datepicker_action"]["selected_date"]
        start_time_str = values["start_time_block"]["start_time_action"]["selected_time"]
        end_time_str = values["end_time_block"]["end_time_action"]["selected_time"]
        team_id = values["team_block"]["team_select"]["selected_option"]["value"]
        participants = values["participants_block"]["participants_select"].get("selected_users", [])
        recurring = values.get("recurring_block", {}).get("recurring_checkbox", {}).get("selected_options", [])
        
        # 기존 예약 데이터 생성 로직과 동일하게 처리
        reservation_data = self._create_reservation_data(
            title, room_id, date_str, start_time_str, end_time_str, 
            team_id, participants, [], user_id
        )
        reservation_data.page_id = page_id
        
        # 시간 중복 검사 (자기 자신 제외)
        conflicts = notion_service.get_conflicting_reservations(
            reservation_data.start_dt, 
            reservation_data.end_dt, 
            reservation_data.room_name,
            exclude_page_id=page_id
        )
        if conflicts:
            # 충돌된 예약 정보 파싱
            parsed_conflicts = notion_service.parse_conflicting_reservations(conflicts)
            raise ConflictError(
                "해당 시간은 이미 다른 예약과 겹칩니다.",
                conflicting_reservations=parsed_conflicts
            )
        
        # Notion에서 예약 수정
        notion_service.update_reservation(page_id, reservation_data)
        
        # 사용자에게 수정 완료 알림
        slack_service.send_update_confirmation_message(user_id, reservation_data.to_dict())
        
        self.log_info("예약 수정 완료", 
                     user_id=user_id,
                     page_id=page_id,
                     title=reservation_data.title,
                     room=reservation_data.room_name)


# 전역 서비스 인스턴스
reservation_service_instance = ReservationService()

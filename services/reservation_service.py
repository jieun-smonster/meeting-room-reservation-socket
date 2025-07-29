# services/reservation_service.py
# 예약과 관련된 핵심 비즈니스 로직을 처리합니다.

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from config import AppConfig
from models.reservation import ReservationData, ReservationModalData
from utils.logger import LoggerMixin, get_logger
from utils.error_handler import handle_exceptions
from utils.constants import NotionConstants
from exceptions import ValidationError, ConflictError, NotionError

from . import notion_service, slack_service

logger = get_logger(__name__)

# 한국 시간대 설정 (UTC+9)
KST = timezone(timedelta(hours=9))


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
            
            # 한국 시간대(KST)로 datetime 객체 생성
            start_dt = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
            end_dt = datetime.strptime(f"{date_str} {end_time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
            
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
            
            """# 반복 설정 (선택사항)
            recurring_options = values["recurring_block"]["recurring_checkbox"].get("selected_options", [])
            is_recurring = bool(recurring_options and recurring_options[0]["value"] == "weekly")
            
            # 반복 주수 (반복 설정이 체크된 경우)
            recurring_weeks = 4  # 기본값
            if is_recurring:
                recurring_weeks_option = values["recurring_weeks_block"]["recurring_weeks_select"].get("selected_option")
                if recurring_weeks_option:
                    recurring_weeks = int(recurring_weeks_option["value"])
                else:
                    raise ValidationError("반복 예약을 선택한 경우 반복 주수를 선택해주세요.")
            """
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
                #participants=participants,
                booking_date=datetime.now().isoformat(),
                #is_recurring=is_recurring,
                #recurring_weeks=recurring_weeks
            )
            
        except (KeyError, TypeError, ValueError) as e:
            self.log_warning(f"Modal 데이터 파싱 오류: {e}", user_id=user_id)
            raise ValidationError("제출된 예약 정보에 오류가 있습니다. 모든 필수 항목을 올바르게 입력했는지 확인해주세요.")

    def _validate_recurring_reservations(self, base_reservation: ReservationData, user_id: str) -> None:
        """
        반복 예약의 모든 주차에 대해 충돌 검사를 수행합니다.
        
        Args:
            base_reservation: 기준 예약 데이터
            user_id: 사용자 ID
            
        Raises:
            ConflictError: 충돌이 발견된 경우
        """
        recurring_weeks = base_reservation.recurring_weeks
        conflict_details = []
        
        # 모든 반복 예약 데이터 생성
        all_reservations = [base_reservation]
        
        for week_offset in range(1, recurring_weeks):
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
                recurring_id=base_reservation.recurring_id,
                booking_date=base_reservation.booking_date,
                # is_recurring=False,
                # recurring_weeks=recurring_weeks
            )
            all_reservations.append(next_reservation)
        
        # 모든 예약에 대해 충돌 검사
        for i, reservation in enumerate(all_reservations):
            conflicts = notion_service.get_conflicting_reservations(
                reservation.start_dt, 
                reservation.end_dt, 
                reservation.room_name
            )
            
            if conflicts:
                parsed_conflicts = notion_service.parse_conflicting_reservations(conflicts)
                for conflict in parsed_conflicts:
                    conflict_detail = (
                        f"{i+1}주차 ({reservation.start_dt.strftime('%Y-%m-%d %H:%M')}) - "
                        f"충돌: {conflict['start_date']} {conflict['start_time']}~{conflict['end_time']} "
                        f"[{conflict['team_name']}] {conflict['title']}"
                    )
                    conflict_details.append(conflict_detail)
        
        # 충돌이 있으면 예외 발생
        if conflict_details:
            conflict_message = "다음 일정과 충돌합니다:\n" + "\n".join(conflict_details)
            raise ConflictError(
                conflict_message,
                conflicting_reservations=[]  # 상세 정보는 메시지에 포함
            )

    @handle_exceptions(default_message="예약 생성에 실패했습니다")
    def create_new_reservation(self, view_or_data, user_id: str) -> None:
        """
        신규 예약을 생성합니다.
        
        Args:
            view_or_data: Slack 모달 뷰 데이터 또는 이미 파싱된 ReservationData
            user_id: 사용자 ID
            
        Raises:
            ValidationError: 입력 검증 실패 시
            ConflictError: 시간 중복 시
            NotionError: Notion API 에러 시
        """
        # 이미 파싱된 데이터인지 확인
        if isinstance(view_or_data, ReservationData):
            reservation_data = view_or_data
        else:
            # 모달 데이터 파싱
            reservation_data = self.parse_modal_data(view_or_data, user_id)
        
        # 반복 예약인 경우 반복 ID 미리 생성
        # if reservation_data.is_recurring:
        #     reservation_data.recurring_id = str(uuid.uuid4())
        
        # 반복 예약인 경우 트랜잭션 방식으로 처리
        # if reservation_data.is_recurring:
        #     self._create_recurring_reservations_transaction(reservation_data, user_id)
        # else:
        # 단일 예약 처리
        conflicts = notion_service.get_conflicting_reservations(
            reservation_data.start_dt, 
            reservation_data.end_dt, 
            reservation_data.room_name
        )
        if conflicts:
            parsed_conflicts = notion_service.parse_conflicting_reservations(conflicts)
            raise ConflictError(
                "해당 시간은 이미 다른 예약과 겹칩니다.",
                conflicting_reservations=parsed_conflicts
            )

        try:
            page = notion_service.create_reservation(reservation_data)
            reservation_data.page_id = page["id"]
            
            slack_service.send_confirmation_message(user_id, reservation_data.to_dict())
            
            self.log_info("단일 예약 생성 완료", 
                         user_id=user_id,
                         title=reservation_data.title,
                         room=reservation_data.room_name,
                         page_id=reservation_data.page_id)
                         
        except Exception as e:
            self.log_error(f"단일 예약 생성 중 오류 발생: {e}", 
                         user_id=user_id,
                         title=reservation_data.title,
                         room=reservation_data.room_name,
                         exc_info=True)
            raise

    @handle_exceptions(default_message="예약 생성에 실패했습니다")
    def create_new_reservation_without_validation(self, reservation_data: ReservationData, user_id: str) -> None:
        """
        검증 없이 예약을 생성합니다 (이미 검증이 완료된 경우).
        
        Args:
            reservation_data: 검증된 예약 데이터
            user_id: 사용자 ID
        """
        # 반복 예약인 경우 트랜잭션 방식으로 처리
        # if reservation_data.is_recurring:
        #     self._create_recurring_reservations_without_validation(reservation_data, user_id)
        # else:
        # 단일 예약 처리
        try:
            page = notion_service.create_reservation(reservation_data)
            reservation_data.page_id = page["id"]
            
            slack_service.send_confirmation_message(user_id, reservation_data.to_dict())
            
            self.log_info("단일 예약 생성 완료", 
                         user_id=user_id,
                         title=reservation_data.title,
                         room=reservation_data.room_name,
                         page_id=reservation_data.page_id)
                         
        except Exception as e:
            self.log_error(f"단일 예약 생성 중 오류 발생: {e}", 
                         user_id=user_id,
                         title=reservation_data.title,
                         room=reservation_data.room_name,
                         exc_info=True)
            raise

    def _create_recurring_reservations_transaction(self, base_reservation: ReservationData, user_id: str) -> None:
        """
        트랜잭션 방식으로 반복 예약을 생성합니다.
        충돌이 발생하면 모든 예약을 롤백합니다.
        
        Args:
            base_reservation: 기준 예약 데이터
            user_id: 사용자 ID
        """
        try:
            recurring_id = base_reservation.recurring_id
            recurring_weeks = base_reservation.recurring_weeks
            
            # 모든 반복 예약 데이터 미리 생성
            all_reservations = []
            conflict_details = []
            
            # 원본 예약 포함
            all_reservations.append(base_reservation)
            
            # 반복 예약들 생성
            for week_offset in range(1, recurring_weeks):
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
                    booking_date=base_reservation.booking_date,
                    # is_recurring=False,
                    # recurring_weeks=recurring_weeks
                )
                all_reservations.append(next_reservation)
            
            # 모든 예약에 대해 충돌 검사
            for i, reservation in enumerate(all_reservations):
                conflicts = notion_service.get_conflicting_reservations(
                    reservation.start_dt, 
                    reservation.end_dt, 
                    reservation.room_name
                )
                
                if conflicts:
                    parsed_conflicts = notion_service.parse_conflicting_reservations(conflicts)
                    for conflict in parsed_conflicts:
                        conflict_detail = (
                            f"{i+1}주차 ({reservation.start_dt.strftime('%Y-%m-%d %H:%M')}) - "
                            f"충돌: {conflict['start_date']} {conflict['start_time']}~{conflict['end_time']} "
                            f"[{conflict['team_name']}] {conflict['title']}"
                        )
                        conflict_details.append(conflict_detail)
            
            # 충돌이 있으면 예외 발생
            if conflict_details:
                conflict_message = "다음 일정과 충돌합니다:\n" + "\n".join(conflict_details)
                raise ConflictError(
                    conflict_message,
                    conflicting_reservations=[]  # 상세 정보는 메시지에 포함
                )
            
            # 충돌이 없으면 모든 예약 생성
            created_pages = []
            try:
                for i, reservation in enumerate(all_reservations):
                    page = notion_service.create_reservation(reservation)
                    created_pages.append(page["id"])
                    reservation.page_id = page["id"]
                    
                    self.log_info(f"{i+1}주차 반복 예약 생성 성공",
                                user_id=user_id,
                                title=reservation.title,
                                start=reservation.start_dt.strftime("%Y-%m-%d %H:%M"),
                                page_id=page["id"])
                    
                    time.sleep(NotionConstants.API_CALL_DELAY)
                
                # 모든 예약 생성 성공 - 이제 메시지 전송
                self.log_info(f"반복 예약 트랜잭션 성공: {len(all_reservations)}개",
                            user_id=user_id,
                            recurring_id=recurring_id,
                            weeks=recurring_weeks)
                
                # 성공 메시지 전송 (실패해도 예약은 유지)
                try:
                    slack_service.send_confirmation_message(user_id, base_reservation.to_dict())
                    slack_service.send_message(
                        user_id,
                        f"✅ 총 {len(all_reservations)}개의 반복 예약이 성공적으로 생성되었습니다."
                    )
                except Exception as message_error:
                    self.log_error(f"성공 메시지 전송 실패 (예약은 성공): {message_error}",
                                 user_id=user_id,
                                 created_count=len(created_pages))
                    # 메시지 전송 실패는 예약 생성과 별개로 처리
                            
            except Exception as create_error:
                # 예약 생성 중 오류 발생 시에만 롤백
                self.log_error(f"반복 예약 생성 중 오류, 롤백 시작: {create_error}",
                             user_id=user_id,
                             created_count=len(created_pages))
                
                # 이미 생성된 예약들 롤백
                for page_id in created_pages:
                    try:
                        notion_service.archive_page(page_id)
                        time.sleep(NotionConstants.API_CALL_DELAY)
                    except Exception as rollback_error:
                        self.log_error(f"롤백 실패: {rollback_error}", page_id=page_id)
                
                # 롤백 완료 후 오류 메시지 전송
                try:
                    slack_service.send_message(
                        user_id,
                        "❌ 반복 예약 생성 중 오류가 발생하여 모든 예약이 취소되었습니다."
                    )
                except Exception as rollback_message_error:
                    self.log_error(f"롤백 메시지 전송 실패: {rollback_message_error}")
                
                raise NotionError(f"반복 예약 생성 실패: {create_error}")
                
        except ConflictError:
            # 충돌 에러는 그대로 전파 (모달에서 처리)
            raise
        except Exception as e:
            self.log_error(f"반복 예약 트랜잭션 중 예상치 못한 오류: {e}",
                         user_id=user_id,
                         title=base_reservation.title,
                         exc_info=True)
            
            # 예상치 못한 오류 메시지 전송
            try:
                slack_service.send_message(
                    user_id,
                    "❌ 반복 예약 처리 중 예상치 못한 오류가 발생했습니다. 관리자에게 문의해주세요."
                )
            except Exception as error_message_error:
                self.log_error(f"오류 메시지 전송 실패: {error_message_error}")
            
            raise

    def _create_recurring_reservations_without_validation(self, base_reservation: ReservationData, user_id: str) -> None:
        """
        검증 없이 반복 예약을 생성합니다 (이미 검증이 완료된 경우).
        
        Args:
            base_reservation: 기준 예약 데이터
            user_id: 사용자 ID
        """
        try:
            recurring_id = base_reservation.recurring_id
            recurring_weeks = base_reservation.recurring_weeks
            
            # 모든 반복 예약 데이터 생성
            all_reservations = [base_reservation]
            
            for week_offset in range(1, recurring_weeks):
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
                    booking_date=base_reservation.booking_date,
                    # is_recurring=False,
                    # recurring_weeks=recurring_weeks
                )
                all_reservations.append(next_reservation)
            
            # 모든 예약 생성
            created_pages = []
            try:
                for i, reservation in enumerate(all_reservations):
                    page = notion_service.create_reservation(reservation)
                    created_pages.append(page["id"])
                    reservation.page_id = page["id"]
                    
                    self.log_info(f"{i+1}주차 반복 예약 생성 성공",
                                user_id=user_id,
                                title=reservation.title,
                                start=reservation.start_dt.strftime("%Y-%m-%d %H:%M"),
                                page_id=page["id"])
                    
                    time.sleep(NotionConstants.API_CALL_DELAY)
                
                # 모든 예약 생성 성공
                self.log_info(f"반복 예약 트랜잭션 성공: {len(all_reservations)}개",
                            user_id=user_id,
                            recurring_id=recurring_id,
                            weeks=recurring_weeks)
                
                # 성공 메시지 전송
                try:
                    slack_service.send_confirmation_message(user_id, base_reservation.to_dict())
                    slack_service.send_message(
                        user_id,
                        f"✅ 총 {len(all_reservations)}개의 반복 예약이 성공적으로 생성되었습니다."
                    )
                except Exception as message_error:
                    self.log_error(f"성공 메시지 전송 실패 (예약은 성공): {message_error}",
                                 user_id=user_id,
                                 created_count=len(created_pages))
                            
            except Exception as create_error:
                # 예약 생성 중 오류 발생 시 롤백
                self.log_error(f"반복 예약 생성 중 오류, 롤백 시작: {create_error}",
                             user_id=user_id,
                             created_count=len(created_pages))
                
                # 이미 생성된 예약들 롤백
                for page_id in created_pages:
                    try:
                        notion_service.archive_page(page_id)
                        time.sleep(NotionConstants.API_CALL_DELAY)
                    except Exception as rollback_error:
                        self.log_error(f"롤백 실패: {rollback_error}", page_id=page_id)
                
                # 롤백 완료 후 오류 메시지 전송
                try:
                    slack_service.send_message(
                        user_id,
                        "❌ 반복 예약 생성 중 오류가 발생하여 모든 예약이 취소되었습니다."
                    )
                except Exception as rollback_message_error:
                    self.log_error(f"롤백 메시지 전송 실패: {rollback_message_error}")
                
                raise NotionError(f"반복 예약 생성 실패: {create_error}")
                
        except Exception as e:
            self.log_error(f"반복 예약 트랜잭션 중 예상치 못한 오류: {e}",
                         user_id=user_id,
                         title=base_reservation.title,
                         exc_info=True)
            
            # 예상치 못한 오류 메시지 전송
            try:
                slack_service.send_message(
                    user_id,
                    "❌ 반복 예약 처리 중 예상치 못한 오류가 발생했습니다. 관리자에게 문의해주세요."
                )
            except Exception as error_message_error:
                self.log_error(f"오류 메시지 전송 실패: {error_message_error}")
            
            raise

    @handle_exceptions(default_message="예약 정보 파싱에 실패했습니다")
    def parse_reservation_for_modal(self, reservation: Dict[str, Any]) -> ReservationModalData:
        """
        Notion 예약 정보를 모달용 데이터로 변환합니다.
        
        Args:
            reservation: Notion에서 조회한 예약 정보
            
        Returns:
            ReservationModalData: 모달용 예약 데이터
            
        Raises:
            ValidationError: 데이터 파싱 실패 시
        """
        try:
            properties = reservation.get("properties", {})
            
            # 제목 추출
            title = ""
            if self.config.NOTION_PROPS["title"] in properties:
                title_prop = properties[self.config.NOTION_PROPS["title"]]
                if title_prop.get("title"):
                    title = title_prop["title"][0]["text"]["content"]
            
            # 회의실 정보 추출
            room_id = ""
            if self.config.NOTION_PROPS["room_name"] in properties:
                room_prop = properties[self.config.NOTION_PROPS["room_name"]]
                if room_prop.get("rich_text"):
                    room_name = room_prop["rich_text"][0]["text"]["content"]
                    # room_name으로 room_id 찾기
                    for rid, room_info in self.config.MEETING_ROOMS.items():
                        if room_info["name"] == room_name:
                            room_id = rid
                            break
            
            # 시작 시간 추출
            date = ""
            start_time = ""
            if self.config.NOTION_PROPS["start_time"] in properties:
                start_prop = properties[self.config.NOTION_PROPS["start_time"]]
                if start_prop.get("date", {}).get("start"):
                    # UTC로 저장된 시간을 한국 시간대로 변환
                    start_dt = datetime.fromisoformat(start_prop["date"]["start"].replace("Z", "+00:00"))
                    start_dt_kst = start_dt.astimezone(KST)
                    date = start_dt_kst.strftime("%Y-%m-%d")
                    start_time = start_dt_kst.strftime("%H:%M")
            
            # 종료 시간 추출
            end_time = ""
            if self.config.NOTION_PROPS["end_time"] in properties:
                end_prop = properties[self.config.NOTION_PROPS["end_time"]]
                if end_prop.get("date", {}).get("start"):
                    # UTC로 저장된 시간을 한국 시간대로 변환
                    end_dt = datetime.fromisoformat(end_prop["date"]["start"].replace("Z", "+00:00"))
                    end_dt_kst = end_dt.astimezone(KST)
                    end_time = end_dt_kst.strftime("%H:%M")
            
            # 팀 정보 추출
            team_id = ""
            if self.config.NOTION_PROPS["team_name"] in properties:
                team_prop = properties[self.config.NOTION_PROPS["team_name"]]
                if team_prop.get("rich_text"):
                    team_name = team_prop["rich_text"][0]["text"]["content"]
                    # team_name으로 team_id 찾기
                    for tid, tname in self.config.TEAMS.items():
                        if tname == team_name:
                            team_id = tid
                            break
            
            # 참석자 정보 추출
            # participants = []
            # if self.config.NOTION_PROPS["participants"] in properties:
            #     participants_prop = properties[self.config.NOTION_PROPS["participants"]]
            #     if participants_prop.get("people"):
            #         participants = [p["id"] for p in participants_prop["people"]]
            
            # 반복 ID 확인 (반복 예약 여부 판단)
            # is_recurring = False
            # recurring_weeks = "4"  # 기본값
            # if self.config.NOTION_PROPS["recurring_id"] in properties:
            #     recurring_prop = properties[self.config.NOTION_PROPS["recurring_id"]]
            #     if recurring_prop.get("rich_text") and recurring_prop["rich_text"]:
            #         recurring_id = recurring_prop["rich_text"][0]["text"]["content"]
            #         is_recurring = bool(recurring_id.strip())
            #         # 반복 예약인 경우 기본 주수를 설정 (실제로는 DB에서 조회해야 하지만 여기서는 기본값 사용)
            #         if is_recurring:
            #             recurring_weeks = "4"  # 기본값, 실제 구현에서는 별도 필드에서 조회
            
            modal_data = ReservationModalData(
                title=title,
                room_id=room_id,
                date=date,
                start_time=start_time,
                end_time=end_time,
                team_id=team_id,
                #participants=participants,
                page_id=reservation.get("id", "")
            )
            
            # 반복 설정 정보 추가
            # modal_data.is_recurring = is_recurring
            # modal_data.recurring_weeks = recurring_weeks
            
            return modal_data
            
        except Exception as e:
            self.log_error(f"예약 정보 파싱 중 오류: {e}")
            raise ValidationError(f"예약 정보를 불러올 수 없습니다: {e}")

    @handle_exceptions(default_message="예약 수정에 실패했습니다")
    def update_existing_reservation(self, view_or_data, user_id: str, page_id: str) -> None:
        """
        기존 예약을 수정합니다.
        
        Args:
            view_or_data: Slack 모달 view 데이터 또는 이미 파싱된 ReservationData
            user_id: 사용자 ID
            page_id: 수정할 예약의 Notion 페이지 ID
        """
        # 이미 파싱된 데이터인지 확인
        if isinstance(view_or_data, ReservationData):
            reservation_data = view_or_data
        else:
            # 모달 데이터 파싱
            reservation_data = self.parse_modal_data(view_or_data, user_id)
            
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

        try:
            # Notion에서 예약 수정
            notion_service.update_reservation(page_id, reservation_data)
            
            self.log_info("예약 수정 성공", 
                         user_id=user_id,
                         page_id=page_id,
                         title=reservation_data.title,
                         room=reservation_data.room_name)
                         
        except Exception as e:
            self.log_error(f"예약 수정 중 오류 발생: {e}", 
                         user_id=user_id,
                         page_id=page_id,
                         title=reservation_data.title,
                         exc_info=True)
            raise

    @handle_exceptions(default_message="예약 수정에 실패했습니다")
    def update_existing_reservation_without_validation(self, reservation_data: ReservationData, user_id: str, page_id: str) -> None:
        """
        검증 없이 예약을 수정합니다 (이미 검증이 완료된 경우).
        
        Args:
            reservation_data: 검증된 예약 데이터
            user_id: 사용자 ID
            page_id: 수정할 예약의 Notion 페이지 ID
        """
        try:
            # Notion에서 예약 수정
            notion_service.update_reservation(page_id, reservation_data)
            
            self.log_info("예약 수정 성공", 
                         user_id=user_id,
                         page_id=page_id,
                         title=reservation_data.title,
                         room=reservation_data.room_name)
                         
        except Exception as e:
            self.log_error(f"예약 수정 중 오류 발생: {e}", 
                         user_id=user_id,
                         page_id=page_id,
                         title=reservation_data.title,
                         exc_info=True)
            raise


# 전역 서비스 인스턴스
reservation_service_instance = ReservationService()

# 전역 함수들 (하위 호환성을 위해)
def create_new_reservation(view, user_id):
    return reservation_service_instance.create_new_reservation(view, user_id)

def update_existing_reservation(view, user_id, page_id):
    return reservation_service_instance.update_existing_reservation(view, user_id, page_id)

def parse_reservation_for_modal(reservation):
    return reservation_service_instance.parse_reservation_for_modal(reservation)

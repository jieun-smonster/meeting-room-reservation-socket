# app.py
# Slack Bolt 앱을 소켓 모드로 초기화하고, 모든 요청을 처리하는 메인 파일입니다.

from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from dotenv import load_dotenv
from typing import Dict, Any
import uuid

# .env 파일에서 환경 변수 로드
load_dotenv()

# 설정 및 유틸리티 임포트
from config import get_slack_config
from utils.logger import setup_logging, get_logger
from utils.error_handler import ErrorHandler
from utils.date_utils import DateParser
from utils.constants import SlackCommands, ErrorMessages, SuccessMessages, CallbackIds, ActionIds

# 서비스, 뷰, 예외 임포트
from views.reservation_view import build_reservation_modal
from services import reservation_service, notion_service, slack_service
from exceptions import ValidationError, ConflictError, NotionError

# 로깅 설정
setup_logging()
logger = get_logger(__name__)

# Slack 설정 로드
slack_config = get_slack_config()

# Bolt 앱 초기화
app = App(token=slack_config.bot_token)

# --- Slack Home Tab Handler ---
@app.event("app_home_opened")
def handle_app_home_opened(event, client):
    """사용자가 앱의 Home Tab을 열었을 때 호출되는 핸들러입니다."""
    user_id = event["user"]
    
    try:
        # Home Tab View 업데이트
        slack_service.update_home_tab(client, user_id)
        logger.info(f"Home Tab 업데이트 성공 - 사용자: {user_id}")
        
    except Exception as e:
        logger.error(f"Home Tab 업데이트 실패 - 사용자: {user_id}: {e}")

# --- Slack Command Handlers ---
@app.command(SlackCommands.RESERVATION)
def handle_reservation_command(ack, body, client):
    """회의실 예약 모달을 여는 명령어를 처리합니다."""
    ack()
    
    user_id = body["user_id"]
    trigger_id = body["trigger_id"]
    
    try:
        client.views_open(
            trigger_id=trigger_id,
            view=build_reservation_modal()
        )
        
    except Exception as e:
        logger.error(f"예약 모달 열기 실패 - 사용자: {user_id}: {e}")
        ErrorHandler.handle_modal_error(
            user_id=user_id,
            trigger_id=trigger_id,
            error=e,
            send_error_modal_func=slack_service.send_error_message,
            context="예약 모달 열기"
        )

@app.command(SlackCommands.QUERY)
def handle_query_command(ack, body, client):
    """회의실 예약 현황 조회 명령어를 처리합니다."""
    ack()
    
    user_id = body["user_id"]
    channel_id = body["channel_id"]
    channel_name = body.get("channel_name", "")
    text = body.get("text", "").strip()
    
    # DM인 경우 user_id를 사용, 그렇지 않으면 channel_id 사용
    target_channel = user_id if channel_name == "directmessage" else channel_id
    
    try:
        # 날짜 파라미터 파싱
        if DateParser.is_weekly_query(text):
            # 주간 조회
            reservations = notion_service.get_upcoming_reservations(days_ahead=7)
            slack_service.send_reservation_status(target_channel, reservations, "앞으로 7일간")
            return
        
        try:
            target_date, query_date_str = DateParser.parse_query_date(text)
        except ValueError:
            slack_service.send_message(user_id, ErrorMessages.INVALID_DATE_FORMAT)
            return
        
        # 예약 현황 조회
        if target_date:
            reservations = notion_service.get_reservations_by_date(target_date)
        else:
            reservations = notion_service.get_upcoming_reservations(days_ahead=7)
            
        # 결과 전송
        slack_service.send_reservation_status(target_channel, reservations, query_date_str)
        
    except Exception as e:
        logger.error(f"예약 조회 실패 - 사용자: {user_id}: {e}")
        ErrorHandler.handle_slack_command_error(
            user_id=user_id,
            error=e,
            send_message_func=slack_service.send_message,
            context="예약 현황 조회"
        )

# --- Slack View Handlers ---
@app.view(CallbackIds.RESERVATION_SUBMIT)
def handle_reservation_modal_submission(ack, body, client, logger):
    """예약 생성 모달 제출을 처리합니다."""
    view = body["view"]
    user_id = body["user"]["id"]
    
    try:
        # 먼저 입력값 검증 수행
        reservation_data = reservation_service.parse_modal_data(view, user_id)
        
        # 반복 예약인 경우 반복 ID 미리 생성
        # if reservation_data.is_recurring:
        #     reservation_data.recurring_id = str(uuid.uuid4())
        
        # 충돌 검사 수행
        # if reservation_data.is_recurring:
        #     # 반복 예약의 경우 모든 주차에 대해 충돌 검사
        #     try:
        #         reservation_service._validate_recurring_reservations(reservation_data, user_id)
        #     except ConflictError as e:
        #         # 반복 예약 충돌 시 모달 업데이트
        #         modal_data = {
        #             "title": view["state"]["values"]["title_block"]["title_input"]["value"],
        #             "room_id": view["state"]["values"]["room_block"]["room_select"]["selected_option"]["value"] if view["state"]["values"]["room_block"]["room_select"].get("selected_option") else None,
        #             "date": view["state"]["values"]["date_block"]["datepicker_action"]["selected_date"],
        #             "start_time": view["state"]["values"]["start_time_block"]["start_time_action"]["selected_time"],
        #             "end_time": view["state"]["values"]["end_time_block"]["end_time_action"]["selected_time"],
        #             "team_id": view["state"]["values"]["team_block"]["team_select"]["selected_option"]["value"] if view["state"]["values"]["team_block"]["team_select"].get("selected_option") else None,
        #             "participants": view["state"]["values"]["participants_block"]["participants_select"].get("selected_users", []),
        #             "is_recurring": bool(view["state"]["values"]["recurring_block"]["recurring_checkbox"].get("selected_options")),
        #             "recurring_weeks": view["state"]["values"]["recurring_weeks_block"]["recurring_weeks_select"]["selected_option"]["value"] if view["state"]["values"]["recurring_weeks_block"]["recurring_weeks_select"].get("selected_option") else "4"
        #         }
        #         
        #         conflict_info = {"message": str(e)}
        #         
        #         updated_modal = build_reservation_modal(
        #             initial_data=modal_data,
        #             is_edit=False,
        #             conflict_info=conflict_info
        #         )
        #         
        #         ack(response_action="update", view=updated_modal)
        #         logger.info(f"반복 예약 충돌 - 모달 업데이트 - 사용자: {user_id}")
        #         return
        # else:
        # 단일 예약의 경우 일반 충돌 검사
        conflicts = notion_service.get_conflicting_reservations(
            reservation_data.start_dt, 
            reservation_data.end_dt, 
            reservation_data.room_name
        )
        if conflicts:
            parsed_conflicts = notion_service.parse_conflicting_reservations(conflicts)
            
            # 단일 예약 충돌 시 모달 업데이트
            modal_data = {
                "title": view["state"]["values"]["title_block"]["title_input"]["value"],
                "room_id": view["state"]["values"]["room_block"]["room_select"]["selected_option"]["value"] if view["state"]["values"]["room_block"]["room_select"].get("selected_option") else None,
                "date": view["state"]["values"]["date_block"]["datepicker_action"]["selected_date"],
                "start_time": view["state"]["values"]["start_time_block"]["start_time_action"]["selected_time"],
                "end_time": view["state"]["values"]["end_time_block"]["end_time_action"]["selected_time"],
                "team_id": view["state"]["values"]["team_block"]["team_select"]["selected_option"]["value"] if view["state"]["values"]["team_block"]["team_select"].get("selected_option") else None,
                #"participants": view["state"]["values"]["participants_block"]["participants_select"].get("selected_users", []),
                # "is_recurring": bool(view["state"]["values"]["recurring_block"]["recurring_checkbox"].get("selected_options")),
                # "recurring_weeks": view["state"]["values"]["recurring_weeks_block"]["recurring_weeks_select"]["selected_option"]["value"] if view["state"]["values"]["recurring_weeks_block"]["recurring_weeks_select"].get("selected_option") else "4"
            }
            
            conflict = parsed_conflicts[0]
            conflict_info = {
                "start_time": conflict["start_time"],
                "end_time": conflict["end_time"],
                "team_name": conflict["team_name"],
                "title": conflict["title"]
            }
            
            updated_modal = build_reservation_modal(
                initial_data=modal_data,
                is_edit=False,
                conflict_info=conflict_info
            )
            
            ack(response_action="update", view=updated_modal)
            logger.info(f"단일 예약 충돌 - 모달 업데이트 - 사용자: {user_id}")
            return
        
        # 검증 및 충돌 검사 성공 시 즉시 모달 닫기
        ack()
        logger.info(f"모달 제출 승인 완료 - 사용자: {user_id}")
        
        # 백그라운드에서 예약 생성 처리 (충돌 검사는 이미 완료됨)
        try:
            # 충돌 검사가 이미 완료되었으므로 검증 없이 생성
            reservation_service.create_new_reservation_without_validation(reservation_data, user_id)
            logger.info(f"예약 생성 완료 - 사용자: {user_id}")
            
            # Home Tab 업데이트
            try:
                slack_service.update_home_tab(client, user_id)
                logger.info(f"예약 생성 후 Home Tab 업데이트 성공 - 사용자: {user_id}")
            except Exception as update_error:
                logger.error(f"예약 생성 후 Home Tab 업데이트 실패: {update_error}", exc_info=True)
                
        except Exception as e:
            logger.error(f"예약 생성 실패: {e}", exc_info=True)
            try:
                slack_service.send_ephemeral_message(
                    user_id,
                    "예약 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
                )
            except Exception as notify_error:
                logger.error(f"오류 알림 전송 실패: {notify_error}")
        
    except ValidationError as e:
        # 입력값 오류: 모달을 닫지 않고 필드에 오류 메시지 표시
        errors = {"title_block": str(e)}
        ack(response_action="errors", errors=errors)
        logger.info(f"입력값 오류로 모달 유지 - 사용자: {user_id}: {e}")
        
    except Exception as e:
        # 파싱 중 예상치 못한 오류: 모달 닫고 오류 메시지 표시
        ack()
        logger.error(f"모달 제출 처리 실패: {e}", exc_info=True)
        try:
            slack_service.send_ephemeral_message(
                user_id,
                "요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )
        except Exception as notify_error:
            logger.error(f"오류 알림 전송 실패: {notify_error}")

@app.view(CallbackIds.RESERVATION_EDIT)
def handle_edit_modal_submission(ack, body, client, logger):
    """회의실 예약 수정 모달 제출을 처리합니다."""
    view = body["view"]
    user_id = body["user"]["id"]
    page_id = view.get("private_metadata", "")
    
    try:
        if not page_id:
            raise ValidationError("예약 정보를 찾을 수 없습니다.")
        
        # 먼저 입력값 검증 수행
        reservation_data = reservation_service.parse_modal_data(view, user_id)
        reservation_data.page_id = page_id
        
        # 충돌 검사 수행 (자기 자신 제외)
        conflicts = notion_service.get_conflicting_reservations(
            reservation_data.start_dt, 
            reservation_data.end_dt, 
            reservation_data.room_name,
            exclude_page_id=page_id
        )
        if conflicts:
            parsed_conflicts = notion_service.parse_conflicting_reservations(conflicts)
            
            # 충돌 시 모달 업데이트
            modal_data = {
                "title": view["state"]["values"]["title_block"]["title_input"]["value"],
                "room_id": view["state"]["values"]["room_block"]["room_select"]["selected_option"]["value"] if view["state"]["values"]["room_block"]["room_select"].get("selected_option") else None,
                "date": view["state"]["values"]["date_block"]["datepicker_action"]["selected_date"],
                "start_time": view["state"]["values"]["start_time_block"]["start_time_action"]["selected_time"],
                "end_time": view["state"]["values"]["end_time_block"]["end_time_action"]["selected_time"],
                "team_id": view["state"]["values"]["team_block"]["team_select"]["selected_option"]["value"] if view["state"]["values"]["team_block"]["team_select"].get("selected_option") else None,
                # "participants": view["state"]["values"]["participants_block"]["participants_select"].get("selected_users", []),
                # "is_recurring": bool(view["state"]["values"]["recurring_block"]["recurring_checkbox"].get("selected_options")),
                # "recurring_weeks": view["state"]["values"]["recurring_weeks_block"]["recurring_weeks_select"]["selected_option"]["value"] if view["state"]["values"]["recurring_weeks_block"]["recurring_weeks_select"].get("selected_option") else "4",
                "page_id": page_id
            }
            
            conflict = parsed_conflicts[0]
            conflict_info = {
                "start_time": conflict["start_time"],
                "end_time": conflict["end_time"],
                "team_name": conflict["team_name"],
                "title": conflict["title"]
            }
            
            updated_modal = build_reservation_modal(
                initial_data=modal_data,
                is_edit=True,
                conflict_info=conflict_info
            )
            
            ack(response_action="update", view=updated_modal)
            logger.info(f"예약 수정 충돌 - 모달 업데이트 - 사용자: {user_id}")
            return
        
        # 검증 및 충돌 검사 성공 시 즉시 모달 닫기
        ack()
        logger.info(f"수정 모달 제출 승인 완료 - 사용자: {user_id}")
        
        # 백그라운드에서 예약 수정 처리 (충돌 검사는 이미 완료됨)
        try:
            reservation_service.update_existing_reservation_without_validation(reservation_data, user_id, page_id)
            logger.info(f"예약 수정 완료 - 사용자: {user_id}, 페이지: {page_id}")
            
            # Home Tab 업데이트
            try:
                slack_service.update_home_tab(client, user_id)
                logger.info(f"예약 수정 후 Home Tab 업데이트 성공 - 사용자: {user_id}")
            except Exception as update_error:
                logger.error(f"예약 수정 후 Home Tab 업데이트 실패: {update_error}", exc_info=True)
            
            # 수정 완료 메시지 전송 (날짜+시각 정보 포함)
            try:
                date_str = reservation_data.start_dt.strftime('%Y년 %m월 %d일')
                time_str = f"{reservation_data.start_dt.strftime('%H:%M')}~{reservation_data.end_dt.strftime('%H:%M')}"
                
                slack_service.send_ephemeral_message(
                    user_id,
                    f"✅ {date_str} `{time_str}` 예약이 성공적으로 수정되었습니다."
                )
            except Exception as message_error:
                logger.error(f"성공 메시지 전송 실패: {message_error}")
                
        except Exception as e:
            logger.error(f"예약 수정 실패: {e}", exc_info=True)
            try:
                slack_service.send_ephemeral_message(
                    user_id,
                    "예약 수정 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
                )
            except Exception as notify_error:
                logger.error(f"오류 알림 전송 실패: {notify_error}")
        
    except ValidationError as e:
        # 입력값 오류: 모달을 닫지 않고 필드에 오류 메시지 표시
        errors = {"title_block": str(e)}
        ack(response_action="errors", errors=errors)
        logger.info(f"입력값 오류로 수정 모달 유지 - 사용자: {user_id}: {e}")
        
    except Exception as e:
        # 파싱 중 예상치 못한 오류: 모달 닫고 오류 메시지 표시
        ack()
        logger.error(f"수정 모달 제출 처리 실패: {e}", exc_info=True)
        try:
            slack_service.send_ephemeral_message(
                user_id,
                "요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )
        except Exception as notify_error:
            logger.error(f"오류 알림 전송 실패: {notify_error}")

# --- Message Button Action Handlers ---
@app.action("edit_reservation")
def handle_edit_reservation_button(ack, body, client):
    """메시지의 '예약 수정하기' 버튼 클릭을 처리합니다."""
    try:
        # 먼저 요청 승인
        ack()
        
        user_id = body["user"]["id"]
        page_id = body["actions"][0]["value"]
        trigger_id = body["trigger_id"]
        
        logger.info(f"메시지 버튼 예약 수정 요청 - 사용자: {user_id}, 페이지: {page_id}")
        
        # Notion에서 기존 예약 정보 조회
        reservation = notion_service.get_reservation_by_id(page_id)
        
        # 예약 정보를 모달용으로 변환
        modal_data = reservation_service.parse_reservation_for_modal(reservation)
        modal_data.page_id = page_id  # page_id 추가
        
        # 반복 예약인 경우 수정 불가 메시지 표시
        # if modal_data.is_recurring:
        #     slack_service.send_ephemeral_message(
        #         user_id,
        #         "⚠️ 반복 예약은 개별 수정이 불가능합니다.\n시스템팀에 문의해주세요."
        #     )
        #     logger.info(f"반복 예약 수정 시도 차단 - 사용자: {user_id}, 페이지: {page_id}")
        #     return
        
        # 수정 모달 열기
        client.views_open(
            trigger_id=trigger_id,
            view=build_reservation_modal(
                initial_data=modal_data.__dict__,
                is_edit=True
            )
        )
        logger.info(f"메시지 버튼에서 예약 수정 모달 열기 성공 - 사용자: {user_id}, 페이지: {page_id}")
        
    except Exception as e:
        logger.error(f"메시지 버튼 예약 수정 실패: {e}", exc_info=True)
        slack_service.send_ephemeral_message(
            user_id,
            "예약 수정 모달을 여는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )

@app.action("cancel_reservation")
def handle_cancel_reservation_button(ack, body, client):
    """메시지의 '예약 취소하기' 버튼 클릭을 처리합니다."""
    try:
        # 먼저 요청 승인
        ack()
        
        user_id = body["user"]["id"]
        page_id = body["actions"][0]["value"]
        
        logger.info(f"메시지 버튼 예약 취소 요청 - 사용자: {user_id}, 페이지: {page_id}")
        
        # 취소하기 전에 예약 정보 조회 (메시지에 포함하기 위해)
        reservation = notion_service.get_reservation_by_id(page_id)
        reservation_info = reservation_service.parse_reservation_for_modal(reservation)
        
        # Notion에서 예약 취소
        notion_service.archive_page(page_id)
        
        # 취소 완료 메시지 전송 (날짜+시각 정보 포함)
        date_str = f"{reservation_info.date}"
        time_str = f"{reservation_info.start_time}~{reservation_info.end_time}"
        room_name = ""
        title = reservation_info.title
        
        # room_id로 room_name 찾기
        from config import AppConfig
        config = AppConfig()
        if reservation_info.room_id in config.MEETING_ROOMS:
            room_name = config.MEETING_ROOMS[reservation_info.room_id]["name"]
        
        slack_service.send_ephemeral_message(
            user_id,
            f"✅ {date_str} `{time_str}` 예약이 성공적으로 취소되었습니다."
        )
        
        # Home Tab 새로고침 (사용자가 Home Tab을 보고 있다면)
        try:
            slack_service.update_home_tab(client, user_id)
        except Exception as update_error:
            logger.error(f"Home Tab 업데이트 실패: {update_error}")
        
        logger.info(f"메시지 버튼 예약 취소 성공 - 사용자: {user_id}, 페이지: {page_id}")
        
    except Exception as e:
        logger.error(f"메시지 버튼 예약 취소 실패: {e}", exc_info=True)
        slack_service.send_ephemeral_message(
            user_id,
            "예약 취소 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )

# --- Slack Action Handlers ---
@app.action(ActionIds.HOME_REFRESH)
def handle_home_refresh(ack, body, client):
    """Home Tab 새로고침 버튼 클릭을 처리합니다."""
    try:
        # 먼저 요청 승인
        ack()
        
        user_id = body["user"]["id"]
        logger.info(f"Home Tab 새로고침 요청 - 사용자: {user_id}")
        
        # Home Tab View 업데이트
        slack_service.update_home_tab(client, user_id)
        logger.info(f"Home Tab 새로고침 성공 - 사용자: {user_id}")
        
    except Exception as e:
        logger.error(f"Home Tab 새로고침 실패: {e}", exc_info=True)
        try:
            # 오류 발생 시 사용자에게 알림
            slack_service.send_ephemeral_message(
                user_id,
                "새로고침 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )
        except Exception as notify_error:
            logger.error(f"오류 알림 전송 실패: {notify_error}")

@app.action(ActionIds.HOME_MAKE_RESERVATION)
def handle_home_make_reservation(ack, body, client):
    """Home Tab에서 예약하기 버튼 클릭을 처리합니다."""
    try:
        # 먼저 요청 승인
        ack()
        
        user_id = body["user"]["id"]
        trigger_id = body["trigger_id"]
        
        logger.info(f"Home Tab 예약하기 버튼 클릭 - 사용자: {user_id}")
        
        # 예약 모달 열기
        modal_view = build_reservation_modal()
        response = client.views_open(
            trigger_id=trigger_id,
            view=modal_view
        )
        
        if not response["ok"]:
            raise Exception(f"Modal open failed: {response['error']}")
            
        logger.info(f"Home Tab에서 예약 모달 열기 성공 - 사용자: {user_id}")
        
    except Exception as e:
        logger.error(f"Home Tab에서 예약 모달 열기 실패: {e}", exc_info=True)
        try:
            # 오류 발생 시 사용자에게 알림
            slack_service.send_ephemeral_message(
                user_id,
                "예약 모달을 여는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )
        except Exception as notify_error:
            logger.error(f"오류 알림 전송 실패: {notify_error}")

@app.action(ActionIds.RESERVATION_ACTION)
def handle_reservation_action(ack, body, client):
    """예약 항목의 수정/취소 액션을 처리합니다."""
    try:
        # 먼저 요청 승인
        ack()
        
        user_id = body["user"]["id"]
        selected_option = body["actions"][0]["selected_option"]
        action_value = selected_option["value"]
        trigger_id = body["trigger_id"]
        
        # 액션 값에서 동작과 페이지 ID 추출
        action, page_id = action_value.split("_", 1)
        
        logger.info(f"예약 {action} 요청 - 사용자: {user_id}, 페이지: {page_id}")
        
        if action == "edit":
            # 예약 수정 모달 열기
            try:
                # Notion에서 기존 예약 정보 조회
                reservation = notion_service.get_reservation_by_id(page_id)
                
                # 예약 정보를 모달용으로 변환
                modal_data = reservation_service.parse_reservation_for_modal(reservation)
                modal_data.page_id = page_id  # page_id 추가
                
                # 반복 예약인 경우 수정 불가 메시지 표시
                # if modal_data.is_recurring:
                #     slack_service.send_ephemeral_message(
                #         user_id,
                #         "⚠️ 반복 예약은 개별 수정이 불가능합니다.\n시스템팀에 문의해주세요."
                #     )
                #     logger.info(f"반복 예약 수정 시도 차단 - 사용자: {user_id}, 페이지: {page_id}")
                #     return
                
                # 수정 모달 열기
                client.views_open(
                    trigger_id=trigger_id,
                    view=build_reservation_modal(
                        initial_data=modal_data.__dict__,
                        is_edit=True
                    )
                )
                logger.info(f"예약 수정 모달 열기 성공 - 사용자: {user_id}, 페이지: {page_id}")
                
            except Exception as e:
                logger.error(f"예약 수정 모달 열기 실패: {e}", exc_info=True)
                slack_service.send_ephemeral_message(
                    user_id,
                    ErrorMessages.RESERVATION_INFO_LOAD_FAILED
                )
                
        elif action == "cancel":
            try:
                # 취소하기 전에 예약 정보 조회 (메시지에 포함하기 위해)
                reservation = notion_service.get_reservation_by_id(page_id)
                reservation_info = reservation_service.parse_reservation_for_modal(reservation)
                
                # Notion에서 예약 취소
                notion_service.archive_page(page_id)
                
                # 취소 완료 메시지 전송 (날짜+시각 정보 포함)
                date_str = f"{reservation_info.date}"
                time_str = f"{reservation_info.start_time}~{reservation_info.end_time}"
                room_name = ""
                title = reservation_info.title
                
                # room_id로 room_name 찾기
                from config import AppConfig
                config = AppConfig()
                if reservation_info.room_id in config.MEETING_ROOMS:
                    room_name = config.MEETING_ROOMS[reservation_info.room_id]["name"]
                
                slack_service.send_ephemeral_message(
                    user_id,
                    f"✅ {date_str} `{time_str}` 예약이 성공적으로 취소되었습니다."
                )
                
                # Home Tab 새로고침
                slack_service.update_home_tab(client, user_id)
                
                logger.info(f"예약 취소 성공 - 사용자: {user_id}, 페이지: {page_id}")
                
            except Exception as e:
                logger.error(f"예약 취소 실패: {e}", exc_info=True)
                slack_service.send_ephemeral_message(
                    user_id,
                    "예약 취소 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
                )
    
    except Exception as e:
        logger.error(f"예약 액션 처리 실패: {e}", exc_info=True)
        try:
            slack_service.send_ephemeral_message(
                user_id,
                "요청을 처리하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
            )
        except Exception as notify_error:
            logger.error(f"오류 알림 전송 실패: {notify_error}")

# --- Main Execution ---
if __name__ == "__main__":
    logger.info("🚀 회의실 예약 시스템 시작")
    logger.info(f"Slack 워크스페이스 연결 준비 완료")
    
    try:
        handler = SocketModeHandler(app, slack_config.app_token)
        handler.start()
    except KeyboardInterrupt:
        logger.info("👋 시스템 종료 요청")
    except Exception as e:
        logger.error(f"❌ 시스템 시작 실패: {e}", exc_info=True)
    finally:
        logger.info("🔚 회의실 예약 시스템 종료")

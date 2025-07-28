# app.py
# Slack Bolt 앱을 소켓 모드로 초기화하고, 모든 요청을 처리하는 메인 파일입니다.

from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt import App
from dotenv import load_dotenv
from typing import Dict, Any

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
    trigger_id = body["trigger_id"]
    channel_id = body["user"]["id"]  # 모달은 주로 DM에서 사용되므로 user_id 사용
    
    try:
        # 예약 생성
        reservation_service.create_new_reservation(view, user_id)
        ack()  # 성공 시 모달 닫기
        
    except ValidationError as e:
        # 입력값 오류: 모달을 닫지 않고 필드에 오류 메시지 표시
        errors = {"title_block": str(e)}
        ack(response_action="errors", errors=errors)
        
    except ConflictError as e:
        # 시간 중복 오류: ephemeral message로 확실하게 알림
        detailed_message = e.get_detailed_message()
        try:
            slack_service.send_conflict_alert(user_id, channel_id, detailed_message)
            ack()  # 원본 모달 닫기
            logger.info(f"예약 시간 충돌 - ephemeral 알림 전송 - 사용자: {user_id}")
        except Exception as alert_error:
            # ephemeral 실패 시 기존 방식 사용
            logger.error(f"충돌 ephemeral 알림 실패, 기존 방식 사용 - 사용자: {user_id}: {alert_error}")
            errors = {"start_time_block": detailed_message}
            ack(response_action="errors", errors=errors)
        
    except Exception as e:
        # 기타 예외: 모달 닫고 오류 메시지 표시
        ack()
        ErrorHandler.handle_exception(
            error=e,
            user_id=user_id,
            trigger_id=trigger_id,
            send_error_modal_func=slack_service.send_error_message,
            context="예약 생성"
        )

@app.view(CallbackIds.RESERVATION_EDIT)
def handle_edit_modal_submission(ack, body, client, logger):
    """회의실 예약 수정 모달 제출을 처리합니다."""
    view = body["view"]
    user_id = body["user"]["id"]
    trigger_id = body["trigger_id"]
    channel_id = body["user"]["id"]  # 모달은 주로 DM에서 사용되므로 user_id 사용
    page_id = view.get("private_metadata", "")
    
    try:
        # 예약 수정
        reservation_service.update_existing_reservation(view, user_id, page_id)
        ack()  # 성공 시 모달 닫기
        
    except ValidationError as e:
        # 입력값 오류: 모달을 닫지 않고 필드에 오류 메시지 표시
        errors = {"title_block": str(e)}
        ack(response_action="errors", errors=errors)
        
    except ConflictError as e:
        # 시간 중복 오류: ephemeral message로 확실하게 알림
        detailed_message = e.get_detailed_message()
        try:
            slack_service.send_conflict_alert(user_id, channel_id, detailed_message)
            ack()  # 원본 모달 닫기
            logger.info(f"예약 수정 시간 충돌 - ephemeral 알림 전송 - 사용자: {user_id}")
        except Exception as alert_error:
            # ephemeral 실패 시 기존 방식 사용
            logger.error(f"충돌 ephemeral 알림 실패, 기존 방식 사용 - 사용자: {user_id}: {alert_error}")
            errors = {"start_time_block": detailed_message}
            ack(response_action="errors", errors=errors)
        
    except Exception as e:
        # 기타 예외: 모달 닫고 오류 메시지 표시
        ack()
        logger.error(f"예약 수정 실패 - 사용자: {user_id}: {e}")
        ErrorHandler.handle_modal_error(
            user_id=user_id,
            trigger_id=trigger_id,
            error=e,
            send_error_modal_func=slack_service.send_error_message,
            context="예약 수정"
        )

# --- Slack Action Handlers ---
@app.action(ActionIds.CANCEL_RESERVATION)
def handle_cancel_reservation(ack, body, client):
    """예약 취소 버튼 클릭을 처리합니다."""
    ack()
    
    page_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    
    logger.info(f"예약 취소 요청 - 사용자: {user_id}, 페이지: {page_id}")
    
    try:
        notion_service.archive_page(page_id)
        slack_service.send_message(user_id, SuccessMessages.RESERVATION_CANCELLED)
        logger.info(f"예약 취소 성공 - 사용자: {user_id}, 페이지: {page_id}")
        
    except Exception as e:
        ErrorHandler.handle_slack_command_error(
            user_id=user_id,
            error=e,
            send_message_func=slack_service.send_message,
            context="예약 취소"
        )

@app.action(ActionIds.EDIT_RESERVATION)
def handle_edit_reservation(ack, body, client):
    """예약 수정 버튼 클릭을 처리하여 수정 모달을 엽니다."""
    ack()
    
    page_id = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    trigger_id = body["trigger_id"]
    
    logger.info(f"예약 수정 요청 - 사용자: {user_id}, 페이지: {page_id}")
    
    try:
        # Notion에서 기존 예약 정보 조회
        reservation = notion_service.get_reservation_by_id(page_id)
        
        # 예약 정보를 모달용으로 변환
        modal_data = reservation_service.parse_reservation_for_modal(reservation)
        initial_data = {
            "title": modal_data.title,
            "room_id": modal_data.room_id,
            "date": modal_data.date,
            "start_time": modal_data.start_time,
            "end_time": modal_data.end_time,
            "team_id": modal_data.team_id,
            "participants": modal_data.participants,
            "page_id": modal_data.page_id
        }
        initial_data["page_id"] = page_id
        
        # 수정 모달 열기
        client.views_open(
            trigger_id=trigger_id,
            view=build_reservation_modal(initial_data, is_edit=True)
        )
        logger.info(f"예약 수정 모달 열기 성공 - 사용자: {user_id}, 페이지: {page_id}")
        
    except Exception as e:
        ErrorHandler.handle_slack_command_error(
            user_id=user_id,
            error=e,
            send_message_func=slack_service.send_message,
            context="예약 수정 모달 열기"
        )

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

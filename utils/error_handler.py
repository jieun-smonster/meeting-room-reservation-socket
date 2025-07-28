# utils/error_handler.py
# 표준화된 에러 처리 시스템을 제공합니다.

from typing import Optional, Callable, Any
from functools import wraps
from .logger import get_logger
from .constants import ErrorMessages
from exceptions import ValidationError, ConflictError, NotionError

logger = get_logger(__name__)


class ErrorHandler:
    """표준화된 에러 처리를 제공하는 클래스"""
    
    @staticmethod
    def handle_slack_command_error(
        user_id: str, 
        error: Exception, 
        send_message_func: Callable[[str, str], None],
        context: str = "명령 처리"
    ) -> None:
        """
        Slack 명령어 처리 중 발생한 에러를 처리합니다.
        
        Args:
            user_id: 사용자 ID
            error: 발생한 에러
            send_message_func: 메시지 전송 함수
            context: 에러 발생 컨텍스트
        """
        if isinstance(error, NotionError):
            logger.error(f"Notion 오류 - 사용자: {user_id}, 컨텍스트: {context}", exc_info=True)
            message = f"{ErrorMessages.RESERVATION_QUERY_FAILED}: {error}"
        elif isinstance(error, (ValidationError, ConflictError)):
            logger.warning(f"사용자 입력 오류 - 사용자: {user_id}, 컨텍스트: {context}: {error}")
            message = str(error)
        else:
            logger.error(f"{context} 중 예상치 못한 오류 - 사용자: {user_id}", exc_info=True)
            message = f"{ErrorMessages.RESERVATION_PROCESSING_FAILED}: {error}"
        
        try:
            send_message_func(user_id, message)
        except Exception as slack_error:
            logger.error(f"{ErrorMessages.MESSAGE_SEND_FAILED}: {slack_error}", exc_info=True)
    
    @staticmethod
    def handle_modal_error(
        user_id: str,
        trigger_id: str, 
        error: Exception,
        send_error_modal_func: Callable[[str, str, str], None],
        context: str = "모달 처리"
    ) -> None:
        """
        모달 처리 중 발생한 에러를 처리합니다.
        
        Args:
            user_id: 사용자 ID
            trigger_id: 트리거 ID
            error: 발생한 에러
            send_error_modal_func: 에러 모달 전송 함수
            context: 에러 발생 컨텍스트
        """
        logger.error(f"{context} 중 오류 - 사용자: {user_id}", exc_info=True)
        error_message = f"{context} 중 오류가 발생했습니다: {error}"
        send_error_modal_func(user_id, trigger_id, error_message)


def handle_exceptions(
    logger_name: Optional[str] = None,
    default_message: str = "처리 중 오류가 발생했습니다"
):
    """
    함수 데코레이터: 예외를 자동으로 로깅하고 처리합니다.
    
    Args:
        logger_name: 로거 이름 (None이면 함수 모듈명 사용)
        default_message: 기본 에러 메시지
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            func_logger = get_logger(logger_name or func.__module__)
            try:
                return func(*args, **kwargs)
            except (ValidationError, ConflictError) as e:
                # 비즈니스 로직 에러는 다시 raise
                func_logger.warning(f"{func.__name__} 에서 비즈니스 로직 에러: {e}")
                raise
            except NotionError as e:
                # Notion 에러도 다시 raise
                func_logger.error(f"{func.__name__} 에서 Notion 에러: {e}", exc_info=True)
                raise
            except Exception as e:
                # 예상치 못한 에러는 로깅하고 일반적인 에러로 변환
                func_logger.error(f"{func.__name__} 에서 예상치 못한 에러", exc_info=True)
                raise Exception(f"{default_message}: {e}")
        return wrapper
    return decorator


 
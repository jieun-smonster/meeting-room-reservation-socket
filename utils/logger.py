# utils/logger.py
# 통합 로깅 시스템을 제공합니다.

import logging
import sys
from typing import Optional


def setup_logging(level: str = "WARNING", format_string: Optional[str] = None) -> None:
    """
    프로젝트 전체의 로깅을 설정합니다.
    
    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL) - 기본값 WARNING으로 변경
        format_string: 로그 포맷 문자열
    """
    if format_string is None:
        format_string = (
            "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        )
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("app.log", encoding="utf-8")
        ]
    )


def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거를 반환합니다.
    
    Args:
        name: 로거 이름 (보통 __name__)
        
    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
    return logging.getLogger(name)


class LoggerMixin:
    """로깅 기능을 제공하는 믹스인 클래스"""
    
    @property
    def logger(self) -> logging.Logger:
        """클래스별 로거 반환"""
        return get_logger(self.__class__.__module__ + "." + self.__class__.__name__)
    
    def log_info(self, message: str, **kwargs) -> None:
        """정보 로그"""
        self.logger.info(message, extra=kwargs)
    
    def log_error(self, message: str, exc_info: bool = True, **kwargs) -> None:
        """에러 로그"""
        self.logger.error(message, exc_info=exc_info, extra=kwargs)
    
    def log_warning(self, message: str, **kwargs) -> None:
        """경고 로그"""
        self.logger.warning(message, extra=kwargs)
    
 
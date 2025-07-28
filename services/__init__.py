# services/__init__.py

# 서비스 인스턴스들 import
from .notion_service import notion_service
from . import slack_service
from .reservation_service import reservation_service_instance as reservation_service

# 명확한 인터페이스 노출
__all__ = [
    'notion_service',
    'slack_service', 
    'reservation_service'
]

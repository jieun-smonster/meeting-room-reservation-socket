# models/slack_types.py
# Slack 관련 타입과 데이터 구조를 정의합니다.

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class SlackUser:
    """Slack 사용자 정보"""
    id: str
    username: str
    name: str
    team_id: str


@dataclass  
class SlackChannel:
    """Slack 채널 정보"""
    id: str
    name: str


@dataclass
class SlackBody:
    """Slack 이벤트 바디"""
    user_id: str
    channel_id: str
    channel_name: str
    trigger_id: Optional[str] = None
    text: str = ""
    user: Optional[SlackUser] = None
    actions: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.actions is None:
            self.actions = []

    @property
    def is_direct_message(self) -> bool:
        """DM 채널인지 확인"""
        return self.channel_name == "directmessage"

    @property
    def target_channel(self) -> str:
        """메시지를 보낼 대상 채널 (DM인 경우 user_id, 아니면 channel_id)"""
        return self.user_id if self.is_direct_message else self.channel_id


SlackBlocks = List[Dict[str, Any]] 
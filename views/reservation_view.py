
from datetime import datetime
from typing import Dict, Optional
from config import AppConfig
from utils.constants import CallbackIds

def get_static_select_element(action_id, placeholder, options, selected_value):
    element = {
        "type": "static_select",
        "action_id": action_id,
        "placeholder": {"type": "plain_text", "text": placeholder},
        "options": options,
    }
    selected_option = next((opt for opt in options if opt["value"] == selected_value), None)
    if selected_option:
        element["initial_option"] = selected_option
    return element

def build_reservation_modal(initial_data: Optional[Dict] = None, is_edit: bool = False, conflict_info: Optional[Dict] = None):
    """
    회의실 예약 모달을 생성합니다.
    
    Args:
        initial_data: 초기 데이터 (수정 시)
        is_edit: 수정 모달 여부
        conflict_info: 시간 충돌 정보 (있는 경우)
    """
    if initial_data is None:
        initial_data = {}
    
    # 회의실 선택 옵션 생성
    room_options = [
        {
            "text": {"type": "plain_text", "text": room_info["name"]},
            "value": room_id
        }
        for room_id, room_info in AppConfig.MEETING_ROOMS.items()
    ]
    
    # 기본 회의실 설정
    if not initial_data.get("room_id"):
        default_room_id = AppConfig.get_default_room_id()
        if default_room_id:
            initial_data["room_id"] = default_room_id
    
    room_element = {
        "type": "static_select",
        "action_id": "room_select",
        "placeholder": {
            "type": "plain_text",
            "text": "회의실을 선택하세요"
        },
        "options": room_options
    }
    
    # initial_option 설정
    if initial_data.get("room_id"):
        initial_room = next(
            (opt for opt in room_options if opt["value"] == initial_data["room_id"]),
            None
        )
        if initial_room:
            room_element["initial_option"] = initial_room
    
    modal = {
        "type": "modal",
        "callback_id": CallbackIds.RESERVATION_EDIT if is_edit else CallbackIds.RESERVATION_SUBMIT,
        "title": {
            "type": "plain_text",
            "text": "회의실 예약 수정" if is_edit else "회의실 예약"
        },
        "submit": {
            "type": "plain_text",
            "text": "수정하기" if is_edit else "예약하기"
        },
        "close": {
            "type": "plain_text",
            "text": "취소"
        },
        "blocks": []
    }
    
    # 시간 충돌 경고 메시지 추가 (있는 경우)
    if conflict_info:
        modal["blocks"].extend([
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ 시간 충돌 알림",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        conflict_info.get("message", 
                            f"다음 회의와 시간이 겹칩니다:\n> `{conflict_info.get('start_time', '')} ~ {conflict_info.get('end_time', '')}`\n> *[{conflict_info.get('team_name', '')}]* {conflict_info.get('title', '')}\n\n다른 시간을 선택해주세요."
                        )
                    )
                }
            },
            {
                "type": "divider"
            }
        ])
    
    # 회의 제목
    modal["blocks"].append({
        "type": "input",
        "block_id": "title_block",
        "element": {
            "type": "plain_text_input",
            "action_id": "title_input",
            "placeholder": {
                "type": "plain_text",
                "text": "회의 제목을 입력하세요"
            },
            "initial_value": initial_data.get("title", "")
        },
        "label": {
            "type": "plain_text",
            "text": "회의 제목"
        }
    })
    
    # 회의실 선택
    modal["blocks"].append({
        "type": "input",
        "block_id": "room_block",
        "element": room_element,
        "label": {
            "type": "plain_text",
            "text": "회의실"
        }
    })
    
    # 날짜 선택
    modal["blocks"].append({
        "type": "input",
        "block_id": "date_block",
        "element": {
            "type": "datepicker",
            "action_id": "datepicker_action",
            "initial_date": initial_data.get("date", datetime.now().strftime("%Y-%m-%d")),
            "placeholder": {
                "type": "plain_text",
                "text": "날짜 선택"
            }
        },
        "label": {
            "type": "plain_text",
            "text": "날짜"
        }
    })
    
    # 시작 시간
    modal["blocks"].append({
        "type": "input",
        "block_id": "start_time_block",
        "element": {
            "type": "timepicker",
            "action_id": "start_time_action",
            "initial_time": initial_data.get("start_time", "09:00"),
            "placeholder": {
                "type": "plain_text",
                "text": "시작 시간 선택"
            }
        },
        "label": {
            "type": "plain_text",
            "text": "시작 시간"
        }
    })
    
    # 종료 시간
    modal["blocks"].append({
        "type": "input",
        "block_id": "end_time_block",
        "element": {
            "type": "timepicker",
            "action_id": "end_time_action",
            "initial_time": initial_data.get("end_time", "10:00"),
            "placeholder": {
                "type": "plain_text",
                "text": "종료 시간 선택"
            }
        },
        "label": {
            "type": "plain_text",
            "text": "종료 시간"
        }
    })
    
    # 팀 선택
    team_options = [
        {
            "text": {"type": "plain_text", "text": team_name},
            "value": team_id
        }
        for team_id, team_name in AppConfig.TEAMS.items()
    ]
    
    team_element = {
        "type": "static_select",
        "action_id": "team_select",
        "placeholder": {
            "type": "plain_text",
            "text": "주관 팀을 선택하세요"
        },
        "options": team_options
    }
    
    # initial_option은 값이 있을 때만 추가
    if initial_data.get("team_id"):
        initial_team = next(
            (opt for opt in team_options if opt["value"] == initial_data["team_id"]),
            None
        )
        if initial_team:
            team_element["initial_option"] = initial_team
    
    modal["blocks"].append({
        "type": "input",
        "block_id": "team_block",
        "element": team_element,
        "label": {
            "type": "plain_text",
            "text": "주관 팀"
        }
    })
    
    # 참석자 선택 (선택사항)
    modal["blocks"].append({
        "type": "input",
        "block_id": "participants_block",
        "element": {
            "type": "multi_users_select",
            "action_id": "participants_select",
            "placeholder": {
                "type": "plain_text",
                "text": "참석자를 선택하세요"
            },
            "initial_users": initial_data.get("participants", [])
        },
        "label": {
            "type": "plain_text",
            "text": "참석자 (선택사항)"
        },
        "optional": True
    })
    
    # 반복 설정 (선택사항)
    recurring_option = {
        "text": {
            "type": "plain_text",
            "text": "매주 이 시간에 반복",
            "emoji": True
        },
        "description": {
            "type": "plain_text",
            "text": "선택하면 동일한 시간에 매주 반복 예약됩니다.",
            "emoji": True
        },
        "value": "weekly"
    }

    recurring_element = {
        "type": "checkboxes",
        "action_id": "recurring_checkbox",
        "options": [recurring_option]
    }
    
    # 반복 예약인 경우 초기값 설정
    if initial_data.get("is_recurring"):
        recurring_element["initial_options"] = [recurring_option]

    modal["blocks"].append({
        "type": "input",
        "block_id": "recurring_block",
        "element": recurring_element,
        "label": {
            "type": "plain_text",
            "text": "반복 설정",
            "emoji": True
        },
        "optional": True
    })
    
    # 반복 주수 선택 (반복 설정이 체크된 경우에만 표시)
    recurring_weeks_options = [
        {"text": {"type": "plain_text", "text": f"{i}주"}, "value": str(i)}
        for i in range(2, 13)  # 2주부터 12주까지
    ]
    
    recurring_weeks_element = {
        "type": "static_select",
        "action_id": "recurring_weeks_select",
        "placeholder": {
            "type": "plain_text",
            "text": "반복 주수를 선택하세요"
        },
        "options": recurring_weeks_options
    }
    
    # 기본값 설정 (4주)
    default_weeks = initial_data.get("recurring_weeks", "4")
    default_option = next(
        (opt for opt in recurring_weeks_options if opt["value"] == default_weeks),
        recurring_weeks_options[2]  # 4주 (인덱스 2)
    )
    recurring_weeks_element["initial_option"] = default_option

    modal["blocks"].append({
        "type": "input",
        "block_id": "recurring_weeks_block",
        "element": recurring_weeks_element,
        "label": {
            "type": "plain_text",
            "text": "반복 주수",
            "emoji": True
        },
        "optional": True
    })
    
    # 수정 모달인 경우 private_metadata에 page_id 추가
    if is_edit and initial_data.get("page_id"):
        modal["private_metadata"] = initial_data["page_id"]
    
    return modal

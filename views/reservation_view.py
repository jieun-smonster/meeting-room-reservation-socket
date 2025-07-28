
from datetime import datetime
from config import AppConfig
from utils.date_utils import get_next_10min_time

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

def build_reservation_modal(initial_data=None, is_edit=False):
    default_room_id = AppConfig.get_default_room_id()

    if initial_data is None:
        initial_data = {}

    room_options = [
        {"text": {"type": "plain_text", "text": details["name"]}, "value": id}
                    for id, details in AppConfig.MEETING_ROOMS.items()
    ]
    team_options = [
        {"text": {"type": "plain_text", "text": name}, "value": id}
                    for id, name in AppConfig.TEAMS.items()
    ]

    # 기본 시작 시간 (현재 시간 기준 다음 10분 단위, 수정 시에는 기존 값 유지)
    default_start_time = initial_data.get("start_time", get_next_10min_time())
    
    # 기본 종료 시간 (시작 시간 + 1시간, 수정 시에는 기존 값 유지)
    if "end_time" not in initial_data:
        try:
            start_dt = datetime.strptime(default_start_time, '%H:%M')
            end_dt = start_dt.replace(hour=start_dt.hour + 1)
            default_end_time = end_dt.strftime('%H:%M')
        except:
            default_end_time = "10:00"
    else:
        default_end_time = initial_data.get("end_time")

    # 수정 모드인 경우 콜백 ID와 제목, 버튼 텍스트 변경
    callback_id = "reservation_edit_submit" if is_edit else "reservation_modal_submit"
    modal_title = "회의실 예약 수정" if is_edit else "회의실 예약"
    submit_text = "수정하기" if is_edit else "예약하기"

    return {
        "type": "modal",
        "callback_id": callback_id,
        "private_metadata": initial_data.get("page_id", ""),
        "title": {"type": "plain_text", "text": modal_title},
        "submit": {"type": "plain_text", "text": submit_text},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "input",
                "block_id": "title_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title_input",
                    "initial_value": initial_data.get("title", ""),
                    "placeholder": {"type": "plain_text", "text": "예: 주간 기획 회의"},
                },
                "label": {"type": "plain_text", "text": "회의 제목"},
            },
            {
                "type": "input",
                "block_id": "room_block",
                "label": {"type": "plain_text", "text": "회의실 선택"},
                "element": get_static_select_element(
                    action_id="room_select",
                    placeholder="회의실을 선택하세요",
                    options=room_options,
                    selected_value=initial_data.get("room_id", default_room_id)
                )
            },
            {
                "type": "input",
                "block_id": "date_block",
                "element": {
                    "type": "datepicker",
                    "action_id": "datepicker_action",
                    "initial_date": initial_data.get("date", datetime.now().strftime('%Y-%m-%d')),
                },
                "label": {"type": "plain_text", "text": "날짜"},
            },
            {
                "type": "input",
                "block_id": "start_time_block",
                "element": {
                    "type": "timepicker",
                    "action_id": "start_time_action",
                    "initial_time": default_start_time,
                },
                "label": {"type": "plain_text", "text": "시작 시각"},
            },
            {
                "type": "input",
                "block_id": "end_time_block",
                "element": {
                    "type": "timepicker",
                    "action_id": "end_time_action",
                    "initial_time": default_end_time,
                },
                "label": {"type": "plain_text", "text": "종료 시각"},
            },
            {
                "type": "input",
                "block_id": "team_block",
                "label": {"type": "plain_text", "text": "주관 팀"},
                "element": get_static_select_element(
                    action_id="team_select",
                    placeholder="팀을 선택하세요",
                    options=team_options,
                    selected_value=initial_data.get("team_id")
                )
            },
            {
                "type": "input",
                "block_id": "participants_block",
                "element": {
                    "type": "multi_users_select",
                    "action_id": "participants_select",
                    "initial_users": initial_data.get("participants", []),
                    "placeholder": {"type": "plain_text", "text": "참석자를 선택하세요"},
                },
                "label": {"type": "plain_text", "text": "참석자"},
                "optional": True,
            },
            {
                "type": "input",
                "block_id": "recurring_block",
                "label": {"type": "plain_text", "text": "반복 설정"},
                "element": {
                    "type": "checkboxes",
                    "action_id": "recurring_checkbox",
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "매주 이 시간에 반복"},
                            "value": "weekly"
                        }
                    ]
                },
                "optional": True,
            }
        ],
    }

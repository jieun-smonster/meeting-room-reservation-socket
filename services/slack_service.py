# services/slack_service.py
# Slack API와 통신하는 모든 로직을 담당합니다.

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging

from config import AppConfig

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# Slack 클라이언트 초기화
client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
NOTIFICATION_CHANNEL = os.environ.get("SLACK_NOTIFICATION_CHANNEL")

def send_message(channel_id: str, text: str, blocks: list = None):
    """지정된 채널 또는 사용자에게 메시지를 전송합니다."""
    try:
        response = client.chat_postMessage(channel=channel_id, text=text, blocks=blocks)
        return response
    except SlackApiError as e:
        logging.error(f"Slack 메시지 전송 실패 (channel: {channel_id}): {e.response['error']}")
        # 에러가 발생했을 때 다시 시도할 수 있는 경우를 처리
        if e.response.get('error') == 'channel_not_found':
            logging.error(f"채널을 찾을 수 없습니다. channel_id: {channel_id}")
        raise e

def send_ephemeral_message(user_id: str, trigger_id: str, text: str):
    """사용자에게만 보이는 임시 메시지를 전송합니다."""
    try:
        response = client.chat_postEphemeral(channel=user_id, user=user_id, text=f":warning: {text}")
        return response
    except SlackApiError as e:
        logging.error(f"Slack 임시 메시지 전송 실패 (user: {user_id}): {e.response['error']}")
        raise e

def send_conflict_alert(user_id: str, channel_id: str, conflict_details: str):
    """충돌 알림을 ephemeral message로 확실하게 표시합니다."""
    try:
        # Ephemeral message로 사용자에게만 보이는 메시지 전송
        response = client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="⚠️ 예약 시간 충돌",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⚠️ *예약 시간 충돌*\n\n{conflict_details}"
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "💡 *다른 시간으로 다시 예약해주세요.*"
                    }
                }
            ]
        )
        logging.info(f"충돌 알림 ephemeral 메시지 전송 성공 - 사용자: {user_id}")
        return response
    except SlackApiError as e:
        logging.error(f"충돌 알림 ephemeral 메시지 전송 실패 - 사용자: {user_id}: {e.response['error']}")
        
        # Ephemeral이 실패하면 DM으로 시도
        try:
            response = client.chat_postMessage(
                channel=user_id,  # DM으로 전송
                text=f"⚠️ *예약 시간 충돌*\n\n{conflict_details}\n\n💡 다른 시간으로 다시 예약해주세요.",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"⚠️ *예약 시간 충돌*"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": conflict_details
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "💡 *다른 시간으로 다시 예약해주세요.*"
                        }
                    }
                ]
            )
            logging.info(f"충돌 알림 DM 전송 성공 - 사용자: {user_id}")
            return response
        except SlackApiError as dm_error:
            logging.error(f"충돌 알림 DM 전송도 실패 - 사용자: {user_id}: {dm_error.response['error']}")
            raise dm_error

def send_error_message(user_id: str, trigger_id: str, error_text: str):
    """오류 발생 시 사용자에게 오류 Modal을 엽니다."""
    try:
        client.views_open(
            trigger_id=trigger_id,
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "오류 발생"},
                "close": {"type": "plain_text", "text": "닫기"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f":alert: {error_text}"}
                    }
                ]
            }
        )
    except SlackApiError as e:
        logging.error(f"Slack 오류 Modal 전송 실패: {e.response['error']}")

def send_confirmation_message(user_id: str, details: dict):
    """예약 성공 후 사용자에게 확인 DM을 보냅니다."""
    # 참석자 리스트가 비어있을 경우 '없음'으로 표시
    participants = details.get("participants")
    if participants:
        participants_text = ", ".join([f"<@{p}>" for p in participants])
    else:
        participants_text = "없음"

    # 날짜와 시간을 분리하여 더 명확하게 표시
    date_str = details['start_dt'].strftime('%Y년 %m월 %d일 (%A)')
    start_time = details['start_dt'].strftime('%H:%M')
    end_time = details['end_dt'].strftime('%H:%M')
    
    # 요일을 한글로 변경
    weekdays = {
        'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일',
        'Thursday': '목요일', 'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'
    }
    for eng, kor in weekdays.items():
        date_str = date_str.replace(eng, kor)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn", 
                "text": "🎉 *회의실 예약이 성공적으로 완료되었습니다!*"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🗓️ *{date_str}*\n⏰ *{start_time} ~ {end_time}*"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn", 
                    "text": f"🏢 *회의실*\n{details['room_name']}"
                },
                {
                    "type": "mrkdwn", 
                    "text": f"👥 *주관 팀*\n{details['team_name']}"
                },
                {
                    "type": "mrkdwn", 
                    "text": f"📝 *회의 주제*\n{details['title']}"
                },
                {
                    "type": "mrkdwn", 
                    "text": f"👤 *참석자*\n{participants_text}"
                }
            ]
        },
        {
            "type": "divider"
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📝 예약 수정하기"},
                    "action_id": "edit_reservation",
                    "value": details['page_id'],
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ 예약 취소하기"},
                    "style": "danger",
                    "action_id": "cancel_reservation",
                    "value": details['page_id']
                }
            ]
        }
    ]
    send_message(user_id, "✅ 회의실 예약 완료", blocks)

def send_update_confirmation_message(user_id: str, details: dict):
    """예약 수정 완료 후 사용자에게 확인 DM을 보냅니다."""
    # 참석자 리스트가 비어있을 경우 '없음'으로 표시
    participants = details.get("participants")
    if participants:
        participants_text = ", ".join([f"<@{p}>" for p in participants])
    else:
        participants_text = "없음"

    # 날짜와 시간을 분리하여 더 명확하게 표시
    date_str = details['start_dt'].strftime('%Y년 %m월 %d일 (%A)')
    start_time = details['start_dt'].strftime('%H:%M')
    end_time = details['end_dt'].strftime('%H:%M')
    
    # 요일을 한글로 변경
    weekdays = {
        'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일',
        'Thursday': '목요일', 'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'
    }
    for eng, kor in weekdays.items():
        date_str = date_str.replace(eng, kor)

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn", 
                "text": "✏️ *회의실 예약이 성공적으로 수정되었습니다!*"
            }
        },
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🗓️ *{date_str}*\n⏰ *{start_time} ~ {end_time}*"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn", 
                    "text": f"🏢 *회의실*\n{details['room_name']}"
                },
                {
                    "type": "mrkdwn", 
                    "text": f"👥 *주관 팀*\n{details['team_name']}"
                },
                {
                    "type": "mrkdwn", 
                    "text": f"📝 *회의 주제*\n{details['title']}"
                },
                {
                    "type": "mrkdwn", 
                    "text": f"👤 *참석자*\n{participants_text}"
                }
            ]
        },
        {
            "type": "divider"
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📝 다시 수정하기"},
                    "action_id": "edit_reservation",
                    "value": details['page_id'],
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ 예약 취소하기"},
                    "style": "danger",
                    "action_id": "cancel_reservation",
                    "value": details['page_id']
                }
            ]
        }
    ]
    send_message(user_id, "✏️ 회의실 예약 수정 완료", blocks)

def send_success_message(user_id: str):
    """
    예약 성공 시 사용자에게 슬랙 DM으로 성공 메시지를 전송합니다.
    """
    text = ":white_check_mark: 회의실 예약이 정상적으로 완료되었습니다!"
    send_message(user_id, text)

def format_reservation_status_message(reservations: list, query_date: str = None):
    """예약 현황을 Slack 메시지 블록 형태로 포맷합니다."""
    from datetime import datetime
    
    # 날짜 헤더 생성 (한국어 친화적)
    if query_date:
        if query_date in ["오늘", "내일"]:
            date_header = f"📅 *{query_date}의 회의실 예약 현황*"
        elif query_date == "앞으로 7일간":
            date_header = f"📅 *{query_date} 회의실 예약 현황*"
        else:
            # YYYY년 MM월 DD일 형식으로 변환 시도
            try:
                if "년" in query_date:
                    date_header = f"📅 *{query_date}의 회의실 예약 현황*"
                else:
                    # YYYY-MM-DD 형식인 경우 한국어로 변환
                    date_obj = datetime.strptime(query_date, '%Y-%m-%d')
                    korean_date = date_obj.strftime('%Y년 %m월 %d일')
                    weekdays = ['월', '화', '수', '목', '금', '토', '일']
                    korean_weekday = weekdays[date_obj.weekday()]
                    date_header = f"📅 *{korean_date} ({korean_weekday})의 회의실 예약 현황*"
            except:
                date_header = f"📅 *{query_date}의 회의실 예약 현황*"
    else:
        date_header = f"📅 *오늘의 회의실 예약 현황*"
    
    # 예약이 없는 경우
    if not reservations:
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": date_header}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "🎉 예약된 회의가 없습니다!"}}
        ]
    
    # 회의실별로 예약을 그룹화
    rooms_data = {}
    for reservation in reservations:
        try:
            properties = reservation.get("properties", {})
            
            # 회의실 이름 추출
            room_prop = properties.get(AppConfig.NOTION_PROPS["room_name"], {})
            room_name = "알 수 없는 회의실"
            if room_prop.get("rich_text"):
                room_name = room_prop["rich_text"][0]["text"]["content"]
            
            if room_name not in rooms_data:
                rooms_data[room_name] = []
            
            # 제목 추출
            title_prop = properties.get(AppConfig.NOTION_PROPS["title"], {})
            title = "제목 없음"
            if title_prop.get("title"):
                title = title_prop["title"][0]["text"]["content"]
            
            # 시작/종료 시간 추출
            start_prop = properties.get(AppConfig.NOTION_PROPS["start_time"], {})
            end_prop = properties.get(AppConfig.NOTION_PROPS["end_time"], {})
            
            start_time = None
            end_time = None
            if start_prop.get("date") and end_prop.get("date"):
                start_time = datetime.fromisoformat(start_prop["date"]["start"].replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end_prop["date"]["start"].replace("Z", "+00:00"))
            
            # 주관 팀 추출
            team_prop = properties.get(AppConfig.NOTION_PROPS["team_name"], {})
            team_name = "팀 미정"
            if team_prop.get("rich_text"):
                team_name = team_prop["rich_text"][0]["text"]["content"]
            
            # 참석자 추출
            participants_prop = properties.get(AppConfig.NOTION_PROPS["participants"], {})
            participants = []
            if participants_prop.get("people"):
                for person in participants_prop["people"]:
                    if person.get("id"):
                        participants.append(f"<@{person['id']}>")
            
            rooms_data[room_name].append({
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "team_name": team_name,
                "participants": participants,
                "page_id": reservation.get("id", "")
            })
                
        except Exception as e:
            logging.error(f"예약 정보 파싱 중 오류: {e}")
            continue
    
    # 블록 생성
    blocks = []
    
    # 전체 날짜 헤더 한 번만 표시
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": date_header}
    })
    
    # 구분선
    blocks.append({"type": "divider"})
    
    # 각 회의실별로 블록 생성
    room_names = sorted(rooms_data.keys())  # 회의실명으로 정렬
    
    for idx, room_name in enumerate(room_names):
        room_reservations = rooms_data[room_name]
        
        # 시간순으로 정렬
        room_reservations.sort(key=lambda x: x["start_time"] if x["start_time"] else datetime.min.replace(tzinfo=datetime.now().tzinfo))
        
        # 회의실 서브헤더 (날짜 제거, 회의실명만)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f" *{room_name}*"}
        })
        
        # 각 예약에 대한 정보
        for reservation in room_reservations:
          
            if reservation["start_time"] and reservation["end_time"]:
                time_str = f"{reservation['start_time'].strftime('%H:%M')} ~ {reservation['end_time'].strftime('%H:%M')}"
            else:
                time_str = "시간 미정"
            
            # 참석자 처리 (3명 초과 시 토글 형태)
            participants_text = format_participants_with_toggle(reservation["participants"])
            
            # 예약 정보 블록
            reservation_text = f"🕙 *{time_str}* *[{reservation['team_name']}]* {reservation['title']}"
            
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": reservation_text}
            })
            
            # 참석자 정보가 있으면 context로 표시
            if participants_text:
                blocks.append({
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": participants_text}]
                })
        
        # 마지막 회의실이 아니면 구분선 추가
        if idx < len(room_names) - 1:
            blocks.append({"type": "divider"})
    
    return blocks


def format_participants_with_toggle(participants):
    """참석자를 토글 형태로 포맷합니다. 3명 초과 시 접어서 표시."""
    if not participants:
        return "참석자: 없음"
    
    if len(participants) <= 3:
        return f"참석자: {', '.join(participants)}"
    else:
        # 처음 2명만 보여주고 나머지는 '...더보기' 형태로
        visible_participants = participants[:2]
        hidden_count = len(participants) - 2
        
        # Slack에서 완전한 토글은 지원하지 않으므로, 
        # 일부만 보여주고 전체 리스트를 별도 블록으로 처리
        return f"참석자: {', '.join(visible_participants)}... *+{hidden_count}명 더*"

def send_reservation_status(channel_id: str, reservations: list, query_date: str = None):
    """예약 현황을 지정된 채널에 전송합니다."""
    try:
        blocks = format_reservation_status_message(reservations, query_date)
        date_str = query_date if query_date else "오늘"
        send_message(channel_id, f"{date_str}의 회의실 예약 현황입니다.", blocks)
        logging.info(f"예약 현황 메시지 전송 성공 (channel: {channel_id})")
    except SlackApiError as e:
        logging.error(f"예약 현황 메시지 전송 실패: {e}")
        # 블록 메시지가 실패하면 간단한 텍스트로 재시도
        try:
            simple_text = format_simple_reservation_text(reservations, query_date)
            send_message(channel_id, simple_text)
            logging.info(f"간단한 텍스트로 예약 현황 전송 성공 (channel: {channel_id})")
        except Exception as fallback_error:
            logging.error(f"텍스트 메시지 전송도 실패: {fallback_error}")
            raise e
    except Exception as e:
        logging.error(f"예약 현황 포맷팅 중 오류: {e}")
        raise e

def format_simple_reservation_text(reservations: list, query_date: str = None):
    """예약 현황을 간단한 텍스트 형태로 포맷합니다 (블록 메시지 실패 시 폴백용)."""
    from datetime import datetime
    
    date_str = query_date if query_date else "오늘"
    
    if not reservations:
        return f"📅 {date_str}의 회의실 예약 현황\n🎉 예약된 회의가 없습니다!"
    
    text = f"📅 {date_str}의 회의실 예약 현황\n{'='*30}\n"
    
    for i, reservation in enumerate(reservations, 1):
        try:
            properties = reservation.get("properties", {})
            
            # 제목 추출
            title_prop = properties.get(AppConfig.NOTION_PROPS["title"], {})
            title = "제목 없음"
            if title_prop.get("title"):
                title = title_prop["title"][0]["text"]["content"]
            
            # 회의실 이름 추출
            room_prop = properties.get(AppConfig.NOTION_PROPS["room_name"], {})
            room_name = "회의실 미정"
            if room_prop.get("rich_text"):
                room_name = room_prop["rich_text"][0]["text"]["content"]
            
            # 시간 추출
            start_prop = properties.get(AppConfig.NOTION_PROPS["start_time"], {})
            end_prop = properties.get(AppConfig.NOTION_PROPS["end_time"], {})
            
            time_text = "시간 미정"
            if start_prop.get("date") and end_prop.get("date"):
                start_time = datetime.fromisoformat(start_prop["date"]["start"].replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end_prop["date"]["start"].replace("Z", "+00:00"))
                time_text = f"{start_time.strftime('%H:%M')} ~ {end_time.strftime('%H:%M')}"
            
            # 팀 이름 추출
            team_prop = properties.get(AppConfig.NOTION_PROPS["team_name"], {})
            team_name = "팀 미정"
            if team_prop.get("rich_text"):
                team_name = team_prop["rich_text"][0]["text"]["content"]
            
            text += f"{i}. 🏢 {room_name} | 🕐 {time_text}\n"
            text += f"   📝 {title} | 👥 {team_name}\n\n"
            
        except Exception as e:
            logging.error(f"예약 정보 파싱 중 오류 (간단 텍스트): {e}")
            text += f"{i}. 예약 정보 파싱 오류\n\n"
    
    return text

def post_daily_schedule(schedule_blocks: list):
    """지정된 채널에 일일 예약 현황을 포스팅합니다."""
    send_message(NOTIFICATION_CHANNEL, "오늘의 회의실 예약 현황입니다.", schedule_blocks)
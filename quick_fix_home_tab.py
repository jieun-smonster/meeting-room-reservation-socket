#!/usr/bin/env python3
# quick_fix_home_tab.py
# 홈탭 "계속 진행중인 작업입니다" 문제를 즉시 해결하는 스크립트

import os
import sys
import asyncio
import time
from dotenv import load_dotenv

load_dotenv()

def test_home_tab_components():
    """홈탭 구성 요소들을 개별적으로 테스트"""
    print("🔍 홈탭 구성 요소 개별 테스트 시작")
    
    try:
        # 1. Notion 서비스 테스트
        print("\n📊 1단계: Notion 데이터 조회 테스트")
        start_time = time.time()
        
        from services.notion_service import NotionService
        from config import AppConfig
        
        notion_service = NotionService(AppConfig())
        reservations = notion_service.get_reservations_by_date()
        
        notion_time = time.time() - start_time
        print(f"✅ Notion 조회 성공 - 소요시간: {notion_time:.2f}초, 예약 수: {len(reservations)}")
        
        if notion_time > 3.0:
            print(f"⚠️ Notion 응답이 느립니다 ({notion_time:.2f}초). 이것이 홈탭 timeout 원인일 수 있습니다.")
        
        # 2. 홈탭 뷰 구성 테스트
        print("\n🎨 2단계: 홈탭 뷰 구성 테스트")
        start_time = time.time()
        
        from services.slack_service import build_home_tab_view
        home_view = build_home_tab_view(reservations)
        
        view_time = time.time() - start_time
        print(f"✅ 홈탭 뷰 구성 성공 - 소요시간: {view_time:.2f}초, 블록 수: {len(home_view.get('blocks', []))}")
        
        # 3. Action ID 검증
        print("\n🎯 3단계: Action ID 검증")
        action_ids_found = []
        
        for block in home_view.get('blocks', []):
            if block.get('type') == 'actions':
                for element in block.get('elements', []):
                    action_id = element.get('action_id')
                    if action_id:
                        action_ids_found.append(action_id)
            elif block.get('type') == 'section' and 'accessory' in block:
                action_id = block['accessory'].get('action_id')
                if action_id:
                    action_ids_found.append(action_id)
        
        print(f"✅ Action ID 발견: {action_ids_found}")
        
        # 4. JSON 크기 검증
        print("\n📏 4단계: JSON 크기 검증")
        import json
        view_json = json.dumps(home_view)
        view_size = len(view_json.encode('utf-8'))
        print(f"✅ 홈탭 뷰 크기: {view_size:,} bytes")
        
        if view_size > 100000:  # 100KB
            print(f"⚠️ 홈탭 뷰가 너무 큽니다 ({view_size:,} bytes). Slack 제한을 초과할 수 있습니다.")
        
        return True, f"총 소요시간: {notion_time + view_time:.2f}초"
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

def test_slack_api_direct():
    """Slack API 직접 호출 테스트"""
    print("\n🔌 Slack API 직접 호출 테스트")
    
    try:
        from slack_sdk import WebClient
        from config import get_slack_config
        
        slack_config = get_slack_config()
        client = WebClient(token=slack_config.bot_token)
        
        # 간단한 홈탭 뷰 직접 게시 테스트
        test_user_id = "U097J4KBVPA"  # 실제 사용자 ID로 변경 필요
        
        simple_view = {
            "type": "home",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🔧 테스트 홈탭"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"✅ 테스트 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            ]
        }
        
        print(f"📤 테스트 사용자 {test_user_id}에게 간단한 홈탭 전송 중...")
        response = client.views_publish(
            user_id=test_user_id,
            view=simple_view
        )
        
        if response.get("ok"):
            print("✅ Slack API 직접 호출 성공!")
            return True
        else:
            print(f"❌ Slack API 호출 실패: {response}")
            return False
            
    except Exception as e:
        print(f"❌ Slack API 테스트 실패: {e}")
        return False

def create_timeout_safe_home_tab():
    """Timeout 안전한 홈탭 버전 생성"""
    print("\n🛡️ Timeout 안전한 홈탭 생성")
    
    # 매우 간단한 홈탭 뷰
    safe_view = {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🏢 회의실 예약 시스템"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📅 *회의실 예약하기*\n아래 버튼을 클릭하여 새로운 회의를 예약하세요."
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📅 예약하기"
                    },
                    "style": "primary",
                    "action_id": "home_make_reservation"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 `/회의실예약` 또는 `/회의실조회` 명령어도 사용할 수 있습니다."
                    }
                ]
            }
        ]
    }
    
    print("✅ 안전한 홈탭 뷰 생성 완료")
    return safe_view

def main():
    print("🚀 홈탭 '계속 진행중인 작업입니다' 문제 진단 시작")
    print("=" * 60)
    
    # 1. 구성 요소 테스트
    success, message = test_home_tab_components()
    
    if not success:
        print(f"\n🚨 핵심 문제 발견: {message}")
        print("해결 방법:")
        print("1. Notion API 키와 데이터베이스 ID 확인")
        print("2. Docker 컨테이너 재시작")
        print("3. 네트워크 연결 상태 확인")
        return
    
    print(f"\n✅ 구성 요소 테스트 완료: {message}")
    
    # 2. Slack API 직접 테스트
    print("\n" + "=" * 60)
    if test_slack_api_direct():
        print("✅ Slack API 직접 호출도 성공합니다.")
        print("\n🎯 추천 해결 방법:")
        print("1. Socket Mode 이벤트 처리 timeout 증가")
        print("2. 홈탭 이벤트 핸들러를 비동기 처리로 변경")
        print("3. Notion 조회를 캐싱으로 최적화")
    else:
        print("❌ Slack API 직접 호출도 실패합니다.")
        print("Slack Bot Token이나 권한을 확인해주세요.")
    
    # 3. 안전한 홈탭 생성
    print("\n" + "=" * 60)
    safe_view = create_timeout_safe_home_tab()
    
    print("\n📋 권장 임시 해결책:")
    print("1. 현재 홈탭 핸들러를 간단한 버전으로 교체")
    print("2. Notion 조회를 비동기로 처리")
    print("3. 폴백 메커니즘 강화")

if __name__ == "__main__":
    main() 
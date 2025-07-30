#!/usr/bin/env python3
# debug_home_tab.py
# Docker 환경에서 홈탭 기능 문제를 진단하는 스크립트

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("debug.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

def check_environment():
    """환경변수 확인"""
    print("=" * 50)
    print("🔍 환경변수 검사")
    print("=" * 50)
    
    required_vars = [
        "SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN", 
        "NOTION_API_KEY",
        "NOTION_DATABASE_ID"
    ]
    
    all_ok = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked_value = value[:10] + "..." if len(value) > 10 else value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: 설정되지 않음")
            all_ok = False
    
    return all_ok

def test_notion_connection():
    """Notion API 연결 테스트"""
    print("\n" + "=" * 50)
    print("🔍 Notion API 연결 테스트")
    print("=" * 50)
    
    try:
        from services.notion_service import NotionService
        from config import AppConfig
        
        notion_service = NotionService(AppConfig())
        
        # 간단한 데이터베이스 쿼리 테스트
        today_reservations = notion_service.get_reservations_by_date()
        print(f"✅ Notion API 연결 성공 - 오늘 예약: {len(today_reservations)}개")
        return True
        
    except Exception as e:
        print(f"❌ Notion API 연결 실패: {e}")
        logger.error(f"Notion API 연결 실패: {e}", exc_info=True)
        return False

def test_slack_connection():
    """Slack API 연결 테스트"""
    print("\n" + "=" * 50)
    print("🔍 Slack API 연결 테스트")
    print("=" * 50)
    
    try:
        from slack_sdk import WebClient
        from config import get_slack_config
        
        slack_config = get_slack_config()
        client = WebClient(token=slack_config.bot_token)
        
        # Bot 정보 조회
        response = client.auth_test()
        if response["ok"]:
            print(f"✅ Slack API 연결 성공 - Bot ID: {response['user_id']}")
            print(f"   Bot 이름: {response['user']}")
            print(f"   팀 이름: {response['team']}")
            return True
        else:
            print(f"❌ Slack API 연결 실패: {response.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Slack API 연결 실패: {e}")
        logger.error(f"Slack API 연결 실패: {e}", exc_info=True)
        return False

def test_home_tab_view():
    """홈탭 뷰 생성 테스트"""
    print("\n" + "=" * 50)
    print("🔍 홈탭 뷰 생성 테스트")
    print("=" * 50)
    
    try:
        from services.slack_service import build_home_tab_view
        from services.notion_service import NotionService
        from config import AppConfig
        
        # 테스트용 예약 데이터 가져오기
        notion_service = NotionService(AppConfig())
        reservations = notion_service.get_reservations_by_date()
        
        # 홈탭 뷰 생성
        home_view = build_home_tab_view(reservations)
        
        print(f"✅ 홈탭 뷰 생성 성공")
        print(f"   블록 수: {len(home_view.get('blocks', []))}")
        
        # 액션 ID 확인
        for i, block in enumerate(home_view.get('blocks', [])):
            if block.get('type') == 'actions':
                for element in block.get('elements', []):
                    action_id = element.get('action_id')
                    if action_id:
                        print(f"   Action ID 발견: {action_id}")
            elif block.get('type') == 'section' and 'accessory' in block:
                action_id = block['accessory'].get('action_id')
                if action_id:
                    print(f"   Accessory Action ID 발견: {action_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ 홈탭 뷰 생성 실패: {e}")
        logger.error(f"홈탭 뷰 생성 실패: {e}", exc_info=True)
        return False

def test_imports():
    """모든 필요한 모듈 임포트 테스트"""
    print("\n" + "=" * 50)
    print("🔍 모듈 임포트 테스트")
    print("=" * 50)
    
    modules_to_test = [
        "config",
        "utils.constants",
        "services.notion_service",
        "services.slack_service",
        "services.reservation_service",
        "views.reservation_view",
        "exceptions"
    ]
    
    all_ok = True
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except Exception as e:
            print(f"❌ {module_name}: {e}")
            all_ok = False
    
    return all_ok

def main():
    """메인 진단 함수"""
    print("🚀 Docker 환경 홈탭 진단 시작")
    print(f"🕐 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # 환경변수 검사
    results['environment'] = check_environment()
    
    # 모듈 임포트 테스트
    results['imports'] = test_imports()
    
    # Notion API 연결 테스트
    if results['environment'] and results['imports']:
        results['notion'] = test_notion_connection()
        results['slack'] = test_slack_connection()
        results['home_tab'] = test_home_tab_view()
    else:
        print("\n⚠️ 기본 요구사항을 만족하지 않아 추가 테스트를 건너뜁니다.")
        results['notion'] = False
        results['slack'] = False
        results['home_tab'] = False
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 진단 결과 요약")
    print("=" * 50)
    
    for test_name, result in results.items():
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_name.capitalize()}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 모든 테스트가 통과했습니다!")
        print("홈탭 문제는 다른 원인일 수 있습니다:")
        print("- Slack 앱의 Home Tab 권한 설정 확인")
        print("- EC2 보안그룹에서 아웃바운드 HTTPS 트래픽 허용 확인")
        print("- Docker 컨테이너 로그 확인: docker logs <container_name>")
    else:
        print("\n🔧 실패한 테스트를 해결해주세요.")
    
    print(f"\n📝 상세 로그는 debug.log 파일을 확인하세요.")

if __name__ == "__main__":
    main() 
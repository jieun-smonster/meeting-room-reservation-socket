#!/usr/bin/env python3
# docker_env_check.py
# EC2 Docker 환경에서 홈탭 문제를 진단하는 스크립트

import os
import sys
import time
import socket
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def check_environment_variables():
    """환경변수 확인"""
    print("🔐 환경변수 검증")
    required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "NOTION_API_KEY", "NOTION_DATABASE_ID"]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # 토큰의 앞부분만 표시 (보안)
            masked = value[:10] + "..." if len(value) > 10 else value
            print(f"✅ {var}: {masked}")
        else:
            print(f"❌ {var}: 설정되지 않음")
            return False
    return True

def check_network_connectivity():
    """네트워크 연결 확인"""
    print("\n🌐 네트워크 연결 확인")
    
    test_urls = [
        ("Slack API", "https://slack.com/api/api.test"),
        ("Notion API", "https://api.notion.com/v1/users/me"),
        ("Google DNS", "https://8.8.8.8"),
    ]
    
    for name, url in test_urls:
        try:
            start_time = time.time()
            response = requests.get(url, timeout=5)
            elapsed = time.time() - start_time
            print(f"✅ {name}: {response.status_code} ({elapsed:.2f}초)")
        except requests.exceptions.Timeout:
            print(f"⏰ {name}: Timeout (5초 초과)")
        except requests.exceptions.ConnectionError:
            print(f"❌ {name}: 연결 실패")
        except Exception as e:
            print(f"❌ {name}: {e}")

def check_slack_socket_connection():
    """Slack Socket Mode 연결 확인"""
    print("\n📡 Slack Socket Mode 연결 테스트")
    
    try:
        from slack_sdk import WebClient
        from slack_bolt import App
        
        # 환경변수에서 토큰 가져오기
        bot_token = os.getenv("SLACK_BOT_TOKEN")
        app_token = os.getenv("SLACK_APP_TOKEN")
        
        if not bot_token or not app_token:
            print("❌ Slack 토큰이 설정되지 않음")
            return False
        
        # WebClient 테스트
        client = WebClient(token=bot_token)
        
        start_time = time.time()
        auth_response = client.auth_test()
        auth_elapsed = time.time() - start_time
        
        if auth_response.get("ok"):
            print(f"✅ Slack Bot 인증 성공 ({auth_elapsed:.2f}초)")
            print(f"   Bot User: {auth_response.get('user', 'Unknown')}")
            print(f"   Team: {auth_response.get('team', 'Unknown')}")
        else:
            print(f"❌ Slack Bot 인증 실패: {auth_response}")
            return False
        
        # Socket Mode App 테스트 (실제 연결은 하지 않음)
        try:
            app = App(token=bot_token)
            print("✅ Slack Bolt App 초기화 성공")
        except Exception as app_error:
            print(f"❌ Slack Bolt App 초기화 실패: {app_error}")
            return False
            
        return True
        
    except ImportError as e:
        print(f"❌ Slack SDK 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ Slack 연결 테스트 실패: {e}")
        return False

def check_notion_api():
    """Notion API 연결 및 응답 시간 확인"""
    print("\n📚 Notion API 연결 테스트")
    
    try:
        api_key = os.getenv("NOTION_API_KEY")
        database_id = os.getenv("NOTION_DATABASE_ID")
        
        if not api_key or not database_id:
            print("❌ Notion 설정이 누락됨")
            return False
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        
        # 1. Notion API 기본 연결 테스트
        start_time = time.time()
        response = requests.get("https://api.notion.com/v1/users/me", headers=headers, timeout=10)
        auth_elapsed = time.time() - start_time
        
        if response.status_code == 200:
            print(f"✅ Notion API 인증 성공 ({auth_elapsed:.2f}초)")
        else:
            print(f"❌ Notion API 인증 실패: {response.status_code} - {response.text}")
            return False
        
        # 2. 데이터베이스 조회 테스트
        start_time = time.time()
        db_url = f"https://api.notion.com/v1/databases/{database_id}/query"
        
        # 오늘 날짜로 필터링
        today = datetime.now().strftime("%Y-%m-%d")
        payload = {
            "filter": {
                "property": "날짜",
                "date": {
                    "equals": today
                }
            },
            "page_size": 10
        }
        
        response = requests.post(db_url, headers=headers, json=payload, timeout=15)
        db_elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            results_count = len(data.get("results", []))
            print(f"✅ Notion 데이터베이스 조회 성공 ({db_elapsed:.2f}초)")
            print(f"   오늘 예약 수: {results_count}")
            
            if db_elapsed > 5.0:
                print(f"⚠️ Notion 응답이 느립니다 ({db_elapsed:.2f}초). 홈탭 timeout 원인일 수 있습니다.")
                
        else:
            print(f"❌ Notion 데이터베이스 조회 실패: {response.status_code} - {response.text}")
            return False
            
        return True
        
    except requests.exceptions.Timeout:
        print("⏰ Notion API Timeout (15초 초과)")
        return False
    except Exception as e:
        print(f"❌ Notion API 테스트 실패: {e}")
        return False

def check_docker_environment():
    """Docker 환경 정보 확인"""
    print("\n🐳 Docker 환경 정보")
    
    # 현재 시간과 시간대
    print(f"현재 시간: {datetime.now()}")
    print(f"시간대: {time.tzname}")
    
    # 환경변수 확인
    python_path = os.getenv("PYTHONPATH", "설정안됨")
    log_level = os.getenv("LOG_LEVEL", "설정안됨")
    print(f"PYTHONPATH: {python_path}")
    print(f"LOG_LEVEL: {log_level}")
    
    # 메모리 및 디스크 정보
    try:
        import psutil
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        print(f"메모리 사용률: {memory.percent}%")
        print(f"디스크 사용률: {disk.percent}%")
    except ImportError:
        print("psutil 설치되지 않음 - 시스템 정보 조회 불가")
    
    # 네트워크 인터페이스
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"호스트명: {hostname}")
        print(f"로컬 IP: {local_ip}")
    except Exception as e:
        print(f"네트워크 정보 조회 실패: {e}")

def test_home_tab_simulation():
    """홈탭 처리 시뮬레이션"""
    print("\n🏠 홈탭 처리 시뮬레이션")
    
    try:
        total_start = time.time()
        
        # 1단계: Notion 데이터 조회
        print("1️⃣ Notion 데이터 조회 중...")
        from services.notion_service import NotionService
        from config import AppConfig
        
        notion_start = time.time()
        notion_service = NotionService(AppConfig())
        reservations = notion_service.get_reservations_by_date()
        notion_elapsed = time.time() - notion_start
        
        print(f"   ✅ 완료 ({notion_elapsed:.2f}초) - 예약 수: {len(reservations)}")
        
        # 2단계: 홈탭 뷰 구성
        print("2️⃣ 홈탭 뷰 구성 중...")
        view_start = time.time()
        
        from services.slack_service import build_home_tab_view
        home_view = build_home_tab_view(reservations)
        view_elapsed = time.time() - view_start
        
        print(f"   ✅ 완료 ({view_elapsed:.2f}초) - 블록 수: {len(home_view.get('blocks', []))}")
        
        # 3단계: JSON 크기 확인
        import json
        view_json = json.dumps(home_view)
        view_size = len(view_json.encode('utf-8'))
        print(f"   📏 홈탭 크기: {view_size:,} bytes")
        
        total_elapsed = time.time() - total_start
        print(f"\n✅ 시뮬레이션 완료 - 총 소요시간: {total_elapsed:.2f}초")
        
        # 성능 평가
        if total_elapsed > 10:
            print("🚨 처리 시간이 10초를 초과합니다. Slack timeout 발생 가능!")
        elif total_elapsed > 5:
            print("⚠️ 처리 시간이 5초를 초과합니다. 최적화 필요!")
        else:
            print("✅ 처리 시간이 적절합니다.")
            
        return True
        
    except Exception as e:
        print(f"❌ 시뮬레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🔍 EC2 Docker 환경 진단 시작")
    print("=" * 60)
    
    checks = [
        ("환경변수", check_environment_variables),
        ("네트워크 연결", check_network_connectivity), 
        ("Slack 연결", check_slack_socket_connection),
        ("Notion API", check_notion_api),
        ("Docker 환경", check_docker_environment),
        ("홈탭 시뮬레이션", test_home_tab_simulation)
    ]
    
    results = {}
    
    for name, check_func in checks:
        print(f"\n{'='*20} {name} {'='*20}")
        try:
            if check_func == check_docker_environment:
                check_func()  # 이 함수는 boolean을 반환하지 않음
                results[name] = True
            else:
                results[name] = check_func()
        except Exception as e:
            print(f"❌ {name} 검사 중 오류: {e}")
            results[name] = False
    
    # 결과 요약
    print(f"\n{'='*20} 진단 결과 요약 {'='*20}")
    
    for name, success in results.items():
        status = "✅ 정상" if success else "❌ 문제 발견"
        print(f"{name}: {status}")
    
    # 권장사항
    failed_checks = [name for name, success in results.items() if not success]
    
    if not failed_checks:
        print("\n🎉 모든 검사를 통과했습니다!")
        print("홈탭 문제가 지속되면 Slack Socket Mode 설정을 확인해보세요.")
    else:
        print(f"\n🚨 다음 항목들을 확인해주세요: {', '.join(failed_checks)}")

if __name__ == "__main__":
    main() 
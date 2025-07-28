# 🤖 회의실 예약 슬랙봇 (v2.0 - Socket Mode)

<br/>

<p align="center">
  <img src="https://github.com/user-attachments/assets/f023f5e1-3733-481a-9368-885a5438e53b" width="200" alt="Bot Logo">
</p>

<p align="center">
  <strong>Notion과 연동되는 슬랙봇으로 회의실 예약 자동화</strong>
</p>

<p align="center">
  <a href="#-주요-기능">기능</a> •
  <a href="#-아키텍처">아키텍처</a> •
  <a href="#-프로젝트-구조">프로젝트 구조</a> •
  <a href="#-시작하기">시작하기</a> •
  <a href="#-배포-및-운영">배포 및 운영</a> •
  <a href="#-향후-개선-방향">로드맵</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/Slack%20Bolt-Socket%20Mode-blueviolet?logo=slack&style=for-the-badge" alt="Slack Bolt">
  <img src="https://img.shields.io/badge/Notion-API-lightgrey?logo=notion&style=for-the-badge" alt="Notion API">
  <img src="https://img.shields.io/badge/Docker-Compose-blue?logo=docker&style=for-the-badge" alt="Docker">
</p>

---

## 🌟 주요 기능

이 슬랙봇은 단순한 예약 도구를 넘어, 팀의 생산성을 높이는 자동화된 워크플로우를 제공합니다.

| 기능 | 설명 |
| :--- | :--- |
| ⚡ **실시간 예약** | `/회의실예약` 명령어 하나로 즉시 예약 프로세스를 시작할 수 있습니다. |
| 👆 **직관적인 UI** | 슬랙의 Modal(팝업)을 활용하여 누구나 쉽게 회의 제목, 시간, 참석자 등을 입력할 수 있습니다. |
| 🔁 **반복 예약** | '매주 반복' 옵션을 통해 정기적인 회의를 최대 12주까지 한 번에 설정할 수 있습니다. |
| 💥 **충돌 방지** | 예약 시 실시간으로 다른 예약과 시간이 겹치는지 확인하여 더블 부킹을 원천 차단합니다. |
| ✍️ **Notion DB 연동** | 모든 예약은 Notion 데이터베이스에 자동으로 기록되어, 캘린더 뷰 등으로 한눈에 현황을 파악할 수 있습니다. |
| ✏️ **예약 수정 및 취소** | 예약 완료 후 받는 DM의 버튼을 통해 간편하게 예약을 수정하거나 취소할 수 있습니다. |

<br/>

## 🏛️ 아키텍처

이 프로젝트는 **Slack Bolt (Socket Mode)**를 기반으로 구축되어, 외부 웹훅(Webhook) URL 없이도 Slack API와 안정적으로 통신합니다. 이를 통해 방화벽이나 복잡한 네트워크 설정 없이도 로컬 개발 및 운영이 가능합니다.

```
┌───────────────────┐       ┌───────────────────────────────────────────┐
│      Slack        │       │                  Server                   │
│  (Events, Modals) │       │                                           │
└─────────┬─────────┘       └───────────────────────────────────────────┘
          │                 ┌───────────────────┐   ┌───────────────────┐
          │◀─── Websocket ──▶│      app.py       │   │   scheduler.py    │
          │   (Socket Mode) │ (Slack Bolt App)  │   │ (APScheduler)   │
          │                 └─────────┬─────────┘   └─────────┬─────────┘
          │                           │                         │
          └───────────────────────────┼─────────────────────────┘
                                      │
                                      ▼
┌───────────────────┐       ┌───────────────────┐
│   Notion API      │◀──────┤  notion_service   │
│ (Database)        │       │                   │
└───────────────────┘       └───────────────────┘
```

1.  **Slack**: 사용자가 `/회의실예약` 명령어를 입력하거나 버튼을 클릭합니다.
2.  **Socket Mode**: 이 이벤트는 Websocket을 통해 `app.py`에 실시간으로 전달됩니다.
3.  **app.py**: Slack Bolt 앱은 이벤트를 수신하여 `reservation_service`를 호출하고, 필요에 따라 `reservation_view`를 통해 사용자에게 Modal을 보여줍니다.
4.  **reservation_service**: 예약 생성, 수정, 삭제 등 핵심 비즈니스 로직을 처리하며, `notion_service`를 통해 Notion DB와 통신합니다.
5.  **notion_service**: Notion API와 직접 통신하여 데이터를 읽고 쓰는 역할을 담당합니다.


<br/>

## 📂 프로젝트 구조

프로젝트는 역할과 책임에 따라 명확하게 분리되어 있어 유지보수가 용이합니다.

```
.
├── 📜 .env                # API 키 등 민감한 환경 변수 저장
├── 📜 .gitignore           # Git 추적 제외 파일 목록
├── 🐳 Dockerfile           # 운영 환경용 Docker 이미지 빌드 설정
├── 🐳 docker-compose.yml   # Docker 컨테이너 오케스트레이션 설정
├── 📜 requirements.txt     # Python 라이브러리 의존성 목록
│
├── 🚀 app.py               # Slack Bolt 앱의 메인 진입점, 모든 Slack 이벤트 처리
├── ⏰ scheduler.py         # 매일 예약 현황 브리핑 등 정기 작업 스케줄러
├── ⚙️ config.py             # 회의실/팀 목록, Notion 속성명 등 고정 설정값 관리
├── 🚨 exceptions.py        # 사용자 정의 예외 클래스 (ValidationError, ConflictError 등)
│
├── 📦 services/            # 핵심 비즈니스 로직
│   ├── 🤖 slack_service.py   # Slack 메시지 전송 등 Slack 관련 유틸리티
│   ├── ✍️ notion_service.py  # Notion API 연동 로직 (CRUD)
│   └── 📅 reservation_service.py # 예약 생성/수정/삭제 등 핵심 로직
│
└── 🖼️ views/               # Slack에 보여줄 UI (Modal 등)
    └── 📝 reservation_view.py # 예약 생성/수정 Modal의 UI 구조 정의
```

<br/>

## 🚀 시작하기

### 1. 사전 준비

-   **Python 3.9+**
-   **Docker & Docker Compose** (운영 환경용)
-   **Slack App 생성 및 설정**:
    1.  [Slack API](https://api.slack.com/apps)에서 새 앱 생성
    2.  **Socket Mode** 활성화
    3.  **OAuth & Permissions**: 다음 스코프 추가
        -   `chat:write` (메시지 전송)
        -   `commands` (슬래시 명령어)
        -   `users:read` (사용자 정보 조회)
    4.  **Slash Commands**: `/회의실예약` 명령어 생성
    5.  **App-Level Tokens**: `connections:write` 스코프로 토큰 생성 (`xapp-...` 형태)
    6.  **Install to Workspace**: 워크스페이스에 앱 설치 후 **Bot User OAuth Token** (`xoxb-...` 형태) 복사
-   **Notion Integration 생성**:
    1.  [Notion Integrations](https://www.notion.so/my-integrations)에서 새 통합 생성
    2.  **Internal Integration Token** (`secret_...` 형태) 복사

### 2. 로컬 환경에서 실행하기

#### 가. 프로젝트 클론 및 설정

```bash
# 1. 프로젝트 클론
git clone https://github.com/your-username/meeting-room-reservation-socket.git
cd meeting-room-reservation-socket

# 2. 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# 3. 의존성 설치
pip install -r requirements.txt

# 4. .env 파일 생성 및 설정
cp .env.example .env
```

`.env` 파일을 열어 아래 값을 채워주세요.

```dotenv
# .env
SLACK_BOT_TOKEN="xoxb-..."   # Bot User OAuth Token
SLACK_APP_TOKEN="xapp-..."   # App-Level Token
NOTION_API_KEY="secret_..."  # Notion Integration Token
NOTION_DATABASE_ID="..."     # Notion 데이터베이스 ID
SLACK_NOTIFICATION_CHANNEL="C123..." # 일일 브리핑을 받을 채널 ID
```

#### 나. Notion 데이터베이스 준비

1.  Notion에서 새 **전체 페이지 데이터베이스**를 생성합니다.
2.  데이터베이스 우측 상단 `•••` 메뉴 > `+ 연결 추가` > 위에서 만든 Notion 통합(Integration)을 선택하여 DB 접근 권한을 부여합니다.
3.  데이터베이스 속성(Properties)을 `config.py`의 `NOTION_PROPS`와 **정확히 일치하도록** 설정합니다.

#### 다. 애플리케이션 실행 및 로그 확인

**터미널 1: 메인 애플리케이션 실행**

```bash
# 가상환경이 활성화된 상태에서 실행
./venv/bin/python app.py > app.log 2>&1 &
```

**터미널 2: 스케줄러 실행**

```bash
# 가상환경이 활성화된 상태에서 실행
./venv/bin/python scheduler.py > scheduler.log 2>&1 &
```

**로그 실시간 확인**

```bash
# app.py 로그 확인
tail -f app.log

# scheduler.py 로그 확인
tail -f scheduler.log
```

**코드 변경 후 재실행**

1.  실행 중인 프로세스를 종료합니다.
    ```bash
    pkill -f app.py && pkill -f scheduler.py
    ```
2.  다시 실행 명령어를 입력합니다.

---

## 🐳 배포 및 운영 (Docker Compose)

Docker를 사용하면 의존성 문제 없이 어떤 환경에서든 동일하게 프로젝트를 실행할 수 있습니다.

### 1. Docker 이미지 빌드

```bash
# 프로젝트 루트 디렉토리에서 실행
docker-compose build
```

### 2. 컨테이너 실행

```bash
# .env 파일이 준비된 상태에서 실행
docker-compose up -d
```

`-d` 옵션은 컨테이너를 백그라운드에서 실행합니다.

### 3. 로그 확인

```bash
# 전체 서비스 로그 확인
docker-compose logs -f

# 특정 서비스 로그 확인 (예: web)
docker-compose logs -f web
```

### 4. 서비스 중지 및 재시작

```bash
# 서비스 중지 및 컨테이너 삭제
docker-compose down

# 코드 변경 후 재빌드 및 재시작
docker-compose up -d --build
```

<br/>

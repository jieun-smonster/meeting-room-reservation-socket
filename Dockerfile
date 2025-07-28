# 1. 베이스 이미지 선택 (공식 Python 3.9-slim 버전을 사용)
# slim 버전은 가볍고 안정적이라 배포 환경에 적합합니다.
FROM python:3.9-slim

# 2. 작업 디렉토리 설정
# 컨테이너 내에서 명령어가 실행될 기본 경로를 지정합니다.
WORKDIR /app

# 3. 시스템 패키지 업데이트 및 타임존 설정 (선택 사항이지만 권장)
# 스케줄러가 정확한 시간에 동작하도록 한국 시간으로 설정합니다.
RUN apt-get update && apt-get install -y tzdata build-essential &&     ln -fs /usr/share/zoneinfo/Asia/Seoul /etc/localtime &&     dpkg-reconfigure -f noninteractive tzdata

# 4. 의존성 파일 복사 및 설치
# requirements.txt를 먼저 복사하여 설치하면, 코드 변경 시 매번 라이브러리를 새로 설치하지 않아도 되어 빌드 속도가 향상됩니다.
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && python -m pip install --no-cache-dir -r requirements.txt
COPY app.py .

# 5. 프로젝트 전체 코드 복사
# 현재 디렉토리(로컬)의 모든 파일을 컨테이너의 작업 디렉토리(/app)로 복사합니다.
COPY . .

# 6. 컨테이너가 시작될 때 실행할 기본 명령어 설정
# 이 Dockerfile 자체는 app.py를 실행하도록 설정하고, scheduler.py는 docker-compose에서 별도로 실행합니다.
CMD ["python", "app.py"]


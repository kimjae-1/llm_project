FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치 (필요 시)
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 pip 설치
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 소스 복사
COPY . /app

# 포트 오픈 (예: FastAPI 기본 포트)
EXPOSE 8000

# 앱 실행 커맨드 (필요에 따라 변경)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

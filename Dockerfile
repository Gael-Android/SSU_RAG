# UV를 포함한 Python 이미지 사용
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# 작업 디렉토리 설정
WORKDIR /app

# UV를 통한 의존성 설치를 위해 필요한 파일들 복사
COPY pyproject.toml uv.lock ./

# UV를 사용해서 의존성 설치 (가상환경 없이)
RUN uv sync --frozen --no-dev

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# UV를 통해 애플리케이션 실행
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# SSU RAG Chatbot

숭실대학교 공지사항 기반 RAG (Retrieval-Augmented Generation) 챗봇 시스템입니다.

## 기능

- RSS 피드를 통한 자동 공지사항 수집
- 벡터 임베딩을 통한 의미 기반 검색
- OpenAI GPT-3.5를 활용한 자연어 답변 생성
- React 기반의 모던한 채팅 인터페이스
- Docker Compose를 통한 간편한 배포

## 시스템 구성

 - **Backend**: FastAPI + LangChain
- **Frontend**: React + Vite
- **Vector DB**: Milvus
- **LLM**: OpenAI GPT-3.5-turbo
- **Storage**: etcd + MinIO

## 실행 방법

### 1. 환경 변수 설정

`.env` 파일을 생성하고 OpenAI API 키를 설정합니다:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### 2. Docker Compose로 실행

```bash
# 모든 서비스 시작
docker compose up -d

# 특정 서비스만 시작
docker compose up -d ssu-rag frontend
```

### 3. 접속

#### 로컬에서 실행 시
- **채팅 인터페이스**: http://localhost:3001
- **API 문서**: http://localhost:8888/docs
- **Milvus UI (Attu)**: http://localhost:18000

#### 원격 서버에서 실행 시 (SSH 포트 포워딩)
SSH 접속 시 포트 포워딩을 사용하세요:
```bash
ssh -L 3002:localhost:3001 -L 8888:localhost:8888 -L 18000:localhost:18000 user@remote-server
```
그 후 로컬 브라우저에서:
- **채팅 인터페이스**: http://localhost:3002
- **API 문서**: http://localhost:8888/docs
- **Milvus UI (Attu)**: http://localhost:18000

## API 엔드포인트

### 채팅 API
```bash
POST /chat_api
{
  "query": "질문 내용",
  "limit": 5
}
```

### RSS 관련
- `GET /rss/status` - RSS 스케줄러 상태
- `GET /rss/items` - 모든 RSS 아이템 조회
- `POST /rss/fetch` - 즉시 RSS 피드 가져오기

### 벡터 검색 관련
- `POST /vector/process` - RSS 아이템 임베딩 처리
- `GET /vector/stats` - 벡터 DB 통계
- `GET /vector/search?query=검색어` - 유사 콘텐츠 검색

## 프로젝트 구조

```
SSU_RAG/
├── main.py              # FastAPI 메인 앱
├── chains.py            # LangChain 체인 정의
├── embedding_processor.py # 벡터 임베딩 처리
├── rss/                 # RSS 피드 처리
├── scheduler.py         # 스케줄러
├── frontend/            # React 프론트엔드
│   ├── src/
│   │   ├── components/  # React 컴포넌트
│   │   └── styles/      # CSS 스타일
│   └── package.json
├── docker-compose.yml   # Docker 구성
└── Dockerfile          # 백엔드 Docker 이미지
```

## 개발 환경 설정

### 백엔드 로컬 실행
```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 프론트엔드 로컬 실행
```bash
cd frontend
npm install
npm run dev
```

## 주의사항

- OpenAI API 키가 필요합니다
- 첫 실행 시 Milvus 초기화에 시간이 걸릴 수 있습니다
- RSS 피드는 1시간마다 자동으로 업데이트됩니다

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

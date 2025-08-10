# SSU RAG Frontend

React 기반의 SSU RAG 챗봇 프론트엔드입니다.

## 특징

- OpenAI 스타일의 깔끔한 채팅 인터페이스
- 실시간 응답 표시
- Markdown 및 코드 하이라이팅 지원
- 참고 문서 링크 표시
- 반응형 디자인

## 실행 방법

### Docker Compose (권장)
```bash
docker compose up -d frontend
```

### 로컬 실행
```bash
cd frontend
npm install
npm run dev
```

## 접속
- 로컬 실행: http://localhost:3001
- SSH 포트 포워딩 사용 시: http://localhost:3002

## 기술 스택
- React 18
- Vite
- Axios
- React Markdown
- React Syntax Highlighter

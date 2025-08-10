# SSU RAG 챗봇 배포 메뉴얼

## 📋 개요
이 문서는 SSU RAG 챗봇을 kwkun.com 도메인에 프로덕션 배포하는 전체 과정을 기록한 메뉴얼입니다.

## 🏗️ 아키텍처

```
인터넷 → Cloudflare Tunnel → Nginx (포트 80) → 
    ├── Frontend (React, 포트 3001)
    └── Backend API (FastAPI, 포트 8888)
        └── Milvus Vector DB (포트 19530)
```

## 📦 배포된 서비스

| 서비스 | 컨테이너명 | 포트 | 설명 |
|--------|------------|------|------|
| **Nginx** | SSU_RAG_NGINX | 80, 443 | 리버스 프록시 & 로드밸런서 |
| **Frontend** | SSU_RAG_FRONTEND_PROD | 3001 | React 기반 채팅 인터페이스 |
| **Backend** | SSU_RAG_PROD | 8888 | FastAPI + LangChain RAG |
| **Milvus** | milvus-standalone-prod | 19530 | 벡터 데이터베이스 |
| **Attu** | attu-prod | 18000 | Milvus 관리 UI |
| **MinIO** | milvus-minio-prod | 9001 | 객체 스토리지 |
| **etcd** | milvus-etcd-prod | 2379 | Milvus 메타데이터 |

## 🚀 배포 과정

### 1단계: 개발 환경에서 프로덕션 준비
```bash
# 환경변수 설정
cp env.prod.template .env.prod
nano .env.prod  # OPENAI_API_KEY 설정

# 프로덕션 빌드 및 배포
./deploy.sh start
```

### 2단계: Cloudflare Tunnel 설정
```bash
# Cloudflare Tunnel 설정 확인
cat ~/.cloudflared/config.yml

# 터널 실행
cloudflared tunnel run
```

### 3단계: 시스템 서비스 등록
```bash
# 서비스 파일 설치 (관리자 권한 필요)
sudo cp cloudflared.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## 🔧 주요 설정 파일

### docker-compose.prod.yml
- 프로덕션 환경용 Docker Compose 설정
- 포트 80/443으로 Nginx 노출
- 모든 서비스 `restart: unless-stopped` 설정

### nginx/conf.d/kwkun.com.conf
```nginx
server {
    listen 80;
    server_name kwkun.com www.kwkun.com;
    
    location / {
        proxy_pass http://frontend:80;
    }
    
    location /api/ {
        proxy_pass http://ssu-rag:8000/;
    }
}
```

### ~/.cloudflared/config.yml
```yaml
tunnel: b58ca7f7-a447-4c8e-a7cc-8cb6b2592750
credentials-file: /home/kwkun/.cloudflared/b58ca7f7-a447-4c8e-a7cc-8cb6b2592750.json

ingress:
  - hostname: kwkun.com
    service: http://localhost:80
  - service: http_status:404
```

## 🎯 핵심 기능

### ✅ 대화 메모리
- **세션별 기억**: `session_id` 기반 대화 이력 관리
- **자동 질문 재작성**: 이전 맥락을 고려한 검색 쿼리 생성
- **히스토리 제한**: 최근 8턴까지 유지

### ✅ RAG (검색 증강 생성)
- **벡터 검색**: Milvus를 통한 의미 기반 문서 검색
- **실시간 RSS**: 숭실대학교 관련 최신 정보 자동 수집
- **소스 인용**: 답변에 참고 문서 번호 자동 표시

### ✅ 보안 & 성능
- **Rate Limiting**: API 호출 제한 (10req/sec, burst 20)
- **CORS 설정**: 크로스 오리진 요청 허용
- **정적 파일 캐싱**: JS/CSS 파일 1년 캐시
- **보안 헤더**: XSS, CSRF 등 공격 방지

## 🔄 운영 명령어

### 배포 관리
```bash
./deploy.sh start    # 프로덕션 환경 시작
./deploy.sh stop     # 프로덕션 환경 종료
./deploy.sh restart  # 프로덕션 환경 재시작
./deploy.sh logs     # 서비스 로그 확인
./deploy.sh status   # 서비스 상태 확인
```

### 서비스 상태 확인
```bash
# Docker 컨테이너 상태
docker compose -f docker-compose.prod.yml ps

# Cloudflare Tunnel 상태
systemctl status cloudflared
ps aux | grep cloudflared

# 네트워크 연결 확인
curl http://localhost/
curl http://kwkun.com/
```

### 로그 확인
```bash
# 전체 서비스 로그
docker compose -f docker-compose.prod.yml logs -f

# 개별 서비스 로그
docker compose -f docker-compose.prod.yml logs nginx
docker compose -f docker-compose.prod.yml logs ssu-rag
docker compose -f docker-compose.prod.yml logs frontend

# Cloudflare Tunnel 로그
journalctl -u cloudflared -f
```

## 🆘 문제 해결

### 1. Cloudflare Tunnel Error 1033
**증상**: kwkun.com 접속 시 1033 오류
**원인**: cloudflared 프로세스 중단 또는 잘못된 포트 설정
**해결**:
```bash
# cloudflared 상태 확인
systemctl status cloudflared

# 수동 재시작
cloudflared tunnel run

# 포트 설정 확인
cat ~/.cloudflared/config.yml
```

### 2. 포트 80 사용 중 오류
**증상**: nginx 컨테이너 시작 실패
**원인**: 시스템 nginx나 다른 웹 서버가 포트 80 사용
**해결**:
```bash
# 포트 사용 프로세스 확인
ss -tlnp | grep :80

# 시스템 nginx 중지
sudo systemctl stop nginx
sudo systemctl disable nginx
```

### 3. API 응답 없음
**증상**: 프론트엔드는 되는데 채팅 응답이 없음
**원인**: 백엔드 컨테이너 오류 또는 OpenAI API 키 문제
**해결**:
```bash
# 백엔드 로그 확인
docker compose -f docker-compose.prod.yml logs ssu-rag

# API 키 확인
cat .env.prod | grep OPENAI_API_KEY

# 직접 API 테스트
curl -X POST http://localhost:8888/chat_api \
  -H 'Content-Type: application/json' \
  -d '{"query":"테스트","session_id":"debug"}'
```

### 4. 메모리 기능 작동하지 않음
**증상**: 챗봇이 이전 대화를 기억하지 못함
**원인**: session_id 전송 문제 또는 메모리 저장 오류
**확인**:
```bash
# 백엔드 로그에서 session_id 확인
docker compose -f docker-compose.prod.yml logs ssu-rag | grep "sid="

# 브라우저 개발자도구에서 localStorage 확인
# Application > Local Storage > ssu_rag_session_id
```

## 📊 모니터링

### 성능 지표
- **응답 시간**: 평균 2-5초 (RAG 검색 포함)
- **동시 사용자**: 현재 제한 없음 (Rate Limiting 적용)
- **메모리 사용량**: 컨테이너당 ~500MB

### 접속 통계
- **메인 URL**: https://kwkun.com
- **관리 도구**: http://localhost:18000 (Attu - Milvus 관리)
- **API 문서**: http://localhost:8888/docs

## 🔮 향후 개선 사항

### 보안 강화
- [ ] HTTPS/SSL 인증서 설정
- [ ] API 키 AWS Secrets Manager 연동
- [ ] IP 기반 접근 제한

### 성능 최적화
- [ ] Redis 캐시 도입
- [ ] CDN 연동 (Cloudflare)
- [ ] 데이터베이스 백업 자동화

### 기능 확장
- [ ] 사용자 인증 시스템
- [ ] 대화 내역 영구 저장
- [ ] 다국어 지원

## 📞 지원

**개발자**: kwkun  
**서버**: kun-server (58.140.185.93)  
**도메인**: kwkun.com  
**배포일**: 2025-08-10

---

> 이 메뉴얼은 실제 배포 과정을 기록한 것으로, 향후 유지보수나 재배포 시 참고용으로 활용하세요.

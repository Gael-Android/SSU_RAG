#!/bin/bash

# SSU RAG 프로덕션 배포 스크립트
# 사용법: ./deploy.sh [start|stop|restart|logs|ssl]

set -e

# 설정
DOMAIN="kwkun.com"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

# 색상 출력 함수
print_status() {
    echo -e "\033[1;32m[INFO]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

# 환경변수 파일 확인
check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        print_error "$ENV_FILE 파일이 없습니다."
        print_status "env.prod.template을 복사하여 $ENV_FILE을 생성하세요:"
        echo "cp env.prod.template $ENV_FILE"
        echo "그리고 OPENAI_API_KEY를 설정하세요."
        exit 1
    fi
}

# 서비스 시작
start_services() {
    print_status "SSU RAG 프로덕션 서비스를 시작합니다..."
    check_env_file
    
    # 기존 개발 환경 종료
    if docker compose ps | grep -q "Up"; then
        print_warning "개발 환경을 먼저 종료합니다..."
        docker compose down
    fi
    
    # 프로덕션 환경 시작
    docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d --build
    
    print_status "서비스가 시작되었습니다!"
    print_status "상태 확인: ./deploy.sh logs"
    print_status "도메인: https://$DOMAIN"
}

# 서비스 종료
stop_services() {
    print_status "SSU RAG 프로덕션 서비스를 종료합니다..."
    docker compose -f $COMPOSE_FILE down
    print_status "서비스가 종료되었습니다."
}

# 서비스 재시작
restart_services() {
    print_status "SSU RAG 프로덕션 서비스를 재시작합니다..."
    stop_services
    start_services
}

# 로그 확인
show_logs() {
    print_status "서비스 로그를 표시합니다..."
    docker compose -f $COMPOSE_FILE logs -f --tail=50
}

# SSL 인증서 설정 (Cloudflare Origin Certificate 사용 권장)
setup_ssl() {
    print_status "SSL 인증서 설정을 시작합니다..."
    
    if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
        print_warning "Let's Encrypt 인증서가 없습니다."
        print_status "Cloudflare Origin Certificate를 사용하는 것을 권장합니다:"
        print_status "1. Cloudflare Dashboard > SSL/TLS > Origin Server"
        print_status "2. Create Certificate"
        print_status "3. 생성된 인증서를 다음 위치에 저장:"
        print_status "   /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
        print_status "   /etc/letsencrypt/live/$DOMAIN/privkey.pem"
        print_status ""
        print_status "또는 Certbot을 사용하려면:"
        print_status "sudo apt install certbot"
        print_status "sudo certbot certonly --standalone -d $DOMAIN"
    else
        print_status "SSL 인증서가 이미 존재합니다: /etc/letsencrypt/live/$DOMAIN/"
    fi
}

# 상태 확인
check_status() {
    print_status "서비스 상태를 확인합니다..."
    docker compose -f $COMPOSE_FILE ps
    
    echo ""
    print_status "엔드포인트 테스트:"
    
    # 백엔드 API 테스트
    if curl -sf http://localhost:8888/ > /dev/null; then
        print_status "✅ 백엔드 API: http://localhost:8888/"
    else
        print_error "❌ 백엔드 API 응답 없음"
    fi
    
    # 프론트엔드 테스트
    if curl -sf http://localhost:3001/ > /dev/null; then
        print_status "✅ 프론트엔드: http://localhost:3001/"
    else
        print_error "❌ 프론트엔드 응답 없음"
    fi
    
    # HTTPS 테스트 (SSL이 설정된 경우)
    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        if curl -sf https://$DOMAIN/ > /dev/null; then
            print_status "✅ HTTPS: https://$DOMAIN/"
        else
            print_warning "⚠️  HTTPS 설정 확인 필요"
        fi
    else
        print_warning "⚠️  SSL 인증서 설정 필요"
    fi
}

# 메인 로직
case "${1:-}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    ssl)
        setup_ssl
        ;;
    status)
        check_status
        ;;
    *)
        echo "SSU RAG 프로덕션 배포 스크립트"
        echo ""
        echo "사용법: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start    - 프로덕션 서비스 시작"
        echo "  stop     - 프로덕션 서비스 종료"
        echo "  restart  - 프로덕션 서비스 재시작"
        echo "  logs     - 서비스 로그 확인"
        echo "  ssl      - SSL 인증서 설정 안내"
        echo "  status   - 서비스 상태 확인"
        echo ""
        echo "배포 전 준비사항:"
        echo "1. cp env.prod.template .env.prod"
        echo "2. .env.prod에서 OPENAI_API_KEY 설정"
        echo "3. Cloudflare에서 $DOMAIN A 레코드가 현재 서버 IP로 설정되어 있는지 확인"
        echo "4. ./deploy.sh ssl (SSL 인증서 설정)"
        echo "5. ./deploy.sh start"
        ;;
esac

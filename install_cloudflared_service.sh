#!/bin/bash
echo "🔧 Cloudflared 서비스 설치 중..."

# 서비스 파일 복사
sudo cp cloudflared.service /etc/systemd/system/

# 시스템 데몬 새로고침
sudo systemctl daemon-reload

# 서비스 활성화 (부팅 시 자동 시작)
sudo systemctl enable cloudflared

# 기존 백그라운드 프로세스 종료
pkill -f "cloudflared tunnel run" || true

# 서비스 시작
sudo systemctl start cloudflared

# 상태 확인
echo "✅ Cloudflare Tunnel 서비스 상태:"
sudo systemctl status cloudflared --no-pager -l

echo ""
echo "🎉 완료! cloudflared가 시스템 서비스로 등록되었습니다."
echo "📋 관리 명령어:"
echo "  sudo systemctl status cloudflared   # 상태 확인"
echo "  sudo systemctl restart cloudflared  # 재시작"
echo "  sudo systemctl stop cloudflared     # 중지"
echo "  journalctl -u cloudflared -f        # 로그 확인"

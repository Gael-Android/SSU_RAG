import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import threading
import time
from rss import get_rss_reader

logger = logging.getLogger(__name__)

class RSSScheduler:
    """RSS 피드를 주기적으로 가져오는 스케줄러"""
    
    def __init__(self, interval_hours: int = 1):
        self.interval_hours = interval_hours
        self.interval_seconds = interval_hours * 3600  # 시간을 초로 변환
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.rss_reader = get_rss_reader()
        self.last_fetch_time: Optional[datetime] = None
        self.fetch_count = 0
        
    def start(self):
        """스케줄러 시작"""
        if self.is_running:
            logger.warning("스케줄러가 이미 실행 중입니다.")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info(f"RSS 스케줄러가 시작되었습니다. (간격: {self.interval_hours}시간)")
        
        # 시작할 때 한 번 실행
        self._fetch_rss()
    
    def stop(self):
        """스케줄러 중지"""
        if not self.is_running:
            logger.warning("스케줄러가 실행 중이 아닙니다.")
            return
            
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        logger.info("RSS 스케줄러가 중지되었습니다.")
    
    def _run_scheduler(self):
        """스케줄러 메인 루프"""
        while self.is_running:
            try:
                # 다음 실행까지 대기
                for _ in range(self.interval_seconds):
                    if not self.is_running:
                        break
                    time.sleep(1)  # 1초씩 체크하여 즉시 중지 가능하도록
                
                if self.is_running:
                    self._fetch_rss()
                    
            except Exception as e:
                logger.error(f"스케줄러 실행 중 오류 발생: {e}")
                # 오류가 발생해도 계속 실행
                time.sleep(60)  # 1분 대기 후 재시도
    
    def _fetch_rss(self):
        """RSS 피드를 가져오기"""
        try:
            logger.info("정기 RSS 피드 가져오기 시작")
            result = self.rss_reader.fetch_feed()
            
            self.last_fetch_time = datetime.now(timezone.utc)
            self.fetch_count += 1
            
            if result["status"] == "success":
                logger.info(f"RSS 피드 가져오기 성공: 새 아이템 {result['new_items']}개")
            else:
                logger.error(f"RSS 피드 가져오기 실패: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"RSS 피드 가져오기 중 예외 발생: {e}")
    
    def get_status(self) -> dict:
        """스케줄러 상태 정보 반환"""
        return {
            "is_running": self.is_running,
            "interval_hours": self.interval_hours,
            "last_fetch_time": self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            "fetch_count": self.fetch_count,
            "next_fetch_in_seconds": None if not self.is_running else self.interval_seconds
        }
    
    def fetch_now(self) -> dict:
        """즉시 RSS 피드 가져오기"""
        logger.info("수동 RSS 피드 가져오기 요청")
        return self.rss_reader.fetch_feed()

# 전역 스케줄러 인스턴스
_scheduler_instance: Optional[RSSScheduler] = None

def get_scheduler() -> RSSScheduler:
    """스케줄러 인스턴스를 반환 (싱글톤)"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = RSSScheduler(interval_hours=1)
    return _scheduler_instance

def start_scheduler():
    """스케줄러 시작"""
    scheduler = get_scheduler()
    scheduler.start()

def stop_scheduler():
    """스케줄러 중지"""
    scheduler = get_scheduler()
    scheduler.stop()

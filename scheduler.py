import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List
import threading
import time
from rss import get_rss_reader
from rss.reader import create_rss_reader_for
from rss.sources import KNOWN_SOURCES
from rss.utils import identifier_to_filename
from embedding_processor import EmbeddingProcessor
import os

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
        # 임베딩 관련 상태
        self.embedding_processor: Optional[EmbeddingProcessor] = None
        self.last_embedding_time: Optional[datetime] = None
        self.last_embedding_result: Optional[dict] = None
        
    def start(self):
        """스케줄러 시작"""
        if self.is_running:
            logger.warning("스케줄러가 이미 실행 중입니다.")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info(f"RSS 스케줄러가 시작되었습니다. (간격: {self.interval_hours}시간)")
        
        # 시작할 때 한 번 비동기로 실행 (앱 스타트업을 블로킹하지 않도록 별도 스레드)
        threading.Thread(target=self._fetch_all, daemon=True).start()
    
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
                    self._fetch_all()
                    
            except Exception as e:
                logger.error(f"스케줄러 실행 중 오류 발생: {e}")
                # 오류가 발생해도 계속 실행
                time.sleep(60)  # 1분 대기 후 재시도
    
    def _fetch_rss(self):
        """기본 RSS 피드를 가져오기 (단일) - 사용 안 함"""
        pass

    def _fetch_all(self):
        """외부 파일의 identifier 목록을 순회하며 모두 수집"""
        sources = [{"identifier": k, "rss_url": v} for k, v in KNOWN_SOURCES.items()]

        for src in sources:
            identifier = src.get("identifier")
            if not identifier:
                continue
            try:
                logger.info("정기 RSS(%s) 피드 가져오기 시작", identifier)
                reader = create_rss_reader_for(identifier)
                result = reader.fetch_feed()
                if result.get("status") == "success":
                    logger.info("[%s] 성공: 새 %d", identifier, result.get("new_items", 0))
                else:
                    logger.error("[%s] 실패: %s", identifier, result.get("error"))
            except Exception as e:
                logger.error("[%s] 수집 중 예외: %s", identifier, e)

        # 수집 후 임베딩 처리 (data 디렉토리 전체 기준, 신규만 처리)
        try:
            self._run_embedding()
        except Exception as e:
            logger.error("임베딩 처리 트리거 중 예외: %s", e)
    
    def get_status(self) -> dict:
        """스케줄러 상태 정보 반환"""
        return {
            "is_running": self.is_running,
            "interval_hours": self.interval_hours,
            "last_fetch_time": self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            "fetch_count": self.fetch_count,
            "next_fetch_in_seconds": None if not self.is_running else self.interval_seconds,
            "last_embedding_time": self.last_embedding_time.isoformat() if self.last_embedding_time else None
        }
    
    def fetch_now(self) -> dict:
        """즉시 모든 RSS 피드 가져오기 (KNOWN_SOURCES 순회)"""
        logger.info("수동 RSS 피드 일괄 가져오기 요청")
        return self.fetch_all()

    def fetch_all(self) -> dict:
        """공개 API: 모든 소스를 순회하여 결과 요약 반환"""
        results = []
        totals = {"new_items": 0, "existing_items": 0, "total_entries": 0}
        for item in [{"identifier": k, "rss_url": v} for k, v in KNOWN_SOURCES.items()]:
            identifier = item["identifier"]
            try:
                reader = create_rss_reader_for(identifier)
                result = reader.fetch_feed()
                results.append({"identifier": identifier, **result})
                if result.get("status") == "success":
                    totals["new_items"] += int(result.get("new_items", 0))
                    totals["existing_items"] += int(result.get("existing_items", 0))
                    totals["total_entries"] += int(result.get("total_entries", 0))
            except Exception as e:
                results.append({
                    "identifier": identifier,
                    "status": "error",
                    "error": str(e),
                })
        # 수집 후 임베딩 처리 (data 디렉토리 전체 기준, 신규만 처리)
        try:
            self._run_embedding()
        except Exception as e:
            logger.error("임베딩 처리 트리거 중 예외: %s", e)
        return {"status": "success", "totals": totals, "results": results}

    def fetch_for(self, identifier: str) -> dict:
        """특정 identifier 피드를 즉시 가져오기"""
        logger.info("수동 RSS 피드 가져오기 요청 - identifier=%s", identifier)
        reader = create_rss_reader_for(identifier)
        result = reader.fetch_feed()
        # 해당 identifier 파일만 대상으로 임베딩 처리
        try:
            self._run_embedding(identifier_to_filename(identifier))
        except Exception as e:
            logger.error("임베딩 처리 트리거 중 예외(identifier=%s): %s", identifier, e)
        return result

    # 내부: 임베딩 프로세서 준비 및 실행
    def _ensure_embedder(self, json_file_path: Optional[str] = None) -> EmbeddingProcessor:
        # data 디렉토리 전체 처리용 임베더는 재사용
        if json_file_path is None or json_file_path == "data":
            if self.embedding_processor is None:
                self.embedding_processor = EmbeddingProcessor(json_file_path or "data")
            return self.embedding_processor
        # 특정 파일 처리 시 임시 인스턴스 사용
        return EmbeddingProcessor(json_file_path)

    def _run_embedding(self, json_file_path: Optional[str] = None) -> dict:
        processor = self._ensure_embedder(json_file_path)
        result = processor.process_all_items()
        self.last_embedding_time = datetime.now(timezone.utc)
        self.last_embedding_result = result
        logger.info("임베딩 처리 완료: %s", result)
        return result

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

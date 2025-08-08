import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import feedparser

from .models import RSSItem
from .storage import RSSStorage
from .utils import clean_html_text, create_content_hash


logger = logging.getLogger(__name__)


class RSSReader:
    """RSS 피드를 읽고 처리하는 메인 클래스"""

    def __init__(self, rss_url: str, storage: Optional[RSSStorage] = None):
        self.rss_url = rss_url
        self.storage = storage or RSSStorage()

    def _parse_rss_item(self, entry: Any) -> RSSItem:
        """feedparser 엔트리를 RSSItem으로 변환"""
        title = getattr(entry, "title", "제목 없음")
        link = getattr(entry, "link", "")
        description_raw = getattr(entry, "description", "")

        # published 날짜 처리
        published = ""
        if hasattr(entry, "published"):
            published = entry.published
        elif hasattr(entry, "updated"):
            published = entry.updated

        # GUID 처리
        guid = getattr(entry, "id", link)

        # 추가 필드들 처리
        author = getattr(entry, "author", None)

        # category 처리 (복수 카테고리가 있을 수 있으므로 첫 번째 사용)
        category = None
        if hasattr(entry, "tags") and entry.tags:
            category = entry.tags[0].get("term", None)
        elif hasattr(entry, "category"):
            category = entry.category

        # enclosure 처리
        enclosure_url = None
        enclosure_type = None
        if hasattr(entry, "enclosures") and entry.enclosures:
            enclosure = entry.enclosures[0]
            enclosure_url = enclosure.get("href", None)
            enclosure_type = enclosure.get("type", None)

        # content:encoded 처리 (원본 HTML)
        content_raw = None
        if hasattr(entry, "content") and entry.content:
            content_raw = entry.content[0].get("value", None)
        elif hasattr(entry, "summary_detail") and entry.summary_detail:
            content_raw = entry.summary_detail.get("value", None)

        # HTML 정리된 텍스트만 저장
        description = clean_html_text(description_raw)
        content = clean_html_text(content_raw) if content_raw else None

        # 콘텐츠 해시 생성 (원본 description 기준으로 중복 체크)
        content_hash = create_content_hash(title, link, description_raw)

        # 현재 시간
        fetched_at = datetime.now(timezone.utc).isoformat()

        return RSSItem(
            title=title,
            link=link,
            description=description,
            published=published,
            guid=guid,
            content_hash=content_hash,
            fetched_at=fetched_at,
            author=author,
            category=category,
            enclosure_url=enclosure_url,
            enclosure_type=enclosure_type,
            content=content,
        )

    def fetch_feed(self) -> Dict[str, Any]:
        """RSS 피드를 가져와서 새 아이템들을 처리"""
        logger.info("RSS 피드를 가져오는 중: %s", self.rss_url)

        try:
            feed = feedparser.parse(self.rss_url)

            if getattr(feed, "bozo", False):
                logger.warning("RSS 피드 파싱 경고: %s", getattr(feed, "bozo_exception", None))

            new_items: List[RSSItem] = []
            existing_items = 0

            for entry in feed.entries:
                rss_item = self._parse_rss_item(entry)

                if self.storage.add_item(rss_item):
                    new_items.append(rss_item)
                    logger.info("새 아이템 추가: %s", rss_item.title)
                else:
                    existing_items += 1

            self.storage.save_items()

            result: Dict[str, Any] = {
                "status": "success",
                "feed_title": getattr(feed.feed, "title", "제목 없음"),
                "feed_description": getattr(feed.feed, "description", ""),
                "total_entries": len(feed.entries),
                "new_items": len(new_items),
                "existing_items": existing_items,
                "fetch_time": datetime.now(timezone.utc).isoformat(),
                "new_items_data": [asdict(item) for item in new_items],
            }

            logger.info(
                "RSS 피드 처리 완료: 새 아이템 %d개, 기존 아이템 %d개",
                len(new_items),
                existing_items,
            )
            return result

        except Exception as exc:  # noqa: BLE001
            logger.error("RSS 피드 가져오기 실패: %s", exc)
            return {
                "status": "error",
                "error": str(exc),
                "fetch_time": datetime.now(timezone.utc).isoformat(),
            }

    def get_all_items(self) -> List[Dict[str, Any]]:
        """모든 아이템을 딕셔너리 형태로 반환"""
        return [asdict(item) for item in self.storage.get_all_items()]

    def get_recent_items(self, count: int = 10) -> List[Dict[str, Any]]:
        """최근 아이템들을 딕셔너리 형태로 반환"""
        return [asdict(item) for item in self.storage.get_recent_items(count)]


# RSS 리더 인스턴스 생성 (싱글톤 패턴)
_rss_reader_instance: Optional[RSSReader] = None


def get_rss_reader() -> RSSReader:
    """RSS 리더 인스턴스를 반환 (싱글톤)"""
    global _rss_reader_instance
    if _rss_reader_instance is None:
        rss_url = "https://ssufid.yourssu.com/scatch.ssu.ac.kr/rss.xml"
        _rss_reader_instance = RSSReader(rss_url)
    return _rss_reader_instance



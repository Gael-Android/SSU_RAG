import feedparser
import json
import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import hashlib
import time
import re
from bs4 import BeautifulSoup
import html

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RSSItem:
    """RSS 아이템을 나타내는 데이터 클래스"""
    title: str
    link: str
    description: str  # HTML 제거된 깔끔한 설명
    published: str
    guid: str
    content_hash: str
    fetched_at: str
    # 추가 필드들
    author: Optional[str] = None
    category: Optional[str] = None
    enclosure_url: Optional[str] = None
    enclosure_type: Optional[str] = None
    content: Optional[str] = None  # HTML 제거된 깔끔한 전체 내용

class RSSStorage:
    """RSS 아이템들을 저장하고 중복을 관리하는 클래스"""
    
    def __init__(self, storage_file: str = "data/rss_items.json"):
        self.storage_file = storage_file
        self.items: Dict[str, RSSItem] = {}
        self.ensure_data_directory()
        self.load_items()
    
    def ensure_data_directory(self):
        """data 디렉토리가 존재하는지 확인하고 없으면 생성"""
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
    
    def load_items(self):
        """저장된 아이템들을 파일에서 로드"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.items = {
                        key: RSSItem(**item_data) 
                        for key, item_data in data.items()
                    }
                logger.info(f"기존 RSS 아이템 {len(self.items)}개를 로드했습니다.")
            except Exception as e:
                logger.error(f"RSS 아이템 로드 중 오류 발생: {e}")
                self.items = {}
    
    def save_items(self):
        """현재 아이템들을 파일에 저장"""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                data = {key: asdict(item) for key, item in self.items.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"RSS 아이템 {len(self.items)}개를 저장했습니다.")
        except Exception as e:
            logger.error(f"RSS 아이템 저장 중 오류 발생: {e}")
    
    def add_item(self, item: RSSItem) -> bool:
        """새 아이템을 추가. 이미 존재하면 False 반환"""
        if item.content_hash in self.items:
            return False
        
        self.items[item.content_hash] = item
        return True
    
    def get_all_items(self) -> List[RSSItem]:
        """모든 아이템을 반환"""
        return list(self.items.values())
    
    def get_recent_items(self, count: int = 10) -> List[RSSItem]:
        """최근 아이템들을 반환"""
        sorted_items = sorted(
            self.items.values(),
            key=lambda x: x.fetched_at,
            reverse=True
        )
        return sorted_items[:count]

class RSSReader:
    """RSS 피드를 읽고 처리하는 메인 클래스"""
    
    def __init__(self, rss_url: str, storage: Optional[RSSStorage] = None):
        self.rss_url = rss_url
        self.storage = storage or RSSStorage()
        
    def _create_content_hash(self, title: str, link: str, description: str) -> str:
        """콘텐츠 해시를 생성하여 중복 확인용으로 사용"""
        content = f"{title}{link}{description}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _clean_html_text(self, html_text: str) -> str:
        """HTML 태그와 특수 이스케이프 문자를 제거하여 깔끔한 텍스트 반환"""
        if not html_text:
            return ""
        
        try:
            # BeautifulSoup을 사용하여 HTML 태그 제거
            soup = BeautifulSoup(html_text, 'html.parser')
            
            # 모든 태그 제거하고 텍스트만 추출
            text = soup.get_text()
            
            # HTML 엔티티 디코딩 (&amp; -> &, &lt; -> < 등)
            text = html.unescape(text)
            
            # 여러 공백, 탭, 줄바꿈을 단일 공백으로 변환
            text = re.sub(r'\s+', ' ', text)
            
            # 앞뒤 공백 제거
            text = text.strip()
            
            # 특수 문자나 이상한 문자들 정리 (선택적)
            # 기본적인 구두점과 한글, 영문, 숫자만 유지
            text = re.sub(r'[^\w\s가-힣.,!?()[\]{}:;"\'-]', '', text)
            
            return text
            
        except Exception as e:
            logger.warning(f"HTML 텍스트 정리 중 오류 발생: {e}")
            # 오류 발생시 최소한의 정리만 수행
            text = re.sub(r'<[^>]+>', '', html_text)  # 간단한 태그 제거
            text = html.unescape(text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
    
    def _parse_rss_item(self, entry: Any) -> RSSItem:
        """feedparser 엔트리를 RSSItem으로 변환"""
        title = getattr(entry, 'title', '제목 없음')
        link = getattr(entry, 'link', '')
        description_raw = getattr(entry, 'description', '')
        
        # published 날짜 처리
        published = ''
        if hasattr(entry, 'published'):
            published = entry.published
        elif hasattr(entry, 'updated'):
            published = entry.updated
        
        # GUID 처리
        guid = getattr(entry, 'id', link)
        
        # 추가 필드들 처리
        author = getattr(entry, 'author', None)
        
        # category 처리 (복수 카테고리가 있을 수 있으므로 첫 번째 사용)
        category = None
        if hasattr(entry, 'tags') and entry.tags:
            category = entry.tags[0].get('term', None)
        elif hasattr(entry, 'category'):
            category = entry.category
        
        # enclosure 처리
        enclosure_url = None
        enclosure_type = None
        if hasattr(entry, 'enclosures') and entry.enclosures:
            enclosure = entry.enclosures[0]  # 첫 번째 enclosure 사용
            enclosure_url = enclosure.get('href', None)
            enclosure_type = enclosure.get('type', None)
        
        # content:encoded 처리 (원본 HTML)
        content_raw = None
        if hasattr(entry, 'content') and entry.content:
            content_raw = entry.content[0].get('value', None)
        elif hasattr(entry, 'summary_detail') and entry.summary_detail:
            content_raw = entry.summary_detail.get('value', None)
        
        # HTML 정리된 텍스트만 저장
        description = self._clean_html_text(description_raw)
        content = self._clean_html_text(content_raw) if content_raw else None
        
        # 콘텐츠 해시 생성 (원본 description 기준으로 중복 체크)
        content_hash = self._create_content_hash(title, link, description_raw)
        
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
            content=content
        )
    
    def fetch_feed(self) -> Dict[str, Any]:
        """RSS 피드를 가져와서 새 아이템들을 처리"""
        logger.info(f"RSS 피드를 가져오는 중: {self.rss_url}")
        
        try:
            # RSS 피드 파싱
            feed = feedparser.parse(self.rss_url)
            
            if feed.bozo:
                logger.warning(f"RSS 피드 파싱 경고: {feed.bozo_exception}")
            
            new_items = []
            existing_items = 0
            
            # 각 엔트리 처리
            for entry in feed.entries:
                rss_item = self._parse_rss_item(entry)
                
                if self.storage.add_item(rss_item):
                    new_items.append(rss_item)
                    logger.info(f"새 아이템 추가: {rss_item.title}")
                else:
                    existing_items += 1
            
            # 저장
            self.storage.save_items()
            
            result = {
                "status": "success",
                "feed_title": getattr(feed.feed, 'title', '제목 없음'),
                "feed_description": getattr(feed.feed, 'description', ''),
                "total_entries": len(feed.entries),
                "new_items": len(new_items),
                "existing_items": existing_items,
                "fetch_time": datetime.now(timezone.utc).isoformat(),
                "new_items_data": [asdict(item) for item in new_items]
            }
            
            logger.info(f"RSS 피드 처리 완료: 새 아이템 {len(new_items)}개, 기존 아이템 {existing_items}개")
            return result
            
        except Exception as e:
            logger.error(f"RSS 피드 가져오기 실패: {e}")
            return {
                "status": "error",
                "error": str(e),
                "fetch_time": datetime.now(timezone.utc).isoformat()
            }
    
    def get_all_items(self) -> List[Dict[str, Any]]:
        """모든 아이템을 딕셔너리 형태로 반환"""
        return [asdict(item) for item in self.storage.get_all_items()]
    
    def get_recent_items(self, count: int = 10) -> List[Dict[str, Any]]:
        """최근 아이템들을 딕셔너리 형태로 반환"""
        return [asdict(item) for item in self.storage.get_recent_items(count)]

# RSS 리더 인스턴스 생성 (싱글톤 패턴)
_rss_reader_instance = None

def get_rss_reader() -> RSSReader:
    """RSS 리더 인스턴스를 반환 (싱글톤)"""
    global _rss_reader_instance
    if _rss_reader_instance is None:
        rss_url = "https://ssufid.yourssu.com/scatch.ssu.ac.kr/rss.xml"
        _rss_reader_instance = RSSReader(rss_url)
    return _rss_reader_instance

from dataclasses import dataclass
from typing import Optional


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



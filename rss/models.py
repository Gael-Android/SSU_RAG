from dataclasses import dataclass, field
from typing import Optional, List


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
    anchor_hrefs: List[str] = field(default_factory=list)  # 본문 내 a 태그 href 목록
    identifier: str = "scatch.ssu.ac.kr"



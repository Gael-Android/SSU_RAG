import hashlib
import html
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


def create_content_hash(title: str, link: str, description_raw: str) -> str:
    """콘텐츠 해시를 생성하여 중복 확인용으로 사용"""
    content = f"{title}{link}{description_raw}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def clean_html_text(html_text: Optional[str]) -> str:
    """HTML 태그와 특수 이스케이프 문자를 제거하여 깔끔한 텍스트 반환"""
    if not html_text:
        return ""

    try:
        soup = BeautifulSoup(html_text, "html.parser")
        text = soup.get_text()
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text)
        text = text.strip()
        text = re.sub(r"[^\w\s가-힣.,!?()[\]{}:;\"'-]", "", text)
        return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("HTML 텍스트 정리 중 오류 발생: %s", exc)
        text = re.sub(r"<[^>]+>", "", html_text)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text



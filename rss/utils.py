import hashlib
import html
import logging
import re
from typing import Optional, List
from urllib.parse import urlparse

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


def extract_anchor_hrefs(html_text: Optional[str]) -> List[str]:
    """HTML에서 <a> 태그의 href 값을 모두 추출하여 리스트로 반환"""
    if not html_text:
        return []

    try:
        soup = BeautifulSoup(html_text, "html.parser")
        hrefs: List[str] = []
        for a in soup.find_all("a"):
            href = a.get("href")
            if href:
                hrefs.append(href.strip())
        return hrefs
    except Exception as exc:  # noqa: BLE001
        logger.warning("a 태그 href 추출 중 오류 발생: %s", exc)
        return []


def normalize_hrefs(hrefs: List[str], identifier: str) -> List[str]:
    """상대/스킴 없는 href를 identifier 도메인을 사용해 절대 URL로 정규화"""
    normalized: List[str] = []
    base = f"https://{identifier}"
    for href in hrefs:
        if not href:
            continue
        href = href.strip()
        if href.startswith("http://") or href.startswith("https://"):
            normalized.append(href)
        elif href.startswith("/"):
            normalized.append(base + href)
        else:
            normalized.append(base + "/" + href)
    return normalized


def rewrite_download_urls(hrefs: List[str], identifier: str) -> List[str]:
    """다운로드 링크는 도메인을 제거하고 경로+쿼리만 붙여 https://{identifier}{path}?{query} 로 재작성"""
    rewritten: List[str] = []
    base = f"https://{identifier}"
    for raw in hrefs:
        if not raw:
            continue
        href = raw.strip()
        if "download.php" not in href:
            rewritten.append(href)
            continue

        # base/https://example.com/... 형태로 잘못된 값 정리
        if href.startswith(base + "/http://") or href.startswith(base + "/https://"):
            href = href[len(base) + 1 :]

        parsed = urlparse(href)
        # 절대/상대 모두 처리: 경로와 쿼리만 사용
        path = parsed.path or ""
        query = parsed.query or ""
        new_href = base + path + ("?" + query if query else "")
        rewritten.append(new_href)
    return rewritten


def identifier_to_filename(identifier: str) -> str:
    """identifier를 data/{identifier의 .과 /를 _로 교체}.json 형태로 변환"""
    safe = (identifier or "").strip().replace(".", "_").replace("/", "_")
    if not safe:
        safe = "rss_items"
    return f"data/{safe}.json"


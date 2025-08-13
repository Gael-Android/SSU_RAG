import json
import os
from typing import List, Dict


def load_sources_from_file(file_path: str) -> List[Dict[str, str]]:
    """외부 JSON 파일에서 identifier-RSS 쌍을 로드

    지원 포맷:
    - 배열: [{"identifier": "...", "rss_url": "..."}, ...]
    - 맵: {"identifier": "rss_url", ...}
    """
    if not file_path:
        return []

    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    sources: List[Dict[str, str]] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            identifier = item.get("identifier")
            rss_url = item.get("rss_url")
            if identifier and rss_url:
                sources.append({"identifier": identifier, "rss_url": rss_url})
    elif isinstance(data, dict):
        for identifier, rss_url in data.items():
            if isinstance(identifier, str) and isinstance(rss_url, str):
                sources.append({"identifier": identifier, "rss_url": rss_url})

    return sources



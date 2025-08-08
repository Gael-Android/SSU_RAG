import json
import logging
import os
from dataclasses import asdict
from typing import Dict, List

from .models import RSSItem


logger = logging.getLogger(__name__)


class RSSStorage:
    """RSS 아이템들을 저장하고 중복을 관리하는 클래스"""

    def __init__(self, storage_file: str = "data/rss_items.json"):
        self.storage_file = storage_file
        self.items: Dict[str, RSSItem] = {}
        self.ensure_data_directory()
        self.load_items()

    def ensure_data_directory(self) -> None:
        """data 디렉토리가 존재하는지 확인하고 없으면 생성"""
        os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)

    def load_items(self) -> None:
        """저장된 아이템들을 파일에서 로드"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.items = {
                        key: RSSItem(**item_data) for key, item_data in data.items()
                    }
                logger.info("기존 RSS 아이템 %d개를 로드했습니다.", len(self.items))
            except Exception as exc:  # noqa: BLE001
                logger.error("RSS 아이템 로드 중 오류 발생: %s", exc)
                self.items = {}

    def save_items(self) -> None:
        """현재 아이템들을 파일에 저장"""
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                data = {key: asdict(item) for key, item in self.items.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("RSS 아이템 %d개를 저장했습니다.", len(self.items))
        except Exception as exc:  # noqa: BLE001
            logger.error("RSS 아이템 저장 중 오류 발생: %s", exc)

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
            key=lambda item: item.fetched_at,
            reverse=True,
        )
        return sorted_items[:count]



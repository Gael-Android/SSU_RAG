"""
RSS 데이터 임베딩 처리 메인 모듈
JSON 파일에서 RSS 아이템을 읽어 새로운 항목만 임베딩하여 벡터 DB에 저장합니다.
"""

import json
import os
from typing import Dict, List
from datetime import datetime
import logging
from vector_store import VectorStore

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingProcessor:
    def __init__(self, 
                 json_file_path: str = "data/rss_items.json",
                 milvus_host: str = None,
                 milvus_port: str = "19530"):
        """
        임베딩 처리기 초기화
        
        Args:
            json_file_path: RSS 아이템이 저장된 JSON 파일 경로
            milvus_host: Milvus 서버 호스트
            milvus_port: Milvus 서버 포트
        """
        self.json_file_path = json_file_path
        
        # milvus_host 자동 설정 (Docker 환경 고려)
        if milvus_host is None:
            milvus_host = os.getenv("MILVUS_HOST", "localhost")
            # Docker 환경에서는 서비스 이름으로 접근
            if os.getenv("DOCKER_ENV"):
                milvus_host = "milvus"
        
        # 벡터 스토어 초기화
        self.vector_store = VectorStore(
            milvus_host=milvus_host,
            milvus_port=milvus_port
        )
        
        logger.info("임베딩 처리기가 초기화되었습니다.")
    
    def load_rss_items(self) -> Dict[str, Dict]:
        """JSON 파일에서 RSS 아이템들을 로드"""
        try:
            if not os.path.exists(self.json_file_path):
                logger.error(f"JSON 파일을 찾을 수 없습니다: {self.json_file_path}")
                return {}
            
            with open(self.json_file_path, 'r', encoding='utf-8') as file:
                items = json.load(file)
            
            logger.info(f"총 {len(items)}개의 RSS 아이템을 로드했습니다.")
            return items
            
        except Exception as e:
            logger.error(f"JSON 파일 로드 실패: {e}")
            return {}
    
    def filter_new_items(self, all_items: Dict[str, Dict]) -> List[Dict]:
        """이미 처리되지 않은 새로운 아이템들만 필터링"""
        new_items = []
        
        for content_hash, item_data in all_items.items():
            # content_hash가 아이템 데이터에 없다면 추가
            if "content_hash" not in item_data:
                item_data["content_hash"] = content_hash
            
            # 이미 처리된 아이템인지 확인
            if not self.vector_store.is_item_processed(content_hash):
                new_items.append(item_data)
        
        logger.info(f"새로운 아이템 {len(new_items)}개를 발견했습니다.")
        return new_items
    
    def process_all_items(self) -> Dict[str, int]:
        """모든 RSS 아이템을 처리하여 새로운 것들만 임베딩"""
        try:
            # RSS 아이템 로드
            all_items = self.load_rss_items()
            if not all_items:
                logger.warning("처리할 RSS 아이템이 없습니다.")
                return {"total": 0, "new": 0, "processed": 0}
            
            # 새로운 아이템 필터링
            new_items = self.filter_new_items(all_items)
            
            if not new_items:
                logger.info("모든 아이템이 이미 처리되었습니다.")
                return {
                    "total": len(all_items),
                    "new": 0,
                    "processed": len(all_items) - len(new_items)
                }
            
            # 새로운 아이템들을 벡터 DB에 추가
            logger.info(f"{len(new_items)}개의 새로운 아이템을 처리합니다...")
            added_count = self.vector_store.add_items_batch(new_items)
            
            result = {
                "total": len(all_items),
                "new": len(new_items),
                "processed": added_count,
                "skipped": len(new_items) - added_count
            }
            
            logger.info(f"처리 완료: {result}")
            return result
            
        except Exception as e:
            logger.error(f"아이템 처리 중 오류 발생: {e}")
            return {"total": 0, "new": 0, "processed": 0, "error": str(e)}
    
    def process_single_item(self, content_hash: str) -> bool:
        """특정 아이템 하나만 처리"""
        try:
            all_items = self.load_rss_items()
            
            if content_hash not in all_items:
                logger.error(f"해당 content_hash를 찾을 수 없습니다: {content_hash}")
                return False
            
            item_data = all_items[content_hash]
            item_data["content_hash"] = content_hash
            
            # 이미 처리된 아이템인지 확인
            if self.vector_store.is_item_processed(content_hash):
                logger.info(f"이미 처리된 아이템입니다: {content_hash}")
                return False
            
            # 아이템 처리
            success = self.vector_store.add_item(item_data)
            
            if success:
                logger.info(f"아이템이 성공적으로 처리되었습니다: {content_hash}")
            else:
                logger.error(f"아이템 처리 실패: {content_hash}")
            
            return success
            
        except Exception as e:
            logger.error(f"단일 아이템 처리 중 오류 발생: {e}")
            return False
    
    def search_similar_content(self, query: str, limit: int = 5) -> List[Dict]:
        """쿼리와 유사한 콘텐츠 검색 (옵션 A: full_vector 기준)"""
        return self.vector_store.search_similar(query, "full_vector", limit)
    
    def search_similar_title(self, query: str, limit: int = 5) -> List[Dict]:
        """쿼리와 유사한 제목 검색 (옵션 A: full_vector 기준)"""
        return self.vector_store.search_similar(query, "full_vector", limit)
    
    def get_statistics(self) -> Dict:
        """처리 통계 정보 반환"""
        vector_stats = self.vector_store.get_stats()
        
        # JSON 파일의 전체 아이템 수 가져오기
        all_items = self.load_rss_items()
        total_in_json = len(all_items)
        
        return {
            "json_file": {
                "path": self.json_file_path,
                "total_items": total_in_json,
                "exists": os.path.exists(self.json_file_path)
            },
            "vector_store": vector_stats,
            "processing_status": {
                "items_in_json": total_in_json,
                "items_in_vector_db": vector_stats.get("total_entities", 0),
                "pending_items": max(0, total_in_json - vector_stats.get("processed_hashes", 0))
            }
        }


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RSS 아이템 임베딩 처리")
    parser.add_argument("--json-file", default="data/rss_items.json", 
                       help="RSS 아이템 JSON 파일 경로")
    parser.add_argument("--milvus-host", default="localhost", 
                       help="Milvus 서버 호스트")
    parser.add_argument("--milvus-port", default="19530", 
                       help="Milvus 서버 포트")
    parser.add_argument("--item-hash", 
                       help="처리할 특정 아이템의 content_hash")
    parser.add_argument("--search", 
                       help="유사한 콘텐츠 검색 쿼리")
    parser.add_argument("--stats", action="store_true",
                       help="통계 정보만 출력")
    
    args = parser.parse_args()
    
    # 임베딩 처리기 초기화
    processor = EmbeddingProcessor(
        json_file_path=args.json_file,
        milvus_host=args.milvus_host,
        milvus_port=args.milvus_port
    )
    
    if args.stats:
        # 통계 정보 출력
        stats = processor.get_statistics()
        print("\n=== 처리 통계 ===")
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        
    elif args.search:
        # 유사 콘텐츠 검색
        results = processor.search_similar_content(args.search)
        print(f"\n=== '{args.search}' 검색 결과 ===")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['title']}")
            print(f"   거리: {result['distance']:.4f}")
            print(f"   링크: {result['link']}")
            print()
    
    elif args.item_hash:
        # 특정 아이템 처리
        success = processor.process_single_item(args.item_hash)
        if success:
            print(f"아이템 {args.item_hash}가 성공적으로 처리되었습니다.")
        else:
            print(f"아이템 {args.item_hash} 처리에 실패했습니다.")
    
    else:
        # 모든 새로운 아이템 처리
        print("RSS 아이템 임베딩 처리를 시작합니다...")
        result = processor.process_all_items()
        
        print("\n=== 처리 결과 ===")
        print(f"전체 아이템: {result['total']}")
        print(f"새로운 아이템: {result['new']}")
        print(f"성공적으로 처리된 아이템: {result['processed']}")
        if 'skipped' in result:
            print(f"건너뛴 아이템: {result['skipped']}")
        if 'error' in result:
            print(f"오류: {result['error']}")


if __name__ == "__main__":
    main()

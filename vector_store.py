"""
벡터 스토어 관리 모듈
OpenAI 임베딩을 사용하여 RSS 아이템을 벡터 DB에 저장하고 관리합니다.
"""

import os
import re
import json
import hashlib
from typing import List, Dict, Optional, Set
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from openai import OpenAI
from datetime import datetime
import logging
from bs4 import BeautifulSoup

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, 
                 collection_name: str = "rss_items",
                 milvus_host: str = "localhost",
                 milvus_port: str = "19530",
                 openai_api_key: str = None):
        """
        벡터 스토어 초기화
        
        Args:
            collection_name: Milvus 컬렉션 이름
            milvus_host: Milvus 서버 호스트
            milvus_port: Milvus 서버 포트
            openai_api_key: OpenAI API 키
        """
        self.collection_name = collection_name
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.embedding_dim = 1536  # OpenAI text-embedding-3-small 차원
        self.metric_type = "COSINE"  # 유사도 계산 방식: COSINE
        
        # OpenAI 클라이언트 초기화
        self.openai_client = OpenAI(
            api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
        )
        
        # Milvus 연결 및 컬렉션 초기화
        self._connect_milvus()
        self._setup_collection()
        
        # 이미 처리된 아이템들의 해시 캐시
        self._processed_hashes: Set[str] = set()
        self._load_processed_hashes()
    
    def _connect_milvus(self):
        """Milvus 데이터베이스에 연결"""
        try:
            connections.connect(
                alias="default",
                host=self.milvus_host,
                port=self.milvus_port
            )
            logger.info(f"Milvus에 연결되었습니다: {self.milvus_host}:{self.milvus_port}")
        except Exception as e:
            logger.error(f"Milvus 연결 실패: {e}")
            raise
    
    def _setup_collection(self):
        """컬렉션 스키마 생성 및 초기화"""
        # 컬렉션이 이미 존재하는지 확인
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            logger.info(f"기존 컬렉션을 사용합니다: {self.collection_name}")
            return
        
        # 컬렉션 스키마 정의
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="content_hash", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=4000),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=10000),
            FieldSchema(name="author", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="published", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="link", dtype=DataType.VARCHAR, max_length=1000),
            FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="raw_json", dtype=DataType.VARCHAR, max_length=60000),
            FieldSchema(name="full_vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        ]
        
        schema = CollectionSchema(fields, "RSS 아이템 임베딩 컬렉션")
        
        # 컬렉션 생성
        self.collection = Collection(self.collection_name, schema)
        
        # 인덱스 생성
        self._create_indexes()
        
        logger.info(f"새 컬렉션이 생성되었습니다: {self.collection_name}")
    
    def _create_indexes(self):
        """벡터 필드에 인덱스 생성"""
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": self.metric_type,
            "params": {"nlist": 100}
        }

        # full_vector 인덱스 생성
        self.collection.create_index("full_vector", index_params)
        logger.info("full_vector 인덱스가 생성되었습니다.")

        # 컬렉션을 메모리에 로드
        self.collection.load()
        logger.info("컬렉션이 메모리에 로드되었습니다.")
    
    def _load_processed_hashes(self):
        """이미 처리된 아이템들의 해시를 로드"""
        try:
            # Milvus에서 모든 content_hash 가져오기
            results = self.collection.query(
                expr="content_hash != ''",
                output_fields=["content_hash"]
            )
            self._processed_hashes = {result["content_hash"] for result in results}
            logger.info(f"이미 처리된 아이템 {len(self._processed_hashes)}개를 로드했습니다.")
        except Exception as e:
            logger.warning(f"처리된 해시 로드 실패: {e}")
            self._processed_hashes = set()
    
    def _clean_text(self, text: str) -> str:
        """HTML 태그 및 특수 문자 제거"""
        if not text:
            return ""
        
        # BeautifulSoup으로 HTML 태그 제거
        soup = BeautifulSoup(text, 'html.parser')
        cleaned = soup.get_text()
        
        # 특수 문자 및 이스케이프 문자 제거
        cleaned = re.sub(r'&[a-zA-Z0-9#]+;', ' ', cleaned)  # HTML 엔티티
        cleaned = re.sub(r'\s+', ' ', cleaned)  # 연속된 공백을 하나로
        cleaned = cleaned.strip()
        
        return cleaned
    
    def _generate_embedding(self, text: str) -> List[float]:
        """OpenAI API를 사용하여 텍스트 임베딩 생성"""
        try:
            # 텍스트 정리
            clean_text = self._clean_text(text)
            
            if not clean_text:
                # 빈 텍스트의 경우 제로 벡터 반환
                return [0.0] * self.embedding_dim
            
            # OpenAI 임베딩 생성
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=clean_text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return [0.0] * self.embedding_dim
    
    def is_item_processed(self, content_hash: str) -> bool:
        """아이템이 이미 처리되었는지 확인"""
        return content_hash in self._processed_hashes
    
    def add_item(self, item_data: Dict) -> bool:
        """새로운 RSS 아이템을 벡터 DB에 추가"""
        try:
            content_hash = item_data.get("content_hash", "")
            
            # 이미 처리된 아이템인지 확인
            if self.is_item_processed(content_hash):
                logger.info(f"이미 처리된 아이템입니다: {content_hash}")
                return False
            
            # 텍스트 임베딩 생성 (옵션 A: 주요 필드를 라벨링하여 단일 문서 임베딩)
            title = item_data.get("title", "")
            description = item_data.get("description", "")
            content = item_data.get("content", "")
            author = item_data.get("author", "")
            category = item_data.get("category", "")
            published = item_data.get("published", "")

            parts: List[str] = []
            if title:
                parts.append(f"Title: {self._clean_text(title)}")
            if description:
                parts.append(f"Description: {self._clean_text(description)}")
            if content:
                parts.append(f"Content: {self._clean_text(content)}")
            if author:
                parts.append(f"Author: {self._clean_text(author)}")
            if category:
                parts.append(f"Category: {self._clean_text(category)}")
            if published:
                parts.append(f"Published: {self._clean_text(published)}")

            combined_text = "\n".join(parts)

            logger.info(f"임베딩 생성 중: {title[:50]}...")

            full_vector = self._generate_embedding(combined_text)
            
            # 데이터 준비
            entity = {
                "id": content_hash,
                "content_hash": content_hash,
                "title": self._clean_text(title)[:1000],  # 길이 제한
                "description": self._clean_text(description)[:4000],
                "content": self._clean_text(content)[:10000],  # 길이 제한
                "author": self._clean_text(author)[:200],
                "category": self._clean_text(category)[:200],
                "published": self._clean_text(published)[:100],
                "link": item_data.get("link", "")[:1000],
                "created_at": datetime.now().isoformat(),
                "raw_json": json.dumps(item_data, ensure_ascii=False)[:60000],
                "full_vector": full_vector
            }
            
            # Milvus에 삽입
            self.collection.insert([entity])
            self.collection.flush()
            
            # 캐시에 추가
            self._processed_hashes.add(content_hash)
            
            logger.info(f"아이템이 성공적으로 추가되었습니다: {title[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"아이템 추가 실패: {e}")
            return False
    
    def add_items_batch(self, items_data: List[Dict]) -> int:
        """여러 RSS 아이템을 배치로 추가"""
        added_count = 0
        
        for item_data in items_data:
            if self.add_item(item_data):
                added_count += 1
        
        logger.info(f"총 {added_count}개의 새로운 아이템이 추가되었습니다.")
        return added_count
    
    def search_similar(self, 
                       query_text: str, 
                       search_field: str = "full_vector",
                       limit: int = 5) -> List[Dict]:
        """유사한 아이템 검색"""
        try:
            # 쿼리 텍스트 임베딩 생성
            query_vector = self._generate_embedding(query_text)
            
            # 검색 파라미터
            search_params = {
                "metric_type": self.metric_type,
                "params": {"nprobe": 10}
            }
            
            # 검색 실행
            # 필드 존재 여부에 따라 안전하게 검색 필드 결정 (구 스키마 호환)
            try:
                field_names = {f.name for f in self.collection.schema.fields}
            except Exception:
                field_names = set()

            effective_field = search_field
            if effective_field not in field_names:
                if "full_vector" in field_names:
                    effective_field = "full_vector"
                elif "content_vector" in field_names:
                    effective_field = "content_vector"
                elif "title_vector" in field_names:
                    effective_field = "title_vector"

            results = self.collection.search(
                data=[query_vector],
                anns_field=effective_field,
                param=search_params,
                limit=limit,
                output_fields=["title", "description", "content", "author", "category", "published", "link", "raw_json"]
            )
            
            # 결과 변환
            similar_items = []
            for hit in results[0]:
                similar_items.append({
                    "id": hit.id,
                    "distance": hit.distance,
                    "title": hit.entity.get("title"),
                    "content": hit.entity.get("content"),
                    "author": hit.entity.get("author"),
                    "category": hit.entity.get("category"),
                    "published": hit.entity.get("published"),
                    "link": hit.entity.get("link")
                })
            
            return similar_items
            
        except Exception as e:
            logger.error(f"유사 검색 실패: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """벡터 스토어 통계 정보"""
        try:
            # PyMilvus 2.6+에서는 get_stats()가 없을 수 있으므로 num_entities 기반으로 집계
            try:
                total_entities = int(getattr(self.collection, "num_entities", 0))
            except Exception:
                total_entities = 0

            return {
                "collection_name": self.collection_name,
                "total_entities": total_entities,
                "processed_hashes": len(self._processed_hashes),
                "index_status": "loaded" if self.collection.has_index() else "not_loaded"
            }
        except Exception as e:
            logger.error(f"통계 정보 조회 실패: {e}")
            return {}

# RSS 데이터 벡터 임베딩 시스템

이 시스템은 RSS 데이터를 OpenAI 임베딩을 사용하여 벡터화하고, Milvus 벡터 데이터베이스에 저장하여 유사도 검색을 가능하게 합니다.

## 🚀 주요 기능

- **자동 중복 체크**: 이미 임베딩된 아이템은 건너뛰고 새로운 아이템만 처리
- **HTML 태그 제거**: RSS 데이터에서 HTML 태그와 특수문자를 제거하여 순수한 텍스트만 저장
- **배치 처리**: 여러 아이템을 효율적으로 일괄 처리
- **유사도 검색**: 제목이나 내용을 기반으로 유사한 아이템 검색
- **RESTful API**: FastAPI를 통한 웹 인터페이스 제공

## 📁 파일 구조

```
├── vector_store.py          # 벡터 스토어 관리 (Milvus 연결, 임베딩 생성)
├── embedding_processor.py   # 임베딩 처리 메인 로직
├── main.py                 # FastAPI 서버 (벡터 API 엔드포인트 추가)
├── docker-compose.yml      # Milvus 포함한 Docker 환경
└── data/rss_items.json     # RSS 데이터 소스
```

## 🔧 설치 및 설정

### 1. 의존성 설치

```bash
# uv 환경에서 설치
uv sync
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 OpenAI API 키를 설정:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Milvus 시작 (Docker)

```bash
# Milvus 벡터 데이터베이스 시작
docker-compose up -d milvus etcd minio
```

## 🏃‍♂️ 사용법

### 방법 1: FastAPI 서버를 통한 사용 (권장)

```bash
# 서버 시작
uv run main.py
```

서버가 시작되면 브라우저에서 `http://localhost:8888`에 접속하여 API 문서를 확인할 수 있습니다.

#### API 엔드포인트

1. **모든 새로운 아이템 처리**
   ```bash
   curl -X POST http://localhost:8888/vector/process
   ```

2. **통계 정보 조회**
   ```bash
   curl http://localhost:8888/vector/stats
   ```

3. **유사 콘텐츠 검색**
   ```bash
   # 내용 기반 검색
   curl "http://localhost:8888/vector/search?query=장학금&limit=5&search_type=content"
   
   # 제목 기반 검색
   curl "http://localhost:8888/vector/search?query=수강신청&limit=3&search_type=title"
   ```

### 방법 2: 명령줄 직접 실행

```bash
# 모든 새로운 아이템 처리
uv run embedding_processor.py

# 통계 정보 확인
uv run embedding_processor.py --stats

# 특정 아이템만 처리
uv run embedding_processor.py --item-hash "471ddab30b939f52d51a4b4b91981d34"

# 유사 콘텐츠 검색
uv run embedding_processor.py --search "장학금 신청"
```

## 📊 데이터 흐름

1. **RSS 데이터 로드**: `data/rss_items.json`에서 RSS 아이템들을 읽기
2. **중복 체크**: Milvus DB에서 이미 처리된 아이템의 해시값 확인
3. **텍스트 정리**: HTML 태그 및 특수문자 제거
4. **임베딩 생성**: OpenAI `text-embedding-ada-002` 모델 사용
5. **벡터 저장**: Milvus에 메타데이터와 함께 벡터 저장
6. **인덱싱**: IVF_FLAT 인덱스로 빠른 검색 지원

## 🔍 검색 기능

### 내용 기반 검색
RSS 아이템의 본문 내용을 기반으로 유사한 아이템을 찾습니다.

### 제목 기반 검색  
RSS 아이템의 제목을 기반으로 유사한 제목을 가진 아이템을 찾습니다.

### 검색 결과
각 검색 결과는 다음 정보를 포함합니다:
- 유사도 거리 (낮을수록 더 유사)
- 제목, 내용, 작성자, 카테고리
- 발행일, 링크

## 🐳 Docker 환경에서 실행

```bash
# 전체 시스템 시작 (RSS 서버 + Milvus)
docker-compose up -d

# 로그 확인
docker-compose logs -f ssu-rag

# 벡터 처리 (컨테이너 내부에서)
docker-compose exec ssu-rag python embedding_processor.py
```

## 📈 모니터링

### 통계 정보 확인
```bash
curl http://localhost:8888/vector/stats
```

응답 예시:
```json
{
  "json_file": {
    "path": "data/rss_items.json", 
    "total_items": 1400,
    "exists": true
  },
  "vector_store": {
    "collection_name": "rss_items",
    "total_entities": 850,
    "processed_hashes": 850,
    "index_status": "loaded"
  },
  "processing_status": {
    "items_in_json": 1400,
    "items_in_vector_db": 850, 
    "pending_items": 550
  }
}
```

## ⚠️ 주의사항

1. **OpenAI API 비용**: 임베딩 생성 시 OpenAI API 호출 비용이 발생합니다.
2. **Milvus 메모리**: 벡터 데이터는 상당한 메모리를 사용할 수 있습니다.
3. **처리 시간**: 대량의 데이터 처리 시 시간이 오래 걸릴 수 있습니다.
4. **HTML 정리**: RSS 데이터의 HTML 태그가 자동으로 제거됩니다.

## 🔧 설정 조정

### Milvus 연결 설정
```python
# embedding_processor.py에서 설정 변경 가능
processor = EmbeddingProcessor(
    json_file_path="data/rss_items.json",
    milvus_host="localhost",  # Milvus 호스트
    milvus_port="19530"       # Milvus 포트
)
```

### 임베딩 모델 변경
`vector_store.py`에서 OpenAI 임베딩 모델을 변경할 수 있습니다:
```python
response = self.openai_client.embeddings.create(
    model="text-embedding-ada-002",  # 다른 모델로 변경 가능
    input=clean_text
)
```

## 🎯 활용 사례

1. **개인화된 콘텐츠 추천**: 사용자의 관심사와 유사한 RSS 아이템 추천
2. **중복 콘텐츠 감지**: 유사한 내용의 RSS 아이템 식별
3. **콘텐츠 분류**: 벡터 유사도를 기반으로 한 자동 카테고리 분류
4. **검색 개선**: 키워드 기반이 아닌 의미 기반 검색

## 🆘 문제 해결

### Milvus 연결 오류
```bash
# Milvus 서비스 상태 확인
docker-compose ps milvus

# Milvus 재시작
docker-compose restart milvus
```

### OpenAI API 오류
- API 키가 올바르게 설정되었는지 확인
- API 사용량 한도를 확인

### 메모리 부족
- Docker에 할당된 메모리 증가
- 배치 크기 줄이기 (한 번에 처리하는 아이템 수 감소)

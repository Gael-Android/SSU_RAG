# RSS 리더 시스템

숭실대학교 공지사항 RSS 피드를 자동으로 수집하고 관리하는 시스템입니다.

## 주요 기능

### 🔄 자동 RSS 수집
- **URL**: `https://ssufid.yourssu.com/scatch.ssu.ac.kr/rss.xml`
- **수집 간격**: 1시간마다 자동 실행
- **중복 방지**: 콘텐츠 해시 기반으로 중복 아이템 자동 필터링
- **데이터 저장**: `data/rss_items.json` 파일에 영구 저장
- **HTML 정리**: 모든 HTML 태그와 특수문자 제거하여 벡터DB 최적화

### 📊 REST API 엔드포인트

#### 1. 스케줄러 상태 확인
```bash
GET /rss/status
```
- 스케줄러 실행 상태
- 마지막 수집 시간
- 총 수집 횟수

#### 2. 모든 RSS 아이템 조회
```bash
GET /rss/items
```
- 수집된 모든 아이템 반환

#### 3. 최근 RSS 아이템 조회
```bash
GET /rss/recent?count=10
```
- 최근 아이템을 지정된 개수만큼 반환
- 기본값: 10개

#### 4. 수동 RSS 수집
```bash
POST /rss/fetch
```
- 즉시 RSS 피드를 수집
- 중복 아이템은 자동으로 필터링

## 시스템 구조

### 핵심 컴포넌트

1. **RSSReader** (`rss/reader.py`)
   - RSS 피드 파싱
   - 콘텐츠 해시 기반 중복 검사
   - JSON 형태로 데이터 저장

2. **RSSScheduler** (`scheduler.py`)
   - 백그라운드에서 1시간마다 실행
   - 멀티스레딩으로 안전한 스케줄링
   - 서버 시작/종료시 자동 관리

3. **FastAPI 통합** (`main.py`)
   - REST API 엔드포인트 제공
   - 서버 라이프사이클과 연동
   - 기존 RAG 시스템과 통합

### 데이터 모델

각 RSS 아이템은 다음 정보를 포함합니다:
- `title`: 제목
- `link`: 원본 링크
- `description`: HTML 태그가 제거된 깔끔한 설명
- `content`: HTML 태그가 제거된 깔끔한 전체 내용
- `published`: 발행일
- `guid`: 고유 식별자
- `content_hash`: 중복 검사용 해시값 (title + link + description 기반)
- `fetched_at`: 수집 시간
- `author`: 작성자 (예: "장학팀", "학사팀")
- `category`: 카테고리 (예: "장학", "학사", "국제교류")
- `enclosure_url`: 첨부파일 URL (이미지, PDF 등)
- `enclosure_type`: 첨부파일 타입 (image/jpeg, application/pdf 등)

## 사용 예시

### 서버 시작
```bash
uv run python main.py
```

### API 호출 예시
```bash
# 스케줄러 상태 확인
curl http://localhost:8888/rss/status

# 최근 5개 아이템 조회
curl "http://localhost:8888/rss/recent?count=5"

# 수동으로 RSS 수집
curl -X POST http://localhost:8888/rss/fetch
```

## 특징

✅ **중복 방지**: 콘텐츠 해시를 이용한 정확한 중복 검사  
✅ **자동 실행**: 1시간마다 자동으로 새 공지사항 수집  
✅ **영구 저장**: JSON 파일로 데이터 영구 보관  
✅ **REST API**: 다양한 방식으로 데이터 접근 가능  
✅ **에러 처리**: 네트워크 오류나 파싱 오류에 대한 견고한 처리  
✅ **기존 시스템 통합**: RAG 챗봇 시스템과 완전 통합  
✅ **HTML 정리**: BeautifulSoup을 사용한 완전한 HTML 태그 제거  
✅ **벡터DB 최적화**: 깔끔한 텍스트만 저장하여 검색 품질 향상  
✅ **메타데이터 완전 수집**: 작성자, 카테고리, 첨부파일 정보 포함

## 중복 처리 로직

### 해시 생성 기준
```python
content_hash = md5(title + link + description)
```

### 동작 방식
- **완전히 동일한 글**: 해시 동일 → 저장하지 않음
- **제목/내용/링크 중 하나라도 변경**: 해시 다름 → 새 글로 저장
- **기존 글이 RSS에서 삭제**: 기존 저장된 데이터는 유지됨

## 개발 과정

### 1단계: 기본 RSS 리더 구현
- `feedparser`를 사용한 RSS 피드 파싱
- 기본 필드 수집 (title, link, description, published, guid)
- JSON 파일 기반 저장소

### 2단계: 스케줄러 추가
- 백그라운드 스레드를 사용한 1시간 주기 실행
- FastAPI 서버 라이프사이클과 연동
- 안전한 시작/종료 처리

### 3단계: 메타데이터 확장
- author, category, enclosure 정보 추가 수집
- RSS 아이템의 모든 정보 완전 수집

### 4단계: HTML 정리 기능
- BeautifulSoup을 사용한 HTML 태그 완전 제거
- HTML 엔티티 디코딩 (&amp; → &)
- 공백 정규화 및 특수문자 정리
- 벡터DB 저장에 최적화된 깔끔한 텍스트 생성

### 5단계: 데이터 구조 최적화
- HTML 원본 필드 제거 (description, content_encoded)
- 클린한 텍스트만 저장 (description, content)
- 저장 공간 효율성 및 검색 품질 향상

## 로그 확인

시스템 실행 중 다음과 같은 로그를 통해 동작 상태를 확인할 수 있습니다:

```
INFO:rss_reader:RSS 피드를 가져오는 중: https://ssufid.yourssu.com/scatch.ssu.ac.kr/rss.xml
INFO:rss_reader:새 아이템 추가: 2025학년도 2학기 한국장학재단 주거안정장학금 2차 신청 안내
INFO:rss_reader:RSS 피드 처리 완료: 새 아이템 5개, 기존 아이템 95개
INFO:scheduler:RSS 스케줄러가 시작되었습니다. (간격: 1시간)
```

이제 숭실대학교 공지사항을 놓치지 않고 자동으로 수집할 수 있습니다! 🎉

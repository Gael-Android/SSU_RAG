from fastapi import FastAPI
from langserve import add_routes
from typing import Dict
from contextlib import asynccontextmanager

# RSS 리더 관련 임포트
from rss import get_rss_reader
from scheduler import get_scheduler, start_scheduler, stop_scheduler

# 임베딩 처리 관련 임포트
from embedding_processor import EmbeddingProcessor
from chains import chat_chain, rag_chain_server, run_rag_qa

# 환경 변수 로드는 chains.py에서 처리

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시
    start_scheduler()
    yield
    # 종료 시
    stop_scheduler()

app = FastAPI(title="SSU RAG Chatbot", version="1.0.0", lifespan=lifespan)

# 임베딩 처리기 초기화 (전역 변수)
embedding_processor = None

def get_embedding_processor():
    """임베딩 처리기 싱글톤 인스턴스 반환"""
    global embedding_processor
    if embedding_processor is None:
        try:
            embedding_processor = EmbeddingProcessor()
        except Exception as e:
            print(f"임베딩 처리기 초기화 실패: {e}")
            embedding_processor = None
    return embedding_processor

# 체인 구성 (분리된 chains.py 사용)
chain = chat_chain

# LangServe로 채팅 엔드포인트 추가
add_routes(
    app,
    chain,
    path="/chat"
)

@app.get("/")
async def root():
    return {
        "message": "SSU RAG Chatbot API", 
        "status": "running",
        "playground": "http://localhost:8888/chat/playground",
        "docs": "http://localhost:8888/docs",
        "rss_endpoints": {
            "status": "http://localhost:8888/rss/status",
            "items": "http://localhost:8888/rss/items",
            "recent": "http://localhost:8888/rss/recent",
            "fetch": "http://localhost:8888/rss/fetch"
        },
        "vector_endpoints": {
            "process": "http://localhost:8888/vector/process",
            "stats": "http://localhost:8888/vector/stats",
            "search": "http://localhost:8888/vector/search"
        }
    }

# RSS 관련 엔드포인트들
@app.get("/rss/status")
async def get_rss_status():
    """RSS 스케줄러 상태 확인"""
    scheduler = get_scheduler()
    return scheduler.get_status()

@app.get("/rss/items")
async def get_all_rss_items():
    """모든 RSS 아이템 가져오기"""
    reader = get_rss_reader()
    items = reader.get_all_items()
    return {
        "total_items": len(items),
        "items": items
    }

@app.get("/rss/recent")
async def get_recent_rss_items(count: int = 10):
    """최근 RSS 아이템 가져오기"""
    reader = get_rss_reader()
    items = reader.get_recent_items(count)
    return {
        "requested_count": count,
        "returned_count": len(items),
        "items": items
    }

@app.post("/rss/fetch")
async def fetch_rss_now():
    """즉시 RSS 피드 가져오기"""
    scheduler = get_scheduler()
    result = scheduler.fetch_now()
    return result

# 벡터 임베딩 관련 엔드포인트들
@app.post("/vector/process")
async def process_embeddings():
    """RSS 아이템들을 임베딩하여 벡터 DB에 저장"""
    processor = get_embedding_processor()
    if not processor:
        return {"error": "임베딩 처리기를 초기화할 수 없습니다. Milvus 서버와 OpenAI API 키를 확인해주세요."}
    
    try:
        result = processor.process_all_items()
        return {
            "message": "임베딩 처리 완료",
            "result": result
        }
    except Exception as e:
        return {"error": f"임베딩 처리 중 오류: {str(e)}"}

@app.get("/vector/stats")
async def get_vector_stats():
    """벡터 DB 통계 정보"""
    processor = get_embedding_processor()
    if not processor:
        return {"error": "임베딩 처리기를 초기화할 수 없습니다."}
    
    try:
        stats = processor.get_statistics()
        return stats
    except Exception as e:
        return {"error": f"통계 조회 중 오류: {str(e)}"}

@app.get("/vector/search")
async def search_similar(query: str, limit: int = 5, search_type: str = "content"):
    """유사한 콘텐츠 검색"""
    processor = get_embedding_processor()
    if not processor:
        return {"error": "임베딩 처리기를 초기화할 수 없습니다."}
    
    try:
        if search_type == "title":
            results = processor.search_similar_title(query, limit)
        else:
            results = processor.search_similar_content(query, limit)
        
        return {
            "query": query,
            "search_type": search_type,
            "limit": limit,
            "results": results
        }
    except Exception as e:
        return {"error": f"검색 중 오류: {str(e)}"}


# (단일화) GET /qa 제거 → POST /qa 만 유지


# ===== RAG QA REST 엔드포인트 (POST: 한글 안전) =====
@app.post("/qa")
async def rag_qa_post(payload: Dict) -> Dict:
    """POST 바디로 질의를 받아 처리 (한글/인코딩 안전)"""
    query = (payload or {}).get("query", "")
    limit = int((payload or {}).get("limit", 5))
    return run_rag_qa(query=query, limit=limit)


add_routes(
    app,
    rag_chain_server,
    path="/rag",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
    

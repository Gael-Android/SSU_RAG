from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langserve import add_routes
from typing import List, Dict
from langchain_core.runnables import RunnableLambda
from typing import List, Dict
import os
from dotenv import load_dotenv
import atexit
from contextlib import asynccontextmanager

# RSS 리더 관련 임포트
from rss import get_rss_reader
from scheduler import get_scheduler, start_scheduler, stop_scheduler

# 임베딩 처리 관련 임포트
from embedding_processor import EmbeddingProcessor

# 환경 변수 로드
load_dotenv()

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

# 간단한 채팅 체인 생성
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 도움이 되는 AI 어시스턴트입니다. 한국어로 친근하게 대답해주세요."),
    ("human", "{input}")
])

# 체인 구성
chain = prompt | llm | StrOutputParser()

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


# ===== RAG 공통 유틸 =====
def _build_context(items: List[Dict]) -> str:
    lines: List[str] = []
    for i, item in enumerate(items, 1):
        title = item.get("title") or ""
        description = item.get("description") or ""
        content = item.get("content") or ""
        author = item.get("author") or ""
        category = item.get("category") or ""
        published = item.get("published") or ""
        link = item.get("link") or ""
        snippet = (description or content)[:500]
        lines.append(
            f"[{i}] Title: {title}\nAuthor: {author} | Category: {category} | Published: {published}\nSnippet: {snippet}\nLink: {link}"
        )
    return "\n\n".join(lines)


# ===== RAG QA REST 엔드포인트 (POST: 한글 안전) =====
@app.post("/qa")
async def rag_qa_post(payload: Dict) -> Dict:
    """POST 바디로 질의를 받아 처리 (한글/인코딩 안전)"""
    query = (payload or {}).get("query", "")
    limit = int((payload or {}).get("limit", 5))
    # 상위 컨텍스트 빌드 후 동일 로직 재사용
    processor = get_embedding_processor()
    if not processor:
        return {"error": "임베딩 처리기를 초기화할 수 없습니다."}
    results: List[Dict] = processor.search_similar_content(query, limit)
    context_text = _build_context(results)
    rag_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "너는 제공된 문맥(Context)만을 근거로 한국어로 간결하고 정확하게 답변한다. 모르면 모른다고 말한다. 필요하면 출처 링크도 함께 제시한다.",
        ),
        ("human", "질문: {question}\n\nContext:\n{context}"),
    ])
    rag_chain = rag_prompt | llm | StrOutputParser()
    answer = rag_chain.invoke({"question": query, "context": context_text})
    sources = [
        {
            "title": r.get("title"),
            "link": r.get("link"),
            "published": r.get("published"),
            "author": r.get("author"),
            "category": r.get("category"),
            "distance": r.get("distance"),
        }
        for r in results
    ]
    return {"query": query, "answer": answer, "sources": sources}


# ===== LangServe용 RAG 체인 노출 (/rag) =====
def _rag_items(query: str, limit: int = 5) -> Dict:
    processor = get_embedding_processor()
    results: List[Dict] = processor.search_similar_content(query, limit)
    return {"question": query, "items": results, "context": _build_context(results)}


_rag_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "너는 제공된 문맥(Context)만을 근거로 한국어로 간결하고 정확하게 답변한다. 모르면 모른다고 말한다. 필요하면 출처 링크도 함께 제시한다.",
    ),
    ("human", "질문: {question}\n\nContext:\n{context}"),
])

_rag_answer_chain = _rag_prompt | llm | StrOutputParser()

rag_chain_server = (
    RunnableLambda(lambda q: _rag_items(q))
)

add_routes(
    app,
    rag_chain_server,
    path="/rag",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
    

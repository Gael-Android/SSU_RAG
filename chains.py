import os
from typing import List, Dict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

from embedding_processor import EmbeddingProcessor


# 환경 변수 로드
load_dotenv()


# ===== 공용 LLM =====
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)


# ===== Chat 체인 (일반 대화) =====
_chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "당신은 도움이 되는 AI 어시스턴트입니다. 한국어로 친근하게 대답해주세요."),
    ("human", "{input}"),
])

chat_chain = _chat_prompt | llm | StrOutputParser()


# ===== 벡터 검색 유틸 =====
_processor: EmbeddingProcessor | None = None


def get_processor() -> EmbeddingProcessor:
    global _processor
    if _processor is None:
        _processor = EmbeddingProcessor()
    return _processor


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


# ===== RAG 답변 체인 =====
_rag_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "너는 제공된 문맥(Context)만을 근거로 한국어로 간결하고 정확하게 답변한다. 모르면 모른다고 말한다. 필요하면 출처 링크도 함께 제시한다.",
    ),
    ("human", "질문: {question}\n\nContext:\n{context}"),
])

_rag_answer_chain = _rag_prompt | llm | StrOutputParser()


def run_rag_qa(query: str, limit: int = 5) -> Dict:
    """질의를 받아 상위 문맥 검색 후 답변 및 출처를 반환"""
    processor = get_processor()
    results: List[Dict] = processor.search_similar_content(query, limit)
    context_text = _build_context(results)
    answer = _rag_answer_chain.invoke({"question": query, "context": context_text})
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


# ===== LangServe용 RAG 체인 (/rag) =====
def _rag_items(query: str, limit: int = 5) -> Dict:
    processor = get_processor()
    results: List[Dict] = processor.search_similar_content(query, limit)
    return {"question": query, "items": results, "context": _build_context(results)}


rag_chain_server = RunnableLambda(lambda q: _rag_items(q))



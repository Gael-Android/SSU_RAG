import os
from typing import List, Dict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from embedding_processor import EmbeddingProcessor


# 환경 변수 로드
load_dotenv()


# ===== 공용 LLM =====
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.7,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
)




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
        "너는 제공된 문맥(Context)만을 근거로 한국어로 간결하고 정확하게 답변한다. 모르면 모른다고 말한다. 반드시 본문 내에 문맥 항목의 대괄호 번호([1], [2], ...)로 근거를 표시하라. 본문에는 링크를 넣지 말고, 링크 목록은 시스템이 답변 마지막에 '참고 문서' 섹션으로 자동 첨부한다.",
    ),
    ("human", "질문: {question}\n\nContext:\n{context}"),
])

_rag_answer_chain = _rag_prompt | llm | StrOutputParser()


# ===== 통합된 RAG 체인 =====
def unified_rag_chain(query: str, limit: int = 5) -> Dict:
    """질의를 받아 답변, 상세 검색 결과, 출처를 모두 반환하는 통합 함수"""
    processor = get_processor()
    results: List[Dict] = processor.search_similar_content(query, limit)
    context_text = _build_context(results)
    
    # AI 답변 생성
    answer = _rag_answer_chain.invoke({"question": query, "context": context_text})
    
    # 출처 정보 구성
    sources = []
    sources_lines: List[str] = []
    for idx, r in enumerate(results, 1):
        title = r.get("title")
        link = r.get("link")
        sources.append(
            {
                "index": idx,
                "title": title,
                "link": link,
                "published": r.get("published"),
                "author": r.get("author"),
                "category": r.get("category"),
                "distance": r.get("distance"),
            }
        )
        sources_lines.append(f"[{idx}] {title} - {link}")

    # # 답변 본문 끝에 참고 문서 섹션 자동 첨부
    # answer_with_sources = answer.strip()
    # if sources_lines:
    #     answer_with_sources += "\n\n참고 문서:\n" + "\n".join(sources_lines)

    # 통합된 결과 반환 (기존 run_rag_qa + _rag_items 정보 모두 포함)
    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "context": context_text,
        "items": results,
        "sources_text": "\n".join(sources_lines),
    }

# 기존 함수들과의 호환성을 위한 별칭
run_rag_qa = unified_rag_chain

# LangServe 관련 스키마/래퍼 제거



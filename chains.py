import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from embedding_processor import EmbeddingProcessor

load_dotenv()

# ===== 설정 =====
LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, api_key=os.getenv("OPENAI_API_KEY"))

# ===== 프롬프트 =====
RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "너는 문맥과 대화 이력을 근거로 한국어로 답변한다. 문맥 내용은 [1], [2] 번호로 인용하라. 모르면 모른다고 말한다."),
    MessagesPlaceholder("history"),
    ("human", "질문: {question}\n\nContext:\n{context}"),
])

CONDENSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "이전 대화를 참고해 최신 질문을 독립적인 한국어 질문으로 재작성한다."),
    ("human", "대화 이력:\n{history}\n\n최신 질문: {question}\n\n재작성:"),
])

# ===== 유틸리티 =====
def build_context(items: List[Dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        snippet = (item.get("description") or item.get("content") or "")[:300]
        link = item.get("link", "")
        lines.append(f"[{i}] {title}\n{snippet}\n{link}")
    return "\n\n".join(lines)

def make_sources(items: List[Dict]) -> List[Dict]:
    return [{
        "index": i,
        "title": item.get("title"),
        "link": item.get("link"),
        "author": item.get("author"),
        "distance": item.get("distance"),
    } for i, item in enumerate(items, 1)]

def history_to_text(messages) -> str:
    lines = []
    for m in messages:
        role = "Human" if m.__class__.__name__ == "HumanMessage" else "AI"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)

# ===== 서비스 =====
class RagService:
    def __init__(self):
        self.processor = EmbeddingProcessor()
        self.histories: Dict[str, ChatMessageHistory] = {}
        self.answer_chain = RAG_PROMPT | LLM | StrOutputParser()
        self.condense_chain = CONDENSE_PROMPT | LLM | StrOutputParser()
    
    def get_history(self, session_id: str) -> ChatMessageHistory:
        if session_id not in self.histories:
            self.histories[session_id] = ChatMessageHistory()
        return self.histories[session_id]
    
    def seed_messages(self, session_id: str, messages: List[Dict]):
        if not messages:
            return
        hist = self.get_history(session_id)
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "").strip()
            if not content:
                continue
            if role == "user":
                hist.add_user_message(content)
            elif role == "assistant":
                hist.add_ai_message(content)
    
    def condense_query(self, session_id: str, query: str) -> str:
        hist = self.get_history(session_id)
        if not hist.messages:
            return query
        try:
            history_text = history_to_text(hist.messages)
            return self.condense_chain.invoke({
                "history": history_text,
                "question": query
            }).strip() or query
        except:
            return query
    
    def rag_query(self, query: str, session_id: str = None, messages: List[Dict] = None, limit: int = 5) -> Dict:
        # 1. 메시지 시드
        if session_id and messages:
            self.seed_messages(session_id, messages)
        
        # 2. 질문 재작성
        effective_query = query
        if session_id:
            effective_query = self.condense_query(session_id, query)
        
        # 3. 검색
        results = self.processor.search_similar_content(effective_query, limit)
        context = build_context(results)
        
        # 4. 답변 생성 (히스토리 포함)
        if session_id:
            chain_with_history = RunnableWithMessageHistory(
                self.answer_chain,
                self.get_history,
                input_messages_key="question",
                history_messages_key="history"
            )
            answer = chain_with_history.invoke(
                {"question": query, "context": context},
                config={"configurable": {"session_id": session_id}}
            )
            # 히스토리에 이번 턴 저장
            hist = self.get_history(session_id)
            hist.add_user_message(query)
            hist.add_ai_message(answer)
        else:
            answer = self.answer_chain.invoke({"question": query, "context": context, "history": []})
        
        return {
            "query": query,
            "rephrased_query": effective_query,
            "answer": answer,
            "sources": make_sources(results),
            "items": results,
        }

# ===== 전역 인스턴스 =====
_service = None

def get_service() -> RagService:
    global _service
    if _service is None:
        _service = RagService()
    return _service

def run_rag_qa(query: str, limit: int = 5, messages: Optional[List[Dict]] = None, session_id: Optional[str] = None) -> Dict:
    return get_service().rag_query(query, session_id, messages, limit)
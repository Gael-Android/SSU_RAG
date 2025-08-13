import os
import json
from typing import List, Dict, Optional, Iterator
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from embedding_processor import EmbeddingProcessor
from openai import OpenAI

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

    def stream_answer(self, query: str, session_id: Optional[str] = None, messages: Optional[List[Dict]] = None, limit: int = 5) -> Iterator[str]:
        # 1) 히스토리 시드
        if session_id and messages:
            self.seed_messages(session_id, messages)

        # 2) 질문 재작성은 검색에만 사용
        effective_query = query
        if session_id:
            effective_query = self.condense_query(session_id, query)

        # 3) 검색 및 컨텍스트 구성
        results = self.processor.search_similar_content(effective_query, limit)
        context = build_context(results)

        # 4) 메시지 구성 (시스템 + 대화이력 + 사용자 메시지[컨텍스트 포함])
        system_content = "너는 문맥과 대화 이력을 근거로 한국어로 답변한다. 문맥 내용은 [1], [2] 번호로 인용하라. 모르면 모른다고 말한다."
        chat_messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        hist: Optional[ChatMessageHistory] = None
        if session_id:
            hist = self.get_history(session_id)
            for m in hist.messages:
                role = "user" if m.__class__.__name__ == "HumanMessage" else "assistant"
                chat_messages.append({"role": role, "content": m.content})

        user_prompt = f"질문: {query}\n\nContext:\n{context}"
        chat_messages.append({"role": "user", "content": user_prompt})

        # 5) OpenAI 스트리밍
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=chat_messages,
            stream=True,
        )

        # 먼저 메타 정보 전송 (원하는 경우 프론트에서 선표시 가능)
        meta_payload = {
            "type": "meta",
            "rephrased_query": effective_query,
            "sources": make_sources(results),
        }
        yield f"data: {json.dumps(meta_payload, ensure_ascii=False)}\n\n"

        collected_tokens: List[str] = []
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta
                token = getattr(delta, "content", None) if hasattr(delta, "content") else delta.get("content")  # type: ignore
            except Exception:
                token = None
            if token:
                collected_tokens.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

        answer_text = ("".join(collected_tokens)).strip()

        # 히스토리에 저장
        if session_id:
            if hist is None:
                hist = self.get_history(session_id)
            hist.add_user_message(query)
            hist.add_ai_message(answer_text)

        final_payload = {
            "type": "final",
            "answer": answer_text,
            "rephrased_query": effective_query,
            "sources": make_sources(results),
            "items": results,
        }
        yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"

# ===== 전역 인스턴스 =====
_service = None

def get_service() -> RagService:
    global _service
    if _service is None:
        _service = RagService()
    return _service

def run_rag_qa(query: str, limit: int = 5, messages: Optional[List[Dict]] = None, session_id: Optional[str] = None) -> Dict:
    return get_service().rag_query(query, session_id, messages, limit)

def stream_rag_qa(query: str, limit: int = 5, messages: Optional[List[Dict]] = None, session_id: Optional[str] = None) -> Iterator[str]:
    return get_service().stream_answer(query, session_id, messages, limit)
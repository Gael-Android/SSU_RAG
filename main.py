from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langserve import add_routes
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

app = FastAPI(title="SSU RAG Chatbot", version="1.0.0")

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
        "docs": "http://localhost:8888/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)

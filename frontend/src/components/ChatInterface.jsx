import React, { useState, useRef, useEffect } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import '../styles/ChatInterface.css';

function ChatInterface() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const [sessionId, setSessionId] = useState(() => {
    const existing = localStorage.getItem('ssu_rag_session_id');
    if (existing) return existing;
    const newId = (window.crypto && window.crypto.randomUUID)
      ? window.crypto.randomUUID()
      : Math.random().toString(36).slice(2);
    localStorage.setItem('ssu_rag_session_id', newId);
    return newId;
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (text) => {
    if (!text.trim()) return;

    const userMessage = {
      id: Date.now(),
      text,
      role: 'user',
      timestamp: new Date()
    };

    const allMessages = [...messages, userMessage];
    setMessages(allMessages);
    setIsLoading(true);

    try {
      const minimalHistory = allMessages.map(m => ({ role: m.role, content: m.text }));

      // 스트리밍 초기 placeholder 메시지 추가
      const aiId = Date.now() + 1;
      setMessages(prev => [...prev, { id: aiId, text: '', role: 'assistant', sources: [], timestamp: new Date() }]);

      const res = await fetch('/api/chat_api/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: text,
          limit: 5,
          messages: minimalHistory,
          session_id: sessionId,
        }),
      });

      if (!res.body) throw new Error('스트림을 열 수 없습니다.');

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      const applyToken = (token) => {
        setMessages(prev => prev.map(m => (
          m.id === aiId ? { ...m, text: (m.text || '') + token } : m
        )));
      };

      const applyMeta = (meta) => {
        if (meta.sources) {
          setMessages(prev => prev.map(m => (
            m.id === aiId ? { ...m, sources: meta.sources } : m
          )));
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 2);
          if (!raw) continue;
          // SSE 라인 파싱: 'data: {json}' 만 처리
          if (raw.startsWith('data: ')) {
            const jsonStr = raw.slice(6);
            try {
              const evt = JSON.parse(jsonStr);
              if (evt.type === 'token' && evt.content) {
                applyToken(evt.content);
              } else if (evt.type === 'meta') {
                applyMeta(evt);
              } else if (evt.type === 'final' && evt.answer) {
                // 최종 보정 (혹시 누락된 토큰 보완)
                setMessages(prev => prev.map(m => (
                  m.id === aiId ? { ...m, text: evt.answer, sources: evt.sources || m.sources } : m
                )));
              }
            } catch (e) {
              // 무시
            }
          }
        }
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: Date.now() + 1,
        text: '오류가 발생했습니다. 다시 시도해주세요.',
        role: 'assistant',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-header">
        <h1>SSU RAG Assistant</h1>
      </div>
      <div className="chat-container">
        <MessageList messages={messages} isLoading={isLoading} />
        <div ref={messagesEndRef} />
      </div>
      <MessageInput onSendMessage={sendMessage} isLoading={isLoading} />
    </div>
  );
}

export default ChatInterface;

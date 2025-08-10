import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
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
      const response = await axios.post('/api/chat_api', {
        query: text,
        limit: 5,
        messages: minimalHistory,
        session_id: sessionId,
      });

      const aiMessage = {
        id: Date.now() + 1,
        text: response.data.message || '응답을 받을 수 없습니다.',
        role: 'assistant',
        sources: response.data.sources || [],
        timestamp: new Date()
      };

      setMessages(prev => [...prev, aiMessage]);
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

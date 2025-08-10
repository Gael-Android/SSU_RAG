import React, { useState } from 'react';
import ChatInterface from './components/ChatInterface';
import './styles/App.css';

function App() {
  return (
    <div className="app">
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>SSU RAG</h2>
          <button className="new-chat-btn">+ 새 대화</button>
        </div>
        <div className="sidebar-content">
          <p>환영합니다! SSU RAG 챗봇입니다.</p>
        </div>
      </div>
      <div className="main-content">
        <ChatInterface />
      </div>
    </div>
  );
}

export default App;

import React, { useState } from 'react';
import ChatInterface from './components/ChatInterface';
import Recommend from './components/Recommend';
import './styles/App.css';

function App() {
  const [activeTab, setActiveTab] = useState('chat');
  return (
    <div className="app">
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>SSU RAG</h2>
          <button className="new-chat-btn">+ 새 대화</button>
        </div>
        <div className="sidebar-content">
          <div className="tab-list">
            <button
              className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              검색/챗봇
            </button>
            <button
              className={`tab-btn ${activeTab === 'recommend' ? 'active' : ''}`}
              onClick={() => setActiveTab('recommend')}
            >
              추천
            </button>
          </div>
        </div>
      </div>
      <div className="main-content">
        {activeTab === 'chat' ? <ChatInterface /> : <Recommend />}
      </div>
    </div>
  );
}

export default App;

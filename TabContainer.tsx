// ekho-frontend/src/components/TabContainer.tsx

import React, { useState } from 'react';
import HealthCheck from './HealthCheck';
import AvatarCreator from './AvatarCreator';
import ChatInterface from './ChatInterface';
import VoiceCloner from './VoiceCloner';

type Tab = 'chat' | 'avatar' | 'health' | 'voicecloner';

const TabContainer: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('chat');

  const renderContent = () => {
    switch (activeTab) {
      case 'chat':
        return <ChatInterface />;
      case 'avatar':
        return <AvatarCreator />;
      case 'health':
        return <HealthCheck />;
      case 'voicecloner':
        return <VoiceCloner />;
      default:
        return <ChatInterface />;
    }
  };

  const TabButton: React.FC<{ tab: Tab; label: string }> = ({ tab, label }) => (
    <button
      className={`tab-button ${activeTab === tab ? 'active' : ''}`}
      onClick={() => setActiveTab(tab)}
    >
      {label}
    </button>
  );

  return (
    <div className="tabs-container">
      <div className="tab-header">
        <TabButton tab="chat" label="💬 Future Chat" />
        <TabButton tab="avatar" label="📸 Create Avatar" />
        <TabButton tab="health" label="✅ System Status" />
        <TabButton tab="voicecloner" label="Voice Cloner"/>
      </div>
      <div className="tab-content">
        {renderContent()}
      </div>
    </div>
  );
};

export default TabContainer;
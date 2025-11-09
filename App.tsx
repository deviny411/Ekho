// ekho-frontend/src/App.tsx

import React from 'react';
import TabContainer from './components/TabContainer'; // <--- NEW IMPORT

function App() {
  return (
    <>
      <div className="ekho-container">
        <h1>Ekho - AI Advising and Journaling</h1>
        
        {/* All components are now managed inside the TabContainer */}
        <TabContainer />
        
      </div>
    </>
  );
}

export default App;
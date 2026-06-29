import React from 'react';
import Watchlist from './pages/Watchlist';
import ShareNote from './pages/ShareNote';
import ContentIncubator from './pages/ContentIncubator';
import 'antd/dist/reset.css';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Watchlist />} />
        <Route path="/watchlist" element={<Watchlist />} />
        <Route path="/share/note/:noteId" element={<ShareNote />} />
        <Route path="/content" element={<ContentIncubator />} />
      </Routes>
    </Router>
  );
}

export default App; 

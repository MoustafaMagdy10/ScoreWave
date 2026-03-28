import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Layout from './components/Layout'
import UploadPage from './pages/UploadPage'
import SeparateAudioPage from './pages/SeparateAudioPage'
import HistoryPage from './pages/HistoryPage'
import EditorPage from './pages/EditorPage'
import LoginPage from './pages/LoginPage'
import ProfilePage from './pages/ProfilePage'

const App: React.FC = () => {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <Layout>
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/separate" element={<SeparateAudioPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/editor" element={<EditorPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Routes>
        </Layout>
      </div>
    </Router>
  )
}

export default App

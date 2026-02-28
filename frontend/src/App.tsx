import { Routes, Route, useLocation } from 'react-router-dom'
import { useState } from 'react'
import ProjectDashboard from './components/ProjectDashboard'
import ProjectDetail from './components/ProjectDetail'
import LogsView from './components/LogsView'
import ChatPanel from './components/ChatPanel'

type Tab = 'projects' | 'logs'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('projects')
  const [chatOpen, setChatOpen] = useState(false)
  const location = useLocation()
  const isDetail = location.pathname.startsWith('/projects/')

  return (
    <div className="min-h-screen bg-gray-950">
      {!isDetail && (
        <nav className="border-b border-gray-800 bg-gray-900">
          <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-12">
            <span className="font-semibold text-white text-sm tracking-wide">Project Management</span>
            <div className="flex gap-1">
              {(['projects', 'logs'] as Tab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                    activeTab === tab
                      ? 'bg-indigo-600 text-white'
                      : 'text-gray-400 hover:text-white hover:bg-gray-800'
                  }`}
                >
                  {tab === 'projects' ? 'Projects' : 'AI Logs'}
                </button>
              ))}
            </div>
          </div>
        </nav>
      )}
      <Routes>
        <Route
          path="/"
          element={activeTab === 'projects' ? <ProjectDashboard /> : <LogsView />}
        />
        <Route path="/projects/:id" element={<ProjectDetail />} />
      </Routes>

      {!chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          aria-label="Open chat"
          className="fixed bottom-6 right-6 w-14 h-14 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full shadow-lg flex items-center justify-center text-2xl z-50"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      )}

      <ChatPanel isOpen={chatOpen} onToggle={() => setChatOpen(false)} />
    </div>
  )
}

import { Routes, Route, useLocation } from 'react-router-dom'
import { useState } from 'react'
import ProjectDashboard from './components/ProjectDashboard'
import ProjectDetail from './components/ProjectDetail'
import LogsView from './components/LogsView'

type Tab = 'projects' | 'logs'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('projects')
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
    </div>
  )
}

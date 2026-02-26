import { Routes, Route } from 'react-router-dom'
import ProjectDashboard from './components/ProjectDashboard'
import ProjectDetail from './components/ProjectDetail'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-950">
      <Routes>
        <Route path="/" element={<ProjectDashboard />} />
        <Route path="/projects/:id" element={<ProjectDetail />} />
      </Routes>
    </div>
  )
}

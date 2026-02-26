import { useEffect, useState } from 'react'
import { listProjects, deleteProject } from '../api'
import type { Project } from '../types'
import ProjectCard from './ProjectCard'
import AnalyzeModal from './AnalyzeModal'

export default function ProjectDashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)

  const fetchProjects = async () => {
    try {
      setLoading(true)
      const data = await listProjects()
      setProjects(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  const handleDelete = async (id: string) => {
    await deleteProject(id)
    setProjects((prev) => prev.filter((p) => p.id !== id))
  }

  const handleAnalyzed = (project: Project) => {
    setProjects((prev) => [project, ...prev])
    setShowModal(false)
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">Project Dashboard</h1>
          <p className="text-gray-400 mt-1">AI-powered GitHub repository analysis</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors"
        >
          <span className="text-lg leading-none">+</span>
          Analyze Repo
        </button>
      </div>

      {/* Content */}
      {loading && (
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-400">Loading projects...</div>
        </div>
      )}

      {error && (
        <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-6">
          {error}
        </div>
      )}

      {!loading && !error && projects.length === 0 && (
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <div className="text-6xl mb-4">🔍</div>
          <h2 className="text-xl font-semibold text-gray-300 mb-2">No projects yet</h2>
          <p className="text-gray-500 mb-6">Paste a GitHub URL and let AI analyze it for you</p>
          <button
            onClick={() => setShowModal(true)}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
          >
            Analyze your first repo
          </button>
        </div>
      )}

      {!loading && projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {showModal && (
        <AnalyzeModal
          onClose={() => setShowModal(false)}
          onSuccess={handleAnalyzed}
        />
      )}
    </div>
  )
}

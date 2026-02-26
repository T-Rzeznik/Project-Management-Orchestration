import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getProject, deleteProject } from '../api'
import type { Project } from '../types'
import TechStackBadges from './TechStackBadges'
import TaskBoard from './TaskBoard'
import MilestoneList from './MilestoneList'
import ContributorAvatars from './ContributorAvatars'

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    getProject(id)
      .then(setProject)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id])

  const handleDelete = async () => {
    if (!project) return
    await deleteProject(project.id)
    navigate('/')
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-gray-400">
        Loading project...
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <p className="text-red-400">{error ?? 'Project not found'}</p>
        <button onClick={() => navigate('/')} className="text-indigo-400 hover:underline">
          ← Back to dashboard
        </button>
      </div>
    )
  }

  const statusColor =
    project.status === 'active'
      ? 'bg-green-900/50 text-green-300 border-green-700'
      : 'bg-gray-700/50 text-gray-400 border-gray-600'

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Back */}
      <button
        onClick={() => navigate('/')}
        className="text-gray-400 hover:text-white transition-colors flex items-center gap-1 text-sm"
      >
        ← Back to Dashboard
      </button>

      {/* Header */}
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <h1 className="text-3xl font-bold text-white">{project.name}</h1>
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusColor}`}>
                {project.status}
              </span>
            </div>
            <a
              href={project.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-400 hover:underline text-sm"
            >
              {project.github_url}
            </a>
            <p className="text-gray-300 mt-3 leading-relaxed">{project.summary || project.description}</p>
          </div>
          <div className="flex items-center gap-4 text-gray-400 text-sm shrink-0">
            <span className="flex flex-col items-center gap-0.5">
              <span className="text-2xl font-bold text-white">{project.stars.toLocaleString()}</span>
              <span className="text-xs">Stars</span>
            </span>
            <span className="flex flex-col items-center gap-0.5">
              <span className="text-2xl font-bold text-white">{project.open_issues_count}</span>
              <span className="text-xs">Issues</span>
            </span>
            <span className="flex flex-col items-center gap-0.5">
              <span className="text-2xl font-bold text-white">{project.tasks.length}</span>
              <span className="text-xs">Tasks</span>
            </span>
          </div>
        </div>

        {/* Tech Stack */}
        {project.tech_stack.length > 0 && (
          <div className="mt-4">
            <TechStackBadges stack={project.tech_stack} />
          </div>
        )}

        {/* Contributors */}
        {project.contributors.length > 0 && (
          <div className="mt-4">
            <ContributorAvatars contributors={project.contributors} />
          </div>
        )}
      </div>

      {/* Task Board */}
      {project.tasks.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-white mb-4">Tasks</h2>
          <TaskBoard tasks={project.tasks} />
        </section>
      )}

      {/* Milestones */}
      {project.milestones.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-white mb-4">Milestones</h2>
          <MilestoneList milestones={project.milestones} />
        </section>
      )}

      {/* Delete */}
      <div className="flex justify-end pt-4 border-t border-gray-800">
        <button
          onClick={handleDelete}
          className="text-red-500 hover:text-red-400 text-sm transition-colors"
        >
          Delete this project
        </button>
      </div>
    </div>
  )
}

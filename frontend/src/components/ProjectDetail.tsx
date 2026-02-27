import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getProject, deleteProject, updateProject } from '../api'
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
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)

  // Edit form state
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editDocumentation, setEditDocumentation] = useState('')
  const [editTechStack, setEditTechStack] = useState('')
  const [editGithubUrl, setEditGithubUrl] = useState('')
  const [editStatus, setEditStatus] = useState('')

  useEffect(() => {
    if (!id) return
    getProject(id)
      .then(setProject)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [id])

  const startEditing = () => {
    if (!project) return
    setEditName(project.name)
    setEditDescription(project.description)
    setEditDocumentation(project.documentation ?? '')
    setEditTechStack(project.tech_stack.join(', '))
    setEditGithubUrl(project.github_url ?? '')
    setEditStatus(project.status)
    setEditing(true)
  }

  const cancelEditing = () => {
    setEditing(false)
  }

  const handleSave = async () => {
    if (!project) return
    setSaving(true)
    setError(null)
    try {
      const updated = await updateProject(project.id, {
        name: editName.trim(),
        description: editDescription.trim(),
        documentation: editDocumentation.trim(),
        tech_stack: editTechStack
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        github_url: editGithubUrl.trim(),
        status: editStatus,
      })
      setProject(updated)
      setEditing(false)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

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

  if (error && !project) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <p className="text-red-400">{error}</p>
        <button onClick={() => navigate('/')} className="text-indigo-400 hover:underline">
          ← Back to dashboard
        </button>
      </div>
    )
  }

  if (!project) return null

  const statusColor =
    project.status === 'active'
      ? 'bg-green-900/50 text-green-300 border-green-700'
      : project.status === 'completed'
        ? 'bg-blue-900/50 text-blue-300 border-blue-700'
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
        {editing ? (
          /* ── Edit Mode ── */
          <div className="space-y-4">
            <div>
              <label htmlFor="ed-name" className="block text-sm text-gray-400 mb-1.5">
                Project Name
              </label>
              <input
                id="ed-name"
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                disabled={saving}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor="ed-desc" className="block text-sm text-gray-400 mb-1.5">
                Description
              </label>
              <textarea
                id="ed-desc"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                disabled={saving}
                rows={3}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 disabled:opacity-50 resize-none"
              />
            </div>

            <div>
              <label htmlFor="ed-docs" className="block text-sm text-gray-400 mb-1.5">
                Documentation
              </label>
              <textarea
                id="ed-docs"
                value={editDocumentation}
                onChange={(e) => setEditDocumentation(e.target.value)}
                disabled={saving}
                rows={4}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 disabled:opacity-50 resize-none"
              />
            </div>

            <div>
              <label htmlFor="ed-tech" className="block text-sm text-gray-400 mb-1.5">
                Tech Stack
              </label>
              <input
                id="ed-tech"
                type="text"
                value={editTechStack}
                onChange={(e) => setEditTechStack(e.target.value)}
                disabled={saving}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              />
              <p className="text-xs text-gray-600 mt-1">Comma-separated</p>
            </div>

            <div>
              <label htmlFor="ed-github" className="block text-sm text-gray-400 mb-1.5">
                GitHub URL
              </label>
              <input
                id="ed-github"
                type="url"
                value={editGithubUrl}
                onChange={(e) => setEditGithubUrl(e.target.value)}
                disabled={saving}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor="ed-status" className="block text-sm text-gray-400 mb-1.5">
                Status
              </label>
              <select
                id="ed-status"
                value={editStatus}
                onChange={(e) => setEditStatus(e.target.value)}
                disabled={saving}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              >
                <option value="active">Active</option>
                <option value="completed">Completed</option>
                <option value="archived">Archived</option>
              </select>
            </div>

            {error && (
              <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
                {error}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                onClick={cancelEditing}
                disabled={saving}
                className="bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium px-5 py-2.5 rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !editName.trim()}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        ) : (
          /* ── View Mode ── */
          <>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 flex-wrap mb-2">
                  <h1 className="text-3xl font-bold text-white">{project.name}</h1>
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusColor}`}>
                    {project.status}
                  </span>
                </div>
                {project.github_url && (
                  <a
                    href={project.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-400 hover:underline text-sm"
                  >
                    {project.github_url}
                  </a>
                )}
                {project.description && (
                  <p className="text-gray-300 mt-3 leading-relaxed">{project.description}</p>
                )}
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={startEditing}
                  className="bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium px-4 py-2 rounded-lg transition-colors text-sm"
                >
                  Edit
                </button>
              </div>
            </div>

            {/* Documentation */}
            {project.documentation && (
              <div className="mt-4">
                <h3 className="text-sm font-medium text-gray-400 mb-1.5">Documentation</h3>
                <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap bg-gray-800/50 rounded-lg p-3 border border-gray-800">
                  {project.documentation}
                </p>
              </div>
            )}

            {/* Stats */}
            {(project.stars > 0 || project.open_issues_count > 0 || project.tasks.length > 0) && (
              <div className="flex items-center gap-4 text-gray-400 text-sm mt-4">
                {project.stars > 0 && (
                  <span className="flex flex-col items-center gap-0.5">
                    <span className="text-2xl font-bold text-white">{project.stars.toLocaleString()}</span>
                    <span className="text-xs">Stars</span>
                  </span>
                )}
                {project.open_issues_count > 0 && (
                  <span className="flex flex-col items-center gap-0.5">
                    <span className="text-2xl font-bold text-white">{project.open_issues_count}</span>
                    <span className="text-xs">Issues</span>
                  </span>
                )}
                <span className="flex flex-col items-center gap-0.5">
                  <span className="text-2xl font-bold text-white">{project.tasks.length}</span>
                  <span className="text-xs">Tasks</span>
                </span>
              </div>
            )}

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
          </>
        )}
      </div>

      {/* Task Board */}
      {!editing && project.tasks.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-white mb-4">Tasks</h2>
          <TaskBoard tasks={project.tasks} />
        </section>
      )}

      {/* Milestones */}
      {!editing && project.milestones.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-white mb-4">Milestones</h2>
          <MilestoneList milestones={project.milestones} />
        </section>
      )}

      {/* Delete */}
      {!editing && (
        <div className="flex justify-end pt-4 border-t border-gray-800">
          <button
            onClick={handleDelete}
            className="text-red-500 hover:text-red-400 text-sm transition-colors"
          >
            Delete this project
          </button>
        </div>
      )}
    </div>
  )
}

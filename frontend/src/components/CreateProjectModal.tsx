import { useState } from 'react'
import { createProject } from '../api'
import type { Project } from '../types'

interface Props {
  onClose: () => void
  onSuccess: (project: Project) => void
}

export default function CreateProjectModal({ onClose, onSuccess }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [techStack, setTechStack] = useState('')
  const [githubUrl, setGithubUrl] = useState('')
  const [documentation, setDocumentation] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    setError(null)
    try {
      const project = await createProject({
        name: name.trim(),
        description: description.trim(),
        tech_stack: techStack
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        github_url: githubUrl.trim(),
        documentation: documentation.trim(),
      })
      onSuccess(project)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-white">Create Project</h2>
          <button
            onClick={onClose}
            disabled={loading}
            className="text-gray-500 hover:text-gray-300 transition-colors text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="cp-name" className="block text-sm text-gray-400 mb-1.5">
              Project Name
            </label>
            <input
              id="cp-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Awesome Project"
              disabled={loading}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 placeholder-gray-600 disabled:opacity-50"
              autoFocus
            />
          </div>

          <div>
            <label htmlFor="cp-desc" className="block text-sm text-gray-400 mb-1.5">
              Description
            </label>
            <textarea
              id="cp-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of the project"
              disabled={loading}
              rows={2}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 placeholder-gray-600 disabled:opacity-50 resize-none"
            />
          </div>

          <div>
            <label htmlFor="cp-tech" className="block text-sm text-gray-400 mb-1.5">
              Tech Stack
            </label>
            <input
              id="cp-tech"
              type="text"
              value={techStack}
              onChange={(e) => setTechStack(e.target.value)}
              placeholder="Python, React, FastAPI"
              disabled={loading}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 placeholder-gray-600 disabled:opacity-50"
            />
            <p className="text-xs text-gray-600 mt-1">Comma-separated</p>
          </div>

          <div>
            <label htmlFor="cp-github" className="block text-sm text-gray-400 mb-1.5">
              GitHub URL
            </label>
            <input
              id="cp-github"
              type="url"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              placeholder="https://github.com/owner/repo (optional)"
              disabled={loading}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 placeholder-gray-600 disabled:opacity-50"
            />
          </div>

          <div>
            <label htmlFor="cp-docs" className="block text-sm text-gray-400 mb-1.5">
              Documentation
            </label>
            <textarea
              id="cp-docs"
              value={documentation}
              onChange={(e) => setDocumentation(e.target.value)}
              placeholder="Notes, links, or documentation for this project"
              disabled={loading}
              rows={3}
              className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 placeholder-gray-600 disabled:opacity-50 resize-none"
            />
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim()}
              className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

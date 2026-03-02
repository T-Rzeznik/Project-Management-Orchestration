import { useState } from 'react'
import { createProject, importFromGithub } from '../api'
import type { Project } from '../types'

interface Props {
  onClose: () => void
  onSuccess: (project: Project) => void
}

type Tab = 'github' | 'manual'

export default function CreateProjectModal({ onClose, onSuccess }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('github')

  // GitHub import state
  const [githubImportUrl, setGithubImportUrl] = useState('')
  const [importLoading, setImportLoading] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)

  // Manual form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [techStack, setTechStack] = useState('')
  const [githubUrl, setGithubUrl] = useState('')
  const [documentation, setDocumentation] = useState('')
  const [manualLoading, setManualLoading] = useState(false)
  const [manualError, setManualError] = useState<string | null>(null)

  const loading = importLoading || manualLoading

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!githubImportUrl.trim()) return
    setImportLoading(true)
    setImportError(null)
    try {
      const project = await importFromGithub(githubImportUrl.trim())
      onSuccess(project)
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : 'Failed to import from GitHub')
    } finally {
      setImportLoading(false)
    }
  }

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setManualLoading(true)
    setManualError(null)
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
      setManualError(e instanceof Error ? e.message : 'Failed to create project')
    } finally {
      setManualLoading(false)
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

        {/* Tabs */}
        <div className="flex border-b border-gray-700 mb-5" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'github'}
            onClick={() => setActiveTab('github')}
            disabled={loading}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'github'
                ? 'text-indigo-400 border-b-2 border-indigo-400'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            From GitHub
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'manual'}
            onClick={() => setActiveTab('manual')}
            disabled={loading}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'manual'
                ? 'text-indigo-400 border-b-2 border-indigo-400'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Manual
          </button>
        </div>

        {/* GitHub Import Tab */}
        {activeTab === 'github' && (
          <form onSubmit={handleImport} className="space-y-4">
            <div>
              <label htmlFor="gh-url" className="block text-sm text-gray-400 mb-1.5">
                GitHub Repository URL
              </label>
              <input
                id="gh-url"
                type="text"
                value={githubImportUrl}
                onChange={(e) => setGithubImportUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                disabled={importLoading}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 placeholder-gray-600 disabled:opacity-50"
                autoFocus
              />
            </div>

            {importError && (
              <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
                {importError}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={importLoading}
                className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={importLoading || !githubImportUrl.trim()}
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {importLoading ? 'Importing...' : 'Import'}
              </button>
            </div>
          </form>
        )}

        {/* Manual Tab */}
        {activeTab === 'manual' && (
          <form onSubmit={handleManualSubmit} className="space-y-4">
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
                disabled={manualLoading}
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
                disabled={manualLoading}
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
                disabled={manualLoading}
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
                disabled={manualLoading}
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
                disabled={manualLoading}
                rows={3}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-indigo-500 placeholder-gray-600 disabled:opacity-50 resize-none"
              />
            </div>

            {manualError && (
              <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
                {manualError}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={manualLoading}
                className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={manualLoading || !name.trim()}
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {manualLoading ? 'Creating...' : 'Create'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

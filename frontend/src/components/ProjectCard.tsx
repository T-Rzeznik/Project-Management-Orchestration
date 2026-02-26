import { useNavigate } from 'react-router-dom'
import type { Project } from '../types'

interface Props {
  project: Project
  onDelete: (id: string) => void
}

export default function ProjectCard({ project, onDelete }: Props) {
  const navigate = useNavigate()

  const statusColor =
    project.status === 'active'
      ? 'bg-green-900/50 text-green-300 border-green-700'
      : 'bg-gray-700/50 text-gray-400 border-gray-600'

  return (
    <div
      className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-4 hover:border-indigo-700 transition-colors cursor-pointer"
      onClick={() => navigate(`/projects/${project.id}`)}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-white leading-tight">{project.name}</h2>
          <a
            href={project.github_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-indigo-400 hover:underline mt-0.5 block"
            onClick={(e) => e.stopPropagation()}
          >
            {project.github_url.replace('https://github.com/', '')}
          </a>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium shrink-0 ${statusColor}`}>
          {project.status}
        </span>
      </div>

      {/* Description */}
      <p className="text-gray-400 text-sm line-clamp-2">{project.description}</p>

      {/* Tech stack badges */}
      {project.tech_stack.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {project.tech_stack.slice(0, 5).map((tech) => (
            <span key={tech} className="bg-gray-800 text-gray-300 text-xs px-2 py-0.5 rounded-md border border-gray-700">
              {tech}
            </span>
          ))}
          {project.tech_stack.length > 5 && (
            <span className="text-gray-500 text-xs py-0.5">+{project.tech_stack.length - 5}</span>
          )}
        </div>
      )}

      {/* Footer stats */}
      <div className="flex items-center justify-between text-gray-500 text-xs pt-1 border-t border-gray-800">
        <div className="flex items-center gap-3">
          <span>⭐ {project.stars.toLocaleString()}</span>
          <span>🐛 {project.open_issues_count}</span>
          <span>📋 {project.tasks.length} tasks</span>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onDelete(project.id)
          }}
          className="text-gray-600 hover:text-red-400 transition-colors"
          aria-label="Delete project"
        >
          🗑️
        </button>
      </div>
    </div>
  )
}

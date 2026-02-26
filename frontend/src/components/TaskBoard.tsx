import type { Task } from '../types'

interface Props {
  tasks: Task[]
}

const columns: { key: Task['status']; label: string; color: string }[] = [
  { key: 'todo', label: 'To Do', color: 'border-gray-600' },
  { key: 'in-progress', label: 'In Progress', color: 'border-yellow-600' },
  { key: 'done', label: 'Done', color: 'border-green-600' },
]

const priorityBadge: Record<Task['priority'], string> = {
  high: 'bg-red-900/50 text-red-300 border-red-700',
  medium: 'bg-yellow-900/50 text-yellow-300 border-yellow-700',
  low: 'bg-gray-700/50 text-gray-400 border-gray-600',
}

export default function TaskBoard({ tasks }: Props) {
  const grouped = columns.map(({ key, label, color }) => ({
    key,
    label,
    color,
    items: tasks.filter((t) => t.status === key),
  }))

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {grouped.map(({ key, label, color, items }) => (
        <div key={key} className={`bg-gray-900 border-t-2 ${color} rounded-xl p-4`}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-300 text-sm">{label}</h3>
            <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded-full">
              {items.length}
            </span>
          </div>
          <div className="space-y-3">
            {items.length === 0 && (
              <p className="text-gray-600 text-xs text-center py-4">Empty</p>
            )}
            {items.map((task, i) => (
              <div key={i} className="bg-gray-800 rounded-lg p-3 border border-gray-700">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <h4 className="text-sm font-medium text-white leading-snug">{task.title}</h4>
                  <span className={`text-xs px-1.5 py-0.5 rounded border shrink-0 ${priorityBadge[task.priority] ?? priorityBadge.medium}`}>
                    {task.priority}
                  </span>
                </div>
                <p className="text-gray-400 text-xs leading-relaxed">{task.description}</p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

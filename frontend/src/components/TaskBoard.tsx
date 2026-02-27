import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  useDroppable,
  useDraggable,
} from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import { useState } from 'react'
import type { Task } from '../types'

interface Props {
  tasks: Task[]
  onTaskMove?: (taskId: string, newStatus: Task['status']) => void
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

export function handleDragEnd(
  event: DragEndEvent,
  onTaskMove: ((taskId: string, newStatus: Task['status']) => void) | undefined,
  tasks: Task[],
) {
  if (!onTaskMove || !event.over) return

  const taskId = String(event.active.id)
  const targetColumnId = String(event.over.id)
  const newStatus = targetColumnId.replace('column-', '') as Task['status']

  const task = tasks.find((t) => t.id === taskId)
  if (!task || task.status === newStatus) return

  onTaskMove(taskId, newStatus)
}

function TaskCard({ task }: { task: Task }) {
  return (
    <>
      <div className="flex items-start justify-between gap-2 mb-1">
        <h4 className="text-sm font-medium text-white leading-snug">{task.title}</h4>
        <span
          className={`text-xs px-1.5 py-0.5 rounded border shrink-0 ${priorityBadge[task.priority] ?? priorityBadge.medium}`}
        >
          {task.priority}
        </span>
      </div>
      <p className="text-gray-400 text-xs leading-relaxed">{task.description}</p>
    </>
  )
}

function DraggableTask({ task }: { task: Task }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
  })
  const style = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      data-task-id={task.id}
      className={`bg-gray-800 rounded-lg p-3 border border-gray-700 cursor-grab active:cursor-grabbing transition-shadow ${isDragging ? 'opacity-50 shadow-lg shadow-indigo-500/20' : ''}`}
    >
      <TaskCard task={task} />
    </div>
  )
}

function DroppableColumn({
  status,
  color,
  label,
  items,
}: {
  status: string
  color: string
  label: string
  items: Task[]
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `column-${status}` })

  return (
    <div
      ref={setNodeRef}
      data-column-status={status}
      className={`bg-gray-900 border-t-2 ${color} rounded-xl p-4 transition-all ${isOver ? 'ring-2 ring-indigo-500/50 bg-gray-900/80' : ''}`}
    >
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
        {items.map((task) => (
          <DraggableTask key={task.id} task={task} />
        ))}
      </div>
    </div>
  )
}

export default function TaskBoard({ tasks, onTaskMove }: Props) {
  const [activeTask, setActiveTask] = useState<Task | null>(null)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor),
  )

  const handleDragStart = (event: DragStartEvent) => {
    const task = tasks.find((t) => t.id === String(event.active.id))
    setActiveTask(task ?? null)
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={(event) => {
        handleDragEnd(event, onTaskMove, tasks)
        setActiveTask(null)
      }}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {columns.map(({ key, label, color }) => (
          <DroppableColumn
            key={key}
            status={key}
            color={color}
            label={label}
            items={tasks.filter((t) => t.status === key)}
          />
        ))}
      </div>
      <DragOverlay>
        {activeTask ? (
          <div className="bg-gray-800 rounded-lg p-3 border border-indigo-500 shadow-xl shadow-indigo-500/30 w-64">
            <TaskCard task={activeTask} />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  )
}

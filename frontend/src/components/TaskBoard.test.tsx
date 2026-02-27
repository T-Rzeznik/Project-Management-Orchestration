import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import TaskBoard, { handleDragEnd } from './TaskBoard'
import type { Task } from '../types'

const mockTasks: Task[] = [
  { id: 'task-1', title: 'Write tests', description: 'TDD first', priority: 'high', status: 'todo' },
  { id: 'task-2', title: 'Implement DnD', description: 'Add drag', priority: 'medium', status: 'in-progress' },
  { id: 'task-3', title: 'Deploy', description: 'Ship it', priority: 'low', status: 'done' },
]

describe('TaskBoard', () => {
  it('should render three columns', () => {
    render(<TaskBoard tasks={mockTasks} onTaskMove={vi.fn()} />)
    expect(screen.getByText('To Do')).toBeInTheDocument()
    expect(screen.getByText('In Progress')).toBeInTheDocument()
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('should render tasks in their respective columns', () => {
    render(<TaskBoard tasks={mockTasks} onTaskMove={vi.fn()} />)
    expect(screen.getByText('Write tests')).toBeInTheDocument()
    expect(screen.getByText('Implement DnD')).toBeInTheDocument()
    expect(screen.getByText('Deploy')).toBeInTheDocument()
  })

  it('should show empty message for columns with no tasks', () => {
    const todoOnly: Task[] = [
      { id: 'task-1', title: 'Only todo', description: 'desc', priority: 'medium', status: 'todo' },
    ]
    render(<TaskBoard tasks={todoOnly} onTaskMove={vi.fn()} />)
    const empties = screen.getAllByText('Empty')
    expect(empties).toHaveLength(2)
  })

  it('should render task cards with data-task-id attributes', () => {
    render(<TaskBoard tasks={mockTasks} onTaskMove={vi.fn()} />)
    const card = screen.getByText('Write tests').closest('[data-task-id]')
    expect(card).toHaveAttribute('data-task-id', 'task-1')
  })

  it('should render droppable columns with data-column-status attributes', () => {
    render(<TaskBoard tasks={mockTasks} onTaskMove={vi.fn()} />)
    const columns = document.querySelectorAll('[data-column-status]')
    expect(columns).toHaveLength(3)
    const statuses = Array.from(columns).map(c => c.getAttribute('data-column-status'))
    expect(statuses).toEqual(['todo', 'in-progress', 'done'])
  })
})

describe('handleDragEnd', () => {
  it('should call onTaskMove when dropped on a different column', () => {
    const onTaskMove = vi.fn()
    const event = {
      active: { id: 'task-1' },
      over: { id: 'column-in-progress' },
    }
    handleDragEnd(event as any, onTaskMove, mockTasks)
    expect(onTaskMove).toHaveBeenCalledWith('task-1', 'in-progress')
  })

  it('should NOT call onTaskMove when dropped on same column', () => {
    const onTaskMove = vi.fn()
    const event = {
      active: { id: 'task-1' },
      over: { id: 'column-todo' },
    }
    handleDragEnd(event as any, onTaskMove, mockTasks)
    expect(onTaskMove).not.toHaveBeenCalled()
  })

  it('should NOT call onTaskMove when dropped outside any column', () => {
    const onTaskMove = vi.fn()
    const event = {
      active: { id: 'task-1' },
      over: null,
    }
    handleDragEnd(event as any, onTaskMove, mockTasks)
    expect(onTaskMove).not.toHaveBeenCalled()
  })
})

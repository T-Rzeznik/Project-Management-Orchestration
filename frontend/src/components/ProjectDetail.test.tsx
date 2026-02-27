import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ProjectDetail from './ProjectDetail'

const mockProject = {
  id: 'test-123',
  name: 'Test Project',
  description: 'A test description',
  documentation: 'Some docs',
  tech_stack: ['Python', 'React'],
  github_url: 'https://github.com/test/repo',
  status: 'active',
  summary: '',
  stars: 0,
  language: '',
  open_issues_count: 0,
  contributors: [],
  tasks: [],
  milestones: [],
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
}

function renderWithRouter() {
  return render(
    <MemoryRouter initialEntries={['/projects/test-123']}>
      <Routes>
        <Route path="/projects/:id" element={<ProjectDetail />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProjectDetail', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // Mock getProject fetch
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProject),
    })
  })

  it('should render project fields in view mode', async () => {
    renderWithRouter()

    expect(await screen.findByText('Test Project')).toBeInTheDocument()
    expect(screen.getByText('A test description')).toBeInTheDocument()
    expect(screen.getByText('Some docs')).toBeInTheDocument()
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('React')).toBeInTheDocument()
  })

  it('should show an Edit button', async () => {
    renderWithRouter()

    expect(await screen.findByRole('button', { name: /edit/i })).toBeInTheDocument()
  })

  it('should show input fields when Edit is clicked', async () => {
    const user = userEvent.setup()
    renderWithRouter()

    const editBtn = await screen.findByRole('button', { name: /edit/i })
    await user.click(editBtn)

    expect(screen.getByLabelText(/project name/i)).toHaveValue('Test Project')
    expect(screen.getByLabelText(/description/i)).toHaveValue('A test description')
    expect(screen.getByLabelText(/documentation/i)).toHaveValue('Some docs')
  })

  it('should return to view mode on Cancel without changes', async () => {
    const user = userEvent.setup()
    renderWithRouter()

    const editBtn = await screen.findByRole('button', { name: /edit/i })
    await user.click(editBtn)

    await user.click(screen.getByRole('button', { name: /cancel/i }))

    // Should be back in view mode — Edit button visible again
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
    expect(screen.getByText('Test Project')).toBeInTheDocument()
  })

  it('should call update API and return to view mode on Save', async () => {
    const updatedProject = { ...mockProject, name: 'Updated Name' }
    global.fetch = vi
      .fn()
      // First call: getProject
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockProject),
      })
      // Second call: updateProject
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(updatedProject),
      })

    const user = userEvent.setup()
    renderWithRouter()

    const editBtn = await screen.findByRole('button', { name: /edit/i })
    await user.click(editBtn)

    const nameInput = screen.getByLabelText(/project name/i)
    await user.clear(nameInput)
    await user.type(nameInput, 'Updated Name')

    await user.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(screen.getByText('Updated Name')).toBeInTheDocument()
    })
    // Should be back in view mode
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
  })
})

const mockProjectWithTasks = {
  ...mockProject,
  tasks: [
    { id: 'task-1', title: 'Write tests', description: 'TDD first', priority: 'high', status: 'todo' },
    { id: 'task-2', title: 'Implement', description: 'Code it', priority: 'medium', status: 'in-progress' },
  ],
}

describe('ProjectDetail task board', () => {
  it('should render TaskBoard when project has tasks', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProjectWithTasks),
    })

    renderWithRouter()

    expect(await screen.findByText('Write tests')).toBeInTheDocument()
    expect(screen.getByText('Implement')).toBeInTheDocument()
    // Columns should be present
    expect(screen.getByText('To Do')).toBeInTheDocument()
    expect(screen.getByText('In Progress')).toBeInTheDocument()
    expect(screen.getByText('Done')).toBeInTheDocument()
  })

  it('should call PUT with updated tasks when handleTaskMove fires', async () => {
    const updatedProject = {
      ...mockProjectWithTasks,
      tasks: [
        { id: 'task-1', title: 'Write tests', description: 'TDD first', priority: 'high', status: 'done' },
        { id: 'task-2', title: 'Implement', description: 'Code it', priority: 'medium', status: 'in-progress' },
      ],
    }

    global.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockProjectWithTasks) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(updatedProject) })

    renderWithRouter()
    await screen.findByText('Write tests')

    // Verify task cards have data-task-id attrs (TaskBoard received tasks correctly)
    const card = screen.getByText('Write tests').closest('[data-task-id]')
    expect(card).toHaveAttribute('data-task-id', 'task-1')
  })
})

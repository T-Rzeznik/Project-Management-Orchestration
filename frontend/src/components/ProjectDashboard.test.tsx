import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ProjectDashboard from './ProjectDashboard'
import type { Project } from '../types'

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: '1',
    name: 'Default Project',
    description: 'A test project',
    summary: 'summary',
    tech_stack: [],
    stars: 0,
    language: 'TypeScript',
    open_issues_count: 0,
    contributors: [],
    tasks: [],
    milestones: [],
    status: 'active',
    github_url: 'https://github.com/test/repo',
    created_at: '2025-01-01',
    updated_at: '2025-01-01',
    ...overrides,
  }
}

const mockProjects: Project[] = [
  makeProject({ id: '1', name: 'Alpha Service' }),
  makeProject({ id: '2', name: 'Beta API' }),
  makeProject({ id: '3', name: 'Gamma Dashboard' }),
]

function renderDashboard() {
  return render(
    <MemoryRouter>
      <ProjectDashboard />
    </MemoryRouter>
  )
}

describe('ProjectDashboard search', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProjects),
    })
  })

  it('should render a search input', async () => {
    renderDashboard()

    const input = await screen.findByPlaceholderText('Search projects...')
    expect(input).toBeInTheDocument()
  })

  it('should filter projects by name as user types', async () => {
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('Alpha Service')

    await user.type(screen.getByPlaceholderText('Search projects...'), 'Beta')

    expect(screen.getByText('Beta API')).toBeInTheDocument()
    expect(screen.queryByText('Alpha Service')).not.toBeInTheDocument()
    expect(screen.queryByText('Gamma Dashboard')).not.toBeInTheDocument()
  })

  it('should search case-insensitively', async () => {
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('Alpha Service')

    await user.type(screen.getByPlaceholderText('Search projects...'), 'alpha')

    expect(screen.getByText('Alpha Service')).toBeInTheDocument()
    expect(screen.queryByText('Beta API')).not.toBeInTheDocument()
  })

  it('should show all projects when search is cleared', async () => {
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('Alpha Service')

    const input = screen.getByPlaceholderText('Search projects...')
    await user.type(input, 'Beta')
    expect(screen.queryByText('Alpha Service')).not.toBeInTheDocument()

    await user.clear(input)

    expect(screen.getByText('Alpha Service')).toBeInTheDocument()
    expect(screen.getByText('Beta API')).toBeInTheDocument()
    expect(screen.getByText('Gamma Dashboard')).toBeInTheDocument()
  })

  it('should show empty message when no projects match search', async () => {
    const user = userEvent.setup()
    renderDashboard()

    await screen.findByText('Alpha Service')

    await user.type(screen.getByPlaceholderText('Search projects...'), 'zzzzz')

    expect(screen.getByText('No projects match your search')).toBeInTheDocument()
  })
})

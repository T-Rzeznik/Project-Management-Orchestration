import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CreateProjectModal from './CreateProjectModal'

describe('CreateProjectModal', () => {
  const mockOnClose = vi.fn()
  const mockOnSuccess = vi.fn()

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should render all form fields', () => {
    render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    expect(screen.getByLabelText(/project name/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/description/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/tech stack/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/github/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/documentation/i)).toBeInTheDocument()
  })

  it('should have submit button disabled when name is empty', () => {
    render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    const submitBtn = screen.getByRole('button', { name: /create/i })
    expect(submitBtn).toBeDisabled()
  })

  it('should enable submit button when name is filled', async () => {
    const user = userEvent.setup()
    render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    await user.type(screen.getByLabelText(/project name/i), 'My Project')

    const submitBtn = screen.getByRole('button', { name: /create/i })
    expect(submitBtn).toBeEnabled()
  })

  it('should call onSuccess with project data on successful submit', async () => {
    const fakeProject = { id: '123', name: 'My Project' }
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(fakeProject),
    })

    const user = userEvent.setup()
    render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    await user.type(screen.getByLabelText(/project name/i), 'My Project')
    await user.click(screen.getByRole('button', { name: /create/i }))

    expect(mockOnSuccess).toHaveBeenCalledWith(fakeProject)
  })

  it('should show error message on API failure', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Server error' }),
    })

    const user = userEvent.setup()
    render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    await user.type(screen.getByLabelText(/project name/i), 'My Project')
    await user.click(screen.getByRole('button', { name: /create/i }))

    expect(await screen.findByText(/server error/i)).toBeInTheDocument()
  })
})

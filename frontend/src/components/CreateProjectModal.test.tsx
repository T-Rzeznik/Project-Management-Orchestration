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

  describe('GitHub import tab', () => {
    it('should render GitHub URL input by default', () => {
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      expect(screen.getByPlaceholderText(/github\.com/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /import/i })).toBeInTheDocument()
    })

    it('should have import button disabled when URL is empty', () => {
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      expect(screen.getByRole('button', { name: /import/i })).toBeDisabled()
    })

    it('should enable import button when URL is entered', async () => {
      const user = userEvent.setup()
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      await user.type(
        screen.getByPlaceholderText(/github\.com/i),
        'https://github.com/owner/repo',
      )

      expect(screen.getByRole('button', { name: /import/i })).toBeEnabled()
    })

    it('should call API and trigger onSuccess on submit', async () => {
      const fakeProject = { id: '456', name: 'Imported' }
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(fakeProject),
      })

      const user = userEvent.setup()
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      await user.type(
        screen.getByPlaceholderText(/github\.com/i),
        'https://github.com/owner/repo',
      )
      await user.click(screen.getByRole('button', { name: /import/i }))

      expect(mockOnSuccess).toHaveBeenCalledWith(fakeProject)
    })

    it('should show error on failure', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: 'Repository not found' }),
      })

      const user = userEvent.setup()
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      await user.type(
        screen.getByPlaceholderText(/github\.com/i),
        'https://github.com/bad/url',
      )
      await user.click(screen.getByRole('button', { name: /import/i }))

      expect(await screen.findByText(/repository not found/i)).toBeInTheDocument()
    })
  })

  describe('Manual tab', () => {
    it('should switch to manual tab and show form fields', async () => {
      const user = userEvent.setup()
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      await user.click(screen.getByRole('tab', { name: /manual/i }))

      expect(screen.getByLabelText(/project name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/description/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/tech stack/i)).toBeInTheDocument()
    })

    it('should have create button disabled when name is empty', async () => {
      const user = userEvent.setup()
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      await user.click(screen.getByRole('tab', { name: /manual/i }))

      const submitBtn = screen.getByRole('button', { name: /create/i })
      expect(submitBtn).toBeDisabled()
    })

    it('should call onSuccess with project data on manual submit', async () => {
      const fakeProject = { id: '123', name: 'My Project' }
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(fakeProject),
      })

      const user = userEvent.setup()
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      await user.click(screen.getByRole('tab', { name: /manual/i }))
      await user.type(screen.getByLabelText(/project name/i), 'My Project')
      await user.click(screen.getByRole('button', { name: /create/i }))

      expect(mockOnSuccess).toHaveBeenCalledWith(fakeProject)
    })

    it('should show error message on manual API failure', async () => {
      global.fetch = vi.fn().mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: 'Server error' }),
      })

      const user = userEvent.setup()
      render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

      await user.click(screen.getByRole('tab', { name: /manual/i }))
      await user.type(screen.getByLabelText(/project name/i), 'My Project')
      await user.click(screen.getByRole('button', { name: /create/i }))

      expect(await screen.findByText(/server error/i)).toBeInTheDocument()
    })
  })

  it('should switch between tabs', async () => {
    const user = userEvent.setup()
    render(<CreateProjectModal onClose={mockOnClose} onSuccess={mockOnSuccess} />)

    // Starts on GitHub tab
    expect(screen.getByPlaceholderText(/github\.com/i)).toBeInTheDocument()

    // Switch to Manual
    await user.click(screen.getByRole('tab', { name: /manual/i }))
    expect(screen.getByLabelText(/project name/i)).toBeInTheDocument()

    // Switch back to GitHub
    await user.click(screen.getByRole('tab', { name: /github/i }))
    expect(screen.getByPlaceholderText(/github\.com/i)).toBeInTheDocument()
  })
})

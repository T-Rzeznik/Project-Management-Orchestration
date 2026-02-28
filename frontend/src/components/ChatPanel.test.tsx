import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ChatPanel from './ChatPanel'
import App from '../App'

describe('ChatPanel', () => {
  const mockOnToggle = vi.fn()

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should return null when isOpen is false', () => {
    const { container } = render(<ChatPanel isOpen={false} onToggle={mockOnToggle} />)
    expect(container.innerHTML).toBe('')
  })

  it('should render header with "AI Chat" when open', () => {
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)
    expect(screen.getByText('AI Chat')).toBeInTheDocument()
  })

  it('should render input and send button', () => {
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)
    expect(screen.getByPlaceholderText(/type a message/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument()
  })

  it('should have send button disabled when input is empty', () => {
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })

  it('should enable send button when input has text', async () => {
    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    expect(screen.getByRole('button', { name: /send/i })).toBeEnabled()
  })

  it('should display user message after sending', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        assistant_message: 'Hi there!',
        input_tokens: 10,
        output_tokens: 5,
      }),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('should display assistant response after sending', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        assistant_message: 'Hi there!',
        input_tokens: 10,
        output_tokens: 5,
      }),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(await screen.findByText('Hi there!')).toBeInTheDocument()
  })

  it('should clear input after sending', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        assistant_message: 'Response',
        input_tokens: 10,
        output_tokens: 5,
      }),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    const input = screen.getByPlaceholderText(/type a message/i)
    await user.type(input, 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(input).toHaveValue('')
  })

  it('should show "Thinking..." while loading', async () => {
    let resolvePromise: (value: unknown) => void
    global.fetch = vi.fn().mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePromise = resolve
      })
    )

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(screen.getByText('Thinking...')).toBeInTheDocument()

    // Resolve to avoid dangling promise
    resolvePromise!({
      ok: true,
      json: () => Promise.resolve({
        assistant_message: 'Done',
        input_tokens: 10,
        output_tokens: 5,
      }),
    })

    await waitFor(() => {
      expect(screen.queryByText('Thinking...')).not.toBeInTheDocument()
    })
  })

  it('should show error on fetch failure', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Server error' }),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(await screen.findByText(/server error/i)).toBeInTheDocument()
  })

  it('should call onToggle when close button is clicked', async () => {
    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.click(screen.getByRole('button', { name: /close/i }))
    expect(mockOnToggle).toHaveBeenCalled()
  })

  it('should submit on Enter key press', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        assistant_message: 'Response',
        input_tokens: 10,
        output_tokens: 5,
      }),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    const input = screen.getByPlaceholderText(/type a message/i)
    await user.type(input, 'Hello')
    await user.keyboard('{Enter}')

    expect(screen.getByText('Hello')).toBeInTheDocument()
  })
})


// --- Phase 5: App integration tests ---

describe('App chat integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // Mock the projects API call that ProjectDashboard makes on mount
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })
  })

  it('should show chat toggle button', () => {
    render(<MemoryRouter><App /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /open chat/i })).toBeInTheDocument()
  })

  it('should hide chat panel by default', () => {
    render(<MemoryRouter><App /></MemoryRouter>)
    expect(screen.queryByText('AI Chat')).not.toBeInTheDocument()
  })

  it('should open chat panel when toggle button is clicked', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><App /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /open chat/i }))
    expect(screen.getByText('AI Chat')).toBeInTheDocument()
  })

  it('should close chat panel when close button is clicked', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><App /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /open chat/i }))
    expect(screen.getByText('AI Chat')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /close/i }))
    expect(screen.queryByText('AI Chat')).not.toBeInTheDocument()
  })

  it('should hide toggle button when panel is open', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><App /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /open chat/i }))
    expect(screen.queryByRole('button', { name: /open chat/i })).not.toBeInTheDocument()
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import ChatPanel from './ChatPanel'
import App from '../App'

/** Helper: build a mock ChatStepResponse with status=done */
function doneResponse(overrides: Record<string, unknown> = {}) {
  return {
    status: 'done',
    thread_id: 'thread-test',
    pending_tools: [],
    completed_steps: [],
    assistant_message: '',
    input_tokens: 10,
    output_tokens: 5,
    ...overrides,
  }
}

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
      json: () => Promise.resolve(doneResponse({ assistant_message: 'Hi there!' })),
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
      json: () => Promise.resolve(doneResponse({ assistant_message: 'Hi there!' })),
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
      json: () => Promise.resolve(doneResponse({ assistant_message: 'Response' })),
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
      json: () => Promise.resolve(doneResponse({ assistant_message: 'Done' })),
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
      json: () => Promise.resolve(doneResponse({ assistant_message: 'Response' })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    const input = screen.getByPlaceholderText(/type a message/i)
    await user.type(input, 'Hello')
    await user.keyboard('{Enter}')

    expect(screen.getByText('Hello')).toBeInTheDocument()
  })
})


// --- Tool Steps rendering tests ---

describe('ChatPanel tool steps', () => {
  const mockOnToggle = vi.fn()

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should render tool step cards when response has completed_steps', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({
        assistant_message: 'Analyzed it!',
        completed_steps: [{
          tool_name: 'read_github_repo',
          tool_label: 'Read GitHub Repository',
          args: { github_url: 'pallets/flask' },
          summary: 'Fetched pallets/flask',
          detail: { owner: 'pallets' },
          duration_ms: 100,
        }],
      })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Analyze flask')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(await screen.findByText('Read GitHub Repository')).toBeInTheDocument()
    expect(screen.getByText('Fetched pallets/flask')).toBeInTheDocument()
    expect(screen.getByText('Analyzed it!')).toBeInTheDocument()
  })

  it('should not render tool steps container when no steps', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({ assistant_message: 'Just text' })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(await screen.findByText('Just text')).toBeInTheDocument()
    expect(screen.queryByText('Read GitHub Repository')).not.toBeInTheDocument()
  })

  it('should render multiple tool steps in order', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({
        assistant_message: 'All done!',
        completed_steps: [
          {
            tool_name: 'read_github_repo',
            tool_label: 'Read GitHub Repository',
            args: {},
            summary: 'Fetched repo',
            detail: {},
            duration_ms: 50,
          },
          {
            tool_name: 'create_project',
            tool_label: 'Create Project',
            args: {},
            summary: 'Created project: Flask',
            detail: {},
            duration_ms: 30,
          },
        ],
      })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Analyze and create')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(await screen.findByText('Read GitHub Repository')).toBeInTheDocument()
    expect(screen.getByText('Create Project')).toBeInTheDocument()
  })
})


// --- Markdown rendering tests ---

describe('ChatPanel markdown rendering', () => {
  const mockOnToggle = vi.fn()

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should render bold markdown as <strong> in assistant messages', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({
        assistant_message: 'This is **bold text** here.',
      })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await screen.findByText('bold text')
    // The bold text should be wrapped in a <strong> tag
    const strong = document.querySelector('strong')
    expect(strong).not.toBeNull()
    expect(strong!.textContent).toBe('bold text')
  })

  it('should render code blocks in assistant messages', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({
        assistant_message: 'Here is `inline code` for you.',
      })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await screen.findByText('inline code')
    const code = document.querySelector('code')
    expect(code).not.toBeNull()
    expect(code!.textContent).toBe('inline code')
  })

  it('should NOT render markdown in user messages', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({
        assistant_message: 'Got it.',
      })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), '**not bold**')
    await user.click(screen.getByRole('button', { name: /send/i }))

    // User message should show raw markdown, not rendered
    expect(await screen.findByText('**not bold**')).toBeInTheDocument()
  })
})


// --- Agent metadata display tests ---

describe('ChatPanel metadata bar', () => {
  const mockOnToggle = vi.fn()

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should display agent name and model name below assistant message', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({
        assistant_message: 'Hello!',
        input_tokens: 100,
        output_tokens: 50,
        agent_name: 'project_creator',
        model_name: 'gemini-2.5-flash',
      })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hi')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(await screen.findByText('Hello!')).toBeInTheDocument()
    expect(screen.getByText('project_creator')).toBeInTheDocument()
    expect(screen.getByText(/gemini-2.5-flash/)).toBeInTheDocument()
  })

  it('should display token counts below assistant message', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({
        assistant_message: 'Done!',
        input_tokens: 200,
        output_tokens: 75,
        agent_name: 'project_creator',
        model_name: 'gemini-2.5-flash',
      })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Test')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(await screen.findByText('Done!')).toBeInTheDocument()
    expect(screen.getByTestId('token-counts')).toHaveTextContent('200')
    expect(screen.getByTestId('token-counts')).toHaveTextContent('75')
  })

  it('should not display metadata bar for user messages', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(doneResponse({
        assistant_message: 'Reply',
        agent_name: 'project_creator',
        model_name: 'gemini-2.5-flash',
      })),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Hello')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await screen.findByText('Reply')
    // There should be exactly one metadata bar (for the assistant message), not for user
    const metadataBars = screen.getAllByTestId('message-metadata')
    expect(metadataBars).toHaveLength(1)
  })
})


// --- Step-by-step approval flow tests ---

describe('ChatPanel step-by-step approval', () => {
  const mockOnToggle = vi.fn()

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('should show ToolApprovalCard when agent returns tool_pending', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: 'tool_pending',
        thread_id: 'thread-abc',
        pending_tools: [{
          tool_name: 'read_github_repo',
          tool_label: 'Read GitHub Repository',
          args: { github_url: 'pallets/flask' },
          tool_call_id: 'call_1',
        }],
        completed_steps: [],
        assistant_message: '',
        input_tokens: 0,
        output_tokens: 0,
      }),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Analyze flask')
    await user.click(screen.getByRole('button', { name: /send/i }))

    expect(await screen.findByText('Tool Approval Required')).toBeInTheDocument()
    expect(screen.getByText('Read GitHub Repository')).toBeInTheDocument()
    expect(screen.getByTestId('approve-btn')).toBeInTheDocument()
    expect(screen.getByTestId('deny-btn')).toBeInTheDocument()
  })

  it('should disable input while tools are pending', async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        status: 'tool_pending',
        thread_id: 'thread-abc',
        pending_tools: [{
          tool_name: 'read_github_repo',
          tool_label: 'Read GitHub Repository',
          args: {},
          tool_call_id: 'call_1',
        }],
        completed_steps: [],
        assistant_message: '',
        input_tokens: 0,
        output_tokens: 0,
      }),
    })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Analyze flask')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await screen.findByText('Tool Approval Required')
    expect(screen.getByPlaceholderText(/type a message/i)).toBeDisabled()
  })

  it('should call approve API and show final response on approve', async () => {
    // First call: POST /api/chat → tool_pending
    // Second call: POST /api/chat/approve → done
    global.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          status: 'tool_pending',
          thread_id: 'thread-abc',
          pending_tools: [{
            tool_name: 'read_github_repo',
            tool_label: 'Read GitHub Repository',
            args: { github_url: 'pallets/flask' },
            tool_call_id: 'call_1',
          }],
          completed_steps: [],
          assistant_message: '',
          input_tokens: 0,
          output_tokens: 0,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(doneResponse({
          assistant_message: 'Analyzed Flask successfully!',
          completed_steps: [{
            tool_name: 'read_github_repo',
            tool_label: 'Read GitHub Repository',
            args: { github_url: 'pallets/flask' },
            summary: 'Fetched pallets/flask',
            detail: {},
            duration_ms: 100,
          }],
        })),
      })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Analyze flask')
    await user.click(screen.getByRole('button', { name: /send/i }))

    // Wait for approval card
    await screen.findByText('Tool Approval Required')
    // Click approve
    await user.click(screen.getByTestId('approve-btn'))

    // Should show final response
    expect(await screen.findByText('Analyzed Flask successfully!')).toBeInTheDocument()
  })

  it('should call deny API and show adapted response on deny', async () => {
    global.fetch = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          status: 'tool_pending',
          thread_id: 'thread-abc',
          pending_tools: [{
            tool_name: 'read_github_repo',
            tool_label: 'Read GitHub Repository',
            args: {},
            tool_call_id: 'call_1',
          }],
          completed_steps: [],
          assistant_message: '',
          input_tokens: 0,
          output_tokens: 0,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(doneResponse({
          assistant_message: 'Tool was denied. How else can I help?',
        })),
      })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Analyze flask')
    await user.click(screen.getByRole('button', { name: /send/i }))

    await screen.findByText('Tool Approval Required')
    await user.click(screen.getByTestId('deny-btn'))

    expect(await screen.findByText('Tool was denied. How else can I help?')).toBeInTheDocument()
  })

  it('should handle multi-step approval (approve, then another tool_pending, then approve again)', async () => {
    global.fetch = vi.fn()
      // 1: POST /api/chat → tool_pending (read_github_repo)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          status: 'tool_pending',
          thread_id: 'thread-abc',
          pending_tools: [{
            tool_name: 'read_github_repo',
            tool_label: 'Read GitHub Repository',
            args: {},
            tool_call_id: 'call_1',
          }],
          completed_steps: [],
          assistant_message: '',
          input_tokens: 0,
          output_tokens: 0,
        }),
      })
      // 2: POST /api/chat/approve → tool_pending (create_project)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          status: 'tool_pending',
          thread_id: 'thread-abc',
          pending_tools: [{
            tool_name: 'create_project',
            tool_label: 'Create Project',
            args: { name: 'Flask' },
            tool_call_id: 'call_2',
          }],
          completed_steps: [{
            tool_name: 'read_github_repo',
            tool_label: 'Read GitHub Repository',
            args: {},
            summary: 'Fetched repo',
            detail: {},
            duration_ms: 50,
          }],
          assistant_message: '',
          input_tokens: 5,
          output_tokens: 3,
        }),
      })
      // 3: POST /api/chat/approve → done
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(doneResponse({
          assistant_message: 'Project created!',
          completed_steps: [
            { tool_name: 'read_github_repo', tool_label: 'Read GitHub Repository', args: {}, summary: 'Fetched repo', detail: {}, duration_ms: 50 },
            { tool_name: 'create_project', tool_label: 'Create Project', args: { name: 'Flask' }, summary: 'Created Flask', detail: {}, duration_ms: 30 },
          ],
        })),
      })

    const user = userEvent.setup()
    render(<ChatPanel isOpen={true} onToggle={mockOnToggle} />)

    await user.type(screen.getByPlaceholderText(/type a message/i), 'Analyze flask')
    await user.click(screen.getByRole('button', { name: /send/i }))

    // Step 1: read_github_repo pending
    expect(await screen.findByText('Read GitHub Repository')).toBeInTheDocument()
    await user.click(screen.getByTestId('approve-btn'))

    // Step 2: create_project pending (Read GitHub Repository now completed)
    expect(await screen.findByText('Create Project')).toBeInTheDocument()
    await user.click(screen.getByTestId('approve-btn'))

    // Final: done
    expect(await screen.findByText('Project created!')).toBeInTheDocument()
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

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ToolApprovalCard from './ToolApprovalCard'
import type { PendingTool } from '../types'

const singleTool: PendingTool[] = [
  {
    tool_name: 'read_github_repo',
    tool_label: 'Read GitHub Repository',
    args: { github_url: 'pallets/flask' },
    tool_call_id: 'call_1',
  },
]

const multipleTools: PendingTool[] = [
  {
    tool_name: 'read_github_repo',
    tool_label: 'Read GitHub Repository',
    args: { github_url: 'pallets/flask' },
    tool_call_id: 'call_1',
  },
  {
    tool_name: 'read_repo_file',
    tool_label: 'Read Repository File',
    args: { owner: 'pallets', repo: 'flask', path: 'app.py' },
    tool_call_id: 'call_2',
  },
]

describe('ToolApprovalCard', () => {
  it('should render tool name and label', () => {
    render(<ToolApprovalCard tools={singleTool} onApprove={vi.fn()} onDeny={vi.fn()} />)
    expect(screen.getByText('Read GitHub Repository')).toBeInTheDocument()
    expect(screen.getByText('(read_github_repo)')).toBeInTheDocument()
  })

  it('should render approve and deny buttons', () => {
    render(<ToolApprovalCard tools={singleTool} onApprove={vi.fn()} onDeny={vi.fn()} />)
    expect(screen.getByTestId('approve-btn')).toHaveTextContent('Approve')
    expect(screen.getByTestId('deny-btn')).toHaveTextContent('Deny')
  })

  it('should render "Tool Approval Required" header', () => {
    render(<ToolApprovalCard tools={singleTool} onApprove={vi.fn()} onDeny={vi.fn()} />)
    expect(screen.getByText('Tool Approval Required')).toBeInTheDocument()
  })

  it('should call onApprove when approve button is clicked', async () => {
    const onApprove = vi.fn()
    const user = userEvent.setup()
    render(<ToolApprovalCard tools={singleTool} onApprove={onApprove} onDeny={vi.fn()} />)

    await user.click(screen.getByTestId('approve-btn'))
    expect(onApprove).toHaveBeenCalledOnce()
  })

  it('should call onDeny when deny button is clicked', async () => {
    const onDeny = vi.fn()
    const user = userEvent.setup()
    render(<ToolApprovalCard tools={singleTool} onApprove={vi.fn()} onDeny={onDeny} />)

    await user.click(screen.getByTestId('deny-btn'))
    expect(onDeny).toHaveBeenCalledOnce()
  })

  it('should show "Running..." and disable buttons after approve', async () => {
    const user = userEvent.setup()
    render(<ToolApprovalCard tools={singleTool} onApprove={vi.fn()} onDeny={vi.fn()} />)

    await user.click(screen.getByTestId('approve-btn'))
    expect(screen.getByTestId('approve-btn')).toHaveTextContent('Running...')
    expect(screen.getByTestId('approve-btn')).toBeDisabled()
    expect(screen.getByTestId('deny-btn')).toBeDisabled()
  })

  it('should render multiple tools', () => {
    render(<ToolApprovalCard tools={multipleTools} onApprove={vi.fn()} onDeny={vi.fn()} />)
    expect(screen.getByText('Read GitHub Repository')).toBeInTheDocument()
    expect(screen.getByText('Read Repository File')).toBeInTheDocument()
  })

  it('should show args when tool is expanded', async () => {
    const user = userEvent.setup()
    render(<ToolApprovalCard tools={singleTool} onApprove={vi.fn()} onDeny={vi.fn()} />)

    // Click to expand
    await user.click(screen.getByText('Read GitHub Repository'))
    expect(screen.getByText(/"pallets\/flask"/)).toBeInTheDocument()
  })
})

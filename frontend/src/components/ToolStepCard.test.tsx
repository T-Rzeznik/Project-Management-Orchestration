import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ToolStepCard from './ToolStepCard'
import type { ToolStep } from '../types'

const step: ToolStep = {
  tool_name: 'read_github_repo',
  tool_label: 'Read GitHub Repository',
  args: { github_url: 'pallets/flask' },
  summary: 'Fetched pallets/flask',
  detail: { owner: 'pallets', stars: 65000 },
  duration_ms: 142,
}

describe('ToolStepCard', () => {
  it('should render the tool label', () => {
    render(<ToolStepCard step={step} />)
    expect(screen.getByText('Read GitHub Repository')).toBeInTheDocument()
  })

  it('should render the summary', () => {
    render(<ToolStepCard step={step} />)
    expect(screen.getByText('Fetched pallets/flask')).toBeInTheDocument()
  })

  it('should be collapsed by default', () => {
    render(<ToolStepCard step={step} />)
    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-expanded', 'false')
  })

  it('should expand on click and show args and detail', async () => {
    const user = userEvent.setup()
    render(<ToolStepCard step={step} />)

    await user.click(screen.getByRole('button'))
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Args:')).toBeInTheDocument()
    expect(screen.getByText('Result:')).toBeInTheDocument()
    expect(screen.getByText(/65000/)).toBeInTheDocument()
  })

  it('should collapse again on second click', async () => {
    const user = userEvent.setup()
    render(<ToolStepCard step={step} />)

    await user.click(screen.getByRole('button'))
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')

    await user.click(screen.getByRole('button'))
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false')
  })

  it('should show duration', () => {
    render(<ToolStepCard step={step} />)
    expect(screen.getByText('142ms')).toBeInTheDocument()
  })

  it('should handle unknown tool with fallback label', () => {
    const unknownStep: ToolStep = {
      ...step,
      tool_name: 'some_tool',
      tool_label: 'Some Tool',
      summary: 'Completed',
    }
    render(<ToolStepCard step={unknownStep} />)
    expect(screen.getByText('Some Tool')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
  })
})

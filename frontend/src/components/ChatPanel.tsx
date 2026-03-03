import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { sendChatMessage, approveToolCall, denyToolCall } from '../api'
import type { ChatMessage, PendingTool, ToolStep, Project } from '../types'
import ToolStepCard from './ToolStepCard'
import ToolApprovalCard from './ToolApprovalCard'

interface ChatPanelProps {
  isOpen: boolean
  onToggle: () => void
  onProjectCreated?: (project: Project) => void
}

export default function ChatPanel({ isOpen, onToggle, onProjectCreated }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step-by-step state
  const [pendingTools, setPendingTools] = useState<PendingTool[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const [approvedSteps, setApprovedSteps] = useState<ToolStep[]>([])

  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, loading, pendingTools])

  if (!isOpen) return null

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: ChatMessage = { role: 'user', content: text }
    const updated = [...messages, userMsg]
    setMessages(updated)
    setInput('')
    setError(null)
    setLoading(true)
    setApprovedSteps([])
    setPendingTools([])
    setThreadId(null)

    try {
      const res = await sendChatMessage(updated)
      setThreadId(res.thread_id)

      if (res.status === 'tool_pending') {
        setPendingTools(res.pending_tools)
        setApprovedSteps(res.completed_steps)
        setLoading(false)
      } else {
        // Done — no tools needed
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: res.assistant_message,
            toolSteps: res.completed_steps,
            agentName: res.agent_name,
            modelName: res.model_name,
            inputTokens: res.input_tokens,
            outputTokens: res.output_tokens,
          },
        ])
        setPendingTools([])
        setLoading(false)
        if (res.project_created && onProjectCreated) {
          onProjectCreated(res.project_created)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!threadId) return
    setLoading(true)
    setPendingTools([])

    try {
      const res = await approveToolCall(threadId)

      if (res.status === 'tool_pending') {
        setApprovedSteps(res.completed_steps)
        setPendingTools(res.pending_tools)
        setLoading(false)
      } else {
        // Done
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: res.assistant_message,
            toolSteps: res.completed_steps,
            agentName: res.agent_name,
            modelName: res.model_name,
            inputTokens: res.input_tokens,
            outputTokens: res.output_tokens,
          },
        ])
        setPendingTools([])
        setApprovedSteps([])
        setThreadId(null)
        setLoading(false)
        if (res.project_created && onProjectCreated) {
          onProjectCreated(res.project_created)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approve failed')
      setLoading(false)
    }
  }

  const handleDeny = async () => {
    if (!threadId) return
    setLoading(true)
    setPendingTools([])

    try {
      const res = await denyToolCall(threadId)

      if (res.status === 'tool_pending') {
        setApprovedSteps(res.completed_steps)
        setPendingTools(res.pending_tools)
        setLoading(false)
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: res.assistant_message,
            toolSteps: res.completed_steps,
            agentName: res.agent_name,
            modelName: res.model_name,
            inputTokens: res.input_tokens,
            outputTokens: res.output_tokens,
          },
        ])
        setPendingTools([])
        setApprovedSteps([])
        setThreadId(null)
        setLoading(false)
        if (res.project_created && onProjectCreated) {
          onProjectCreated(res.project_created)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deny failed')
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="fixed top-0 right-0 h-full w-96 bg-gray-900 border-l border-gray-800 flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <h2 className="text-white font-semibold text-sm">AI Chat</h2>
        <button
          onClick={onToggle}
          aria-label="Close"
          className="text-gray-400 hover:text-white text-lg leading-none"
        >
          &times;
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role === 'assistant' && msg.toolSteps && msg.toolSteps.length > 0 && (
              <div className="mr-8 mb-1">
                {msg.toolSteps.map((step, j) => (
                  <ToolStepCard key={j} step={step} />
                ))}
              </div>
            )}
            <div
              className={`px-3 py-2 rounded-lg text-sm ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white ml-8 whitespace-pre-wrap'
                  : 'bg-gray-800 text-gray-100 mr-8 prose prose-invert prose-sm max-w-none'
              }`}
            >
              {msg.role === 'assistant'
                ? <ReactMarkdown>{msg.content}</ReactMarkdown>
                : msg.content}
            </div>
            {msg.role === 'assistant' && (msg.agentName || msg.inputTokens !== undefined) && (
              <div data-testid="message-metadata" className="flex items-center gap-2 mt-1 mr-8 text-[11px] text-gray-500">
                {msg.agentName && <span>{msg.agentName}</span>}
                {msg.modelName && <span className="text-gray-600">&middot; {msg.modelName}</span>}
                {msg.inputTokens !== undefined && (
                  <span data-testid="token-counts" className="ml-auto">{msg.inputTokens}&uarr; {msg.outputTokens}&darr;</span>
                )}
              </div>
            )}
          </div>
        ))}

        {/* In-progress tool steps (already approved) */}
        {approvedSteps.length > 0 && (
          <div className="mr-8 mb-1">
            {approvedSteps.map((step, j) => (
              <ToolStepCard key={j} step={step} />
            ))}
          </div>
        )}

        {/* Pending tool approval */}
        {pendingTools.length > 0 && (
          <ToolApprovalCard
            tools={pendingTools}
            onApprove={handleApprove}
            onDeny={handleDeny}
          />
        )}

        {loading && (
          <div className="bg-gray-800 text-gray-400 px-3 py-2 rounded-lg text-sm mr-8">
            Thinking...
          </div>
        )}
        {error && (
          <div className="text-red-400 text-sm px-3 py-1">{error}</div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 p-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          disabled={pendingTools.length > 0}
          className="flex-1 bg-gray-800 text-white text-sm rounded-lg px-3 py-2 border border-gray-700 focus:outline-none focus:border-indigo-500 disabled:opacity-40"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading || pendingTools.length > 0}
          aria-label="Send"
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
    </div>
  )
}

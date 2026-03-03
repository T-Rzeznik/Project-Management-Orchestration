import { useState } from 'react'
import type { PendingTool } from '../types'

interface ToolApprovalCardProps {
  tools: PendingTool[]
  onApprove: () => void
  onDeny: () => void
}

export default function ToolApprovalCard({ tools, onApprove, onDeny }: ToolApprovalCardProps) {
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const handleApprove = () => {
    setLoading(true)
    onApprove()
  }

  const handleDeny = () => {
    setLoading(true)
    onDeny()
  }

  return (
    <div className="border border-amber-600/40 bg-amber-950/20 rounded-lg text-xs mb-2 mr-8">
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-amber-400 font-medium">Tool Approval Required</span>
        </div>

        {tools.map((tool) => (
          <div key={tool.tool_call_id} className="mb-1">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="flex items-center gap-1.5 text-left w-full hover:bg-amber-900/20 rounded px-1 py-0.5"
            >
              <span className={`transition-transform text-[10px] ${expanded ? 'rotate-90' : ''}`}>&#9654;</span>
              <span className="text-indigo-400 font-medium">{tool.tool_label}</span>
              <span className="text-gray-500 text-[10px]">({tool.tool_name})</span>
            </button>
            {expanded && (
              <pre className="bg-gray-900 rounded p-1.5 mt-0.5 ml-4 overflow-auto max-h-32 text-gray-300 text-[11px]">
                {JSON.stringify(tool.args, null, 2)}
              </pre>
            )}
          </div>
        ))}

        <div className="flex gap-2 mt-2">
          <button
            onClick={handleApprove}
            disabled={loading}
            data-testid="approve-btn"
            className="bg-emerald-600 text-white px-3 py-1 rounded text-xs font-medium hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? 'Running...' : 'Approve'}
          </button>
          <button
            onClick={handleDeny}
            disabled={loading}
            data-testid="deny-btn"
            className="bg-red-700 text-white px-3 py-1 rounded text-xs font-medium hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Deny
          </button>
        </div>
      </div>
    </div>
  )
}

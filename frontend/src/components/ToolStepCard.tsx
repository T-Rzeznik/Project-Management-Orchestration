import { useState } from 'react'
import type { ToolStep } from '../types'

interface ToolStepCardProps {
  step: ToolStep
}

export default function ToolStepCard({ step }: ToolStepCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-gray-700 rounded-lg text-xs mb-1">
      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-gray-800/50"
      >
        <span className={`transition-transform ${expanded ? 'rotate-90' : ''}`}>
          &#9654;
        </span>
        <span className="text-indigo-400 font-medium">{step.tool_label}</span>
        <span className="text-gray-400 truncate flex-1">{step.summary}</span>
        <span className="text-gray-500 shrink-0">{step.duration_ms}ms</span>
      </button>

      {expanded && (
        <div className="px-3 pb-2 space-y-1">
          <div>
            <span className="text-gray-500">Args:</span>
            <pre className="bg-gray-900 rounded p-1.5 mt-0.5 overflow-auto max-h-48 text-gray-300">
              {JSON.stringify(step.args, null, 2)}
            </pre>
          </div>
          <div>
            <span className="text-gray-500">Result:</span>
            <pre className="bg-gray-900 rounded p-1.5 mt-0.5 overflow-auto max-h-48 text-gray-300">
              {JSON.stringify(step.detail, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

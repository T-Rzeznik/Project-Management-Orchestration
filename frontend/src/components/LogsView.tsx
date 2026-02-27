import { useEffect, useState, useCallback } from 'react'
import { fetchLogs } from '../api'
import type { AuditEvent, LogSession } from '../api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(isoString: string): string {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

function timeOnly(isoString: string): string {
  try {
    return new Date(isoString).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return isoString
  }
}

// ---------------------------------------------------------------------------
// Event type → chip colour
// ---------------------------------------------------------------------------

interface ChipStyle {
  bg: string
  text: string
  border: string
}

function chipStyleForEventType(eventType: string): ChipStyle {
  switch (eventType) {
    case 'SESSION_START':
    case 'SESSION_END':
      return { bg: 'bg-gray-700', text: 'text-gray-300', border: 'border-gray-600' }

    case 'AGENT_TASK_START':
      return { bg: 'bg-indigo-900/60', text: 'text-indigo-300', border: 'border-indigo-700' }

    case 'AGENT_TASK_END':
      return { bg: 'bg-green-900/60', text: 'text-green-300', border: 'border-green-700' }

    case 'TOOL_CALL_PROPOSED':
      return { bg: 'bg-yellow-900/60', text: 'text-yellow-300', border: 'border-yellow-700' }

    case 'VERIFICATION_DECISION':
      return { bg: 'bg-orange-900/60', text: 'text-orange-300', border: 'border-orange-700' }

    case 'TOOL_EXECUTED':
      return { bg: 'bg-blue-900/60', text: 'text-blue-300', border: 'border-blue-700' }

    case 'TOOL_BLOCKED':
    case 'TOOL_ACCESS_DENIED':
      return { bg: 'bg-red-900/60', text: 'text-red-300', border: 'border-red-700' }

    case 'AGENT_HANDOFF':
      return { bg: 'bg-purple-900/60', text: 'text-purple-300', border: 'border-purple-700' }

    case 'MCP_CONNECT':
      return { bg: 'bg-teal-900/60', text: 'text-teal-300', border: 'border-teal-700' }

    case 'MCP_CONNECT_FAILED':
      return { bg: 'bg-red-900/60', text: 'text-red-300', border: 'border-red-700' }

    default:
      return { bg: 'bg-gray-800', text: 'text-gray-400', border: 'border-gray-700' }
  }
}

// ---------------------------------------------------------------------------
// Event detail text
// ---------------------------------------------------------------------------

function eventDetail(event: AuditEvent): string {
  switch (event.event_type) {
    case 'AGENT_TASK_END': {
      const parts: string[] = []
      if (event.turns_used != null) parts.push(`turns: ${event.turns_used}`)
      if (event.total_input_tokens != null || event.total_output_tokens != null) {
        const inp = event.total_input_tokens ?? 0
        const out = event.total_output_tokens ?? 0
        parts.push(`tokens: ${inp.toLocaleString()} in / ${out.toLocaleString()} out`)
      }
      return parts.join(', ')
    }

    case 'VERIFICATION_DECISION':
      return event.verification_choice ? `choice: ${event.verification_choice}` : ''

    case 'TOOL_EXECUTED':
    case 'TOOL_BLOCKED':
    case 'TOOL_ACCESS_DENIED':
    case 'TOOL_CALL_PROPOSED': {
      const parts: string[] = []
      if (event.tool_name) parts.push(event.tool_name)
      if (event.outcome) parts.push(event.outcome)
      return parts.join(' — ')
    }

    case 'AGENT_TASK_START':
      return event.task_summary ?? ''

    default:
      return event.result_summary ?? ''
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface EventRowProps {
  event: AuditEvent
}

function EventRow({ event }: EventRowProps) {
  const chip = chipStyleForEventType(event.event_type)
  const detail = eventDetail(event)

  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-gray-800 last:border-b-0">
      {/* Timestamp */}
      <span className="shrink-0 text-xs text-gray-500 font-mono w-20 pt-0.5">
        {timeOnly(event.timestamp_utc)}
      </span>

      {/* Event type chip */}
      <span
        className={`shrink-0 text-xs px-2 py-0.5 rounded-md border font-medium ${chip.bg} ${chip.text} ${chip.border}`}
      >
        {event.event_type}
      </span>

      {/* Agent name */}
      {event.agent_name && (
        <span className="shrink-0 text-xs text-gray-400 pt-0.5">{event.agent_name}</span>
      )}

      {/* Detail */}
      {detail && (
        <span className="text-xs text-gray-300 pt-0.5 truncate">{detail}</span>
      )}
    </div>
  )
}

interface SessionItemProps {
  session: LogSession
  selected: boolean
  onClick: () => void
}

function SessionItem({ session, selected, onClick }: SessionItemProps) {
  const hasTokens = session.total_input_tokens > 0 || session.total_output_tokens > 0

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 border-b border-gray-800 transition-colors ${
        selected
          ? 'bg-indigo-900/30 border-l-2 border-l-indigo-500'
          : 'hover:bg-gray-800/60 border-l-2 border-l-transparent'
      }`}
    >
      {/* Top row: relative time + event count */}
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-gray-400">{relativeTime(session.start_time)}</span>
        <span className="text-xs text-gray-500">{session.event_count} events</span>
      </div>

      {/* Agent badges */}
      {session.agent_names.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1.5">
          {session.agent_names.map((name) => (
            <span
              key={name}
              className="text-xs bg-gray-800 text-gray-300 border border-gray-700 px-1.5 py-0.5 rounded"
            >
              {name}
            </span>
          ))}
        </div>
      )}

      {/* Token counts */}
      {hasTokens && (
        <span className="text-xs text-gray-500">
          {'\u2191'}{session.total_input_tokens.toLocaleString()}{' '}
          {'\u2193'}{session.total_output_tokens.toLocaleString()}
        </span>
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function LogsView() {
  const [sessions, setSessions] = useState<LogSession[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchLogs()
      // Sort newest first by start_time
      const sorted = [...data].sort(
        (a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime(),
      )
      setSessions(sorted)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const selectedSession = sessions.find((s) => s.session_id === selectedId) ?? null

  // ---------------------------------------------------------------------------
  // Render states
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading logs...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4">
          {error}
        </div>
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center px-4">
        <div className="text-5xl mb-4">📋</div>
        <h2 className="text-xl font-semibold text-gray-300 mb-2">No agent runs yet</h2>
        <p className="text-gray-500">Analyze a GitHub repo to see logs here.</p>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Main layout
  // ---------------------------------------------------------------------------

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Logs</h1>
          <p className="text-gray-400 text-sm mt-1">Audit trail of all agent runs</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white font-medium px-4 py-2 rounded-lg border border-gray-700 transition-colors text-sm"
        >
          {/* Refresh icon (Unicode circular arrows) */}
          <span aria-hidden="true">&#8635;</span>
          Refresh
        </button>
      </div>

      {/* Two-panel layout */}
      <div className="flex gap-4 h-[calc(100vh-220px)] min-h-[400px]">
        {/* Left panel — session list */}
        <aside className="w-72 shrink-0 bg-gray-900 border border-gray-800 rounded-xl overflow-y-auto">
          <div className="px-4 py-3 border-b border-gray-800">
            <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">
              Sessions ({sessions.length})
            </span>
          </div>
          {sessions.map((session) => (
            <SessionItem
              key={session.session_id}
              session={session}
              selected={session.session_id === selectedId}
              onClick={() => setSelectedId(session.session_id)}
            />
          ))}
        </aside>

        {/* Right panel — event timeline */}
        <section className="flex-1 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden flex flex-col">
          {selectedSession == null ? (
            <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
              Select a session to view its event timeline
            </div>
          ) : (
            <>
              {/* Panel header */}
              <div className="px-5 py-3 border-b border-gray-800 shrink-0">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-semibold text-white">
                      {selectedSession.agent_names.join(', ') || 'Unknown agent'}
                    </span>
                    <span className="ml-3 text-xs text-gray-500 font-mono">
                      {selectedSession.session_id}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    {(selectedSession.total_input_tokens > 0 ||
                      selectedSession.total_output_tokens > 0) && (
                      <span>
                        {'\u2191'}{selectedSession.total_input_tokens.toLocaleString()}{' '}
                        {'\u2193'}{selectedSession.total_output_tokens.toLocaleString()} tokens
                      </span>
                    )}
                    <span>{selectedSession.event_count} events</span>
                  </div>
                </div>
              </div>

              {/* Event list */}
              <div className="flex-1 overflow-y-auto px-5 py-1">
                {selectedSession.events.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                    No events in this session
                  </div>
                ) : (
                  selectedSession.events.map((event) => (
                    <EventRow key={event.event_id} event={event} />
                  ))
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}

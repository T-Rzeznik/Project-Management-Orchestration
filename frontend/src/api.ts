import type { Project, CreateProjectData, Task } from './types'

const BASE = '/api'

export async function analyzeRepo(githubUrl: string): Promise<Project> {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ github_url: githubUrl }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Analysis failed')
  }
  return res.json()
}

export async function createProject(data: CreateProjectData): Promise<Project> {
  const res = await fetch(`${BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Failed to create project')
  }
  return res.json()
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${BASE}/projects`)
  if (!res.ok) throw new Error('Failed to load projects')
  return res.json()
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}`)
  if (!res.ok) throw new Error('Project not found')
  return res.json()
}

export async function updateProject(id: string, data: Partial<CreateProjectData> & { status?: string; tasks?: Task[] }): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Failed to update project')
  }
  return res.json()
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${BASE}/projects/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete project')
}

export interface AuditEvent {
  event_id: string
  timestamp_utc: string
  session_id: string
  event_type: string
  agent_name?: string
  model?: string
  tool_name?: string
  tool_input_scrubbed?: Record<string, unknown>
  outcome?: string
  result_summary?: string
  task_summary?: string
  turns_used?: number
  total_input_tokens?: number
  total_output_tokens?: number
  verification_choice?: string
  operator?: string
}

export interface LogSession {
  session_id: string
  file: string
  start_time: string
  operator?: string
  agent_names: string[]
  event_count: number
  total_input_tokens: number
  total_output_tokens: number
  events: AuditEvent[]
}

export async function fetchLogs(): Promise<LogSession[]> {
  const res = await fetch('/api/logs')
  if (!res.ok) throw new Error('Failed to load logs')
  return res.json()
}

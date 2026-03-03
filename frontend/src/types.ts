export interface Task {
  id: string
  title: string
  description: string
  priority: 'high' | 'medium' | 'low'
  status: 'todo' | 'in-progress' | 'done'
}

export interface Milestone {
  title: string
  description: string
}

export interface Project {
  id: string
  github_url?: string
  name: string
  description: string
  documentation?: string
  summary: string
  tech_stack: string[]
  stars: number
  language: string
  open_issues_count: number
  contributors: string[]
  tasks: Task[]
  milestones: Milestone[]
  status: string
  created_at: string
  updated_at: string
}

export interface CreateProjectData {
  name: string
  description?: string
  tech_stack?: string[]
  github_url?: string
  documentation?: string
}

export interface ToolStep {
  tool_name: string
  tool_label: string
  args: Record<string, unknown>
  summary: string
  detail: Record<string, unknown>
  duration_ms: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  toolSteps?: ToolStep[]
  agentName?: string
  modelName?: string
  inputTokens?: number
  outputTokens?: number
}

export interface ChatResponse {
  assistant_message: string
  input_tokens: number
  output_tokens: number
  project_created?: Project
  tool_steps?: ToolStep[]
  agent_name?: string
  model_name?: string
}

export interface PendingTool {
  tool_name: string
  tool_label: string
  args: Record<string, unknown>
  tool_call_id: string
}

export interface ChatStepResponse {
  status: 'tool_pending' | 'done'
  thread_id: string
  pending_tools: PendingTool[]
  completed_steps: ToolStep[]
  assistant_message: string
  input_tokens: number
  output_tokens: number
  project_created?: Project
  agent_name?: string
  model_name?: string
}

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

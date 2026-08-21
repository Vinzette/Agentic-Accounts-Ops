export type Status = 'Healthy' | 'At-Risk' | 'Stalled'

export interface Manager {
  id: number
  name: string
  region: string | null
  account_count: number
}

export interface AccountData {
  account_name: string
  industry?: string | null
  tier?: string | null
  arr?: string | null
  products_in_use?: string[]
  adoption?: string | null
  key_people?: string[]
  last_90_days?: string[]
  open_issues?: string | null
  renewal?: string | null
  nps?: string | null
}

export interface Account {
  id: number
  manager_id: number
  slug: string
  display_name: string
  data: AccountData
}

export interface UploadResult {
  account: AccountData
  truncated: boolean
  total_chars: number
  used_chars: number
}

export interface Briefing {
  reasoning: string
  status: Status
  snapshot: string
  why: string[]
  who_to_talk_to: string[]
  next_actions: string[]
  one_thing_to_watch: string
}

export interface Validation {
  passed: boolean
  errors: string[]
  warnings: string[]
}

/** One pipeline step, as it arrives over the stream. */
export interface NodeEvent {
  type: 'node'
  node: string
  status: 'running' | 'ok' | 'failed'
  detail?: string
}

export interface ResultEvent {
  type: 'result'
  run_id: number | null
  briefing: Briefing
  markdown: string
  generated_at: string | null
  missing_fields: string[]
  attempts: number
  max_attempts: number
  validation: Validation
}

export interface ErrorEvent {
  type: 'error'
  message: string
}

export type StreamEvent = NodeEvent | ResultEvent | ErrorEvent

export interface RunSummary {
  id: number
  account_display_name: string
  created_at: string
  input_source: string
  model: string
  prompt_version: string
  input_hash: string
  attempts: number
  validation_passed: boolean
  validation_errors: string[]
  validation_warnings: string[]
}

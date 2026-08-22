import type {
  Account,
  AccountData,
  Manager,
  Internals,
  Pipeline,
  PortfolioEvent,
  PromptDoc,
  RunDetail,
  RunSummary,
  StreamEvent,
  UploadResult,
} from '../types'

/**
 * Where the API lives.
 *
 * Empty in development and for a single-service deploy, so requests stay
 * relative and Vite's proxy handles them. Set to the backend's origin when the
 * frontend is hosted separately.
 */
const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

const url = (path: string) => `${API_BASE}${path}`

async function message(res: Response): Promise<string> {
  try {
    const body = await res.json()
    return body.detail ?? res.statusText
  } catch {
    return res.statusText
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(url(path))
  if (!res.ok) throw new Error(await message(res))
  return res.json()
}

export const getHealth = () => get<{ ok: boolean; model: string }>('/api/health')
export const getManagers = () => get<Manager[]>('/api/managers')
export const getAccounts = (managerId: number) =>
  get<Account[]>(`/api/accounts?manager_id=${managerId}`)
export async function createManager(name: string, region: string): Promise<Manager> {
  const res = await fetch(url('/api/managers'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, region }),
  })
  if (!res.ok) throw new Error(await message(res))
  return res.json()
}

export const getRuns = () => get<RunSummary[]>('/api/runs')
export const getRun = (id: number) => get<RunDetail>(`/api/runs/${id}`)
export const getPrompts = () => get<PromptDoc[]>('/api/prompts')
export const getInternals = () => get<Internals>('/api/internals')
export const getPipeline = () => get<Pipeline>('/api/pipeline')

/** A PDF, deck, spreadsheet or notes file to a structured draft. */
export async function uploadAccountFile(file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(url('/api/extract/file'), { method: 'POST', body: form })
  if (!res.ok) throw new Error(await message(res))
  return res.json()
}

/** Add the account to a manager's book, or update it if the name already exists. */
export async function saveAccount(managerId: number, data: AccountData): Promise<Account> {
  const res = await fetch(url('/api/accounts'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ manager_id: managerId, data }),
  })
  if (!res.ok) throw new Error(await message(res))
  return res.json()
}

/** Messy notes to a structured draft, for the caller to review before briefing. */
export async function extractAccount(notes: string): Promise<AccountData> {
  const res = await fetch(url('/api/extract'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  })
  if (!res.ok) throw new Error(await message(res))
  return res.json()
}

/**
 * POST a body and read the SSE response, calling `onEvent` per frame.
 *
 * EventSource only speaks GET, so this reads the stream off fetch directly.
 */
async function stream<T>(path: string, body: unknown, onEvent: (event: T) => void): Promise<void> {
  const res = await fetch(url(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await message(res))
  if (!res.body) throw new Error('The server returned no stream.')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    // SSE frames are separated by a blank line; the tail may be a partial frame.
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      const line = frame.trim()
      if (line.startsWith('data:')) onEvent(JSON.parse(line.slice(5)))
    }
  }
}

/** Stream a briefing, one event per pipeline step. */
export const streamBriefing = (
  body: { account_data: AccountData; account_id?: number | null; input_source?: string },
  onEvent: (event: StreamEvent) => void,
) => stream<StreamEvent>('/api/briefings/stream', body, onEvent)

/** Stream a portfolio brief: one event per account as the fan-out lands, then the result. */
export const streamPortfolio = (managerId: number, onEvent: (event: PortfolioEvent) => void) =>
  stream<PortfolioEvent>('/api/portfolio/stream', { manager_id: managerId }, onEvent)

import { useEffect, useState } from 'react'
import { getRun, getRuns } from '../lib/api'
import type { RunDetail, RunSummary } from '../types'
import { StatusBadge } from './StatusBadge'

const SOURCE_LABELS: Record<string, string> = {
  file: 'CLI',
  form: 'Form',
  paste: 'Pasted notes',
  upload: 'Uploaded file',
  portfolio: 'Portfolio run',
}

function when(iso: string): string {
  const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString()
}

function Detail({ run }: { run: RunDetail }) {
  const briefing = run.parsed_briefing
  return (
    <div className="space-y-4 border-t border-slate-200 bg-slate-50 px-3 py-3">
      <div className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
        {[
          ['Model', run.model],
          ['Prompt version', run.prompt_version],
          ['Input hash', run.input_hash],
          ['Attempts', String(run.attempts)],
        ].map(([label, value]) => (
          <p key={label} className="flex gap-2">
            <span className="text-slate-500">{label}</span>
            <span className="font-mono text-slate-700">{value}</span>
          </p>
        ))}
      </div>

      {run.validation_errors.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
          <p className="text-xs font-semibold text-amber-800">Unverified signals</p>
          <ul className="mt-1 space-y-1 text-xs text-amber-700">
            {run.validation_errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {briefing && (
        <div>
          <p className="mb-1 text-xs font-semibold tracking-wider text-slate-500 uppercase">
            What it said
          </p>
          <p className="mb-2 text-sm text-slate-700">{briefing.snapshot}</p>
          <ul className="space-y-1">
            {briefing.why.map((w, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-700">
                <span className="text-slate-300">•</span>
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      <details>
        <summary className="cursor-pointer text-xs font-medium text-slate-600 hover:text-slate-900">
          Raw model response
        </summary>
        <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-white p-2 font-mono text-[11px] whitespace-pre-wrap text-slate-600">
          {run.raw_response || '(empty)'}
        </pre>
      </details>

      <details>
        <summary className="cursor-pointer text-xs font-medium text-slate-600 hover:text-slate-900">
          The data it ran on
        </summary>
        <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-white p-2 font-mono text-[11px] whitespace-pre-wrap text-slate-600">
          {JSON.stringify(run.input_data, null, 2)}
        </pre>
      </details>
    </div>
  )
}

export function RunLog() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [open, setOpen] = useState<number | null>(null)
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getRuns()
      .then(setRuns)
      .catch((e) => setError(e.message))
  }, [])

  const toggle = async (id: number) => {
    if (open === id) {
      setOpen(null)
      return
    }
    setOpen(id)
    setDetail(null)
    try {
      setDetail(await getRun(id))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 lg:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Run log</h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Every briefing ever generated, with the data it ran on and what the model actually
            returned. Open one to see whether it can be reproduced.
          </p>
        </div>
        <button
          onClick={() => getRuns().then(setRuns).catch((e) => setError(e.message))}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {runs.length === 0 && !error && (
        <p className="mt-6 text-sm text-slate-500">Nothing here yet. Generate a briefing first.</p>
      )}

      <div className="mt-5 space-y-2">
        {runs.map((run) => (
          <div key={run.id} className="overflow-hidden rounded-lg border border-slate-200">
            <button
              onClick={() => toggle(run.id)}
              aria-expanded={open === run.id}
              className={`flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5 text-left transition ${
                open === run.id ? 'bg-slate-50' : 'hover:bg-slate-50'
              }`}
            >
              <span className="font-mono text-xs text-slate-400">#{run.id}</span>
              <span className="text-sm font-medium text-slate-800">
                {run.account_display_name}
              </span>
              {run.validation_passed ? (
                <span className="text-xs text-emerald-600">grounded</span>
              ) : (
                <span className="text-xs text-amber-600">unverified</span>
              )}
              {run.attempts > 1 && (
                <span className="text-xs text-slate-500">regenerated {run.attempts - 1}×</span>
              )}
              <span className="ml-auto flex items-center gap-3 text-xs text-slate-400">
                <span>{SOURCE_LABELS[run.input_source] ?? run.input_source}</span>
                <span>{when(run.created_at)}</span>
              </span>
            </button>
            {open === run.id &&
              (detail && detail.id === run.id ? (
                <Detail run={detail} />
              ) : (
                <p className="border-t border-slate-200 px-3 py-3 text-xs text-slate-500">
                  Loading…
                </p>
              ))}
          </div>
        ))}
      </div>
    </div>
  )
}

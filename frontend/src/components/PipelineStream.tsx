import { useEffect, useState } from 'react'
import type { NodeEvent } from '../types'

const LABELS: Record<string, string> = {
  load_data: 'Reading the account data',
  generate_briefing: 'Writing the briefing',
  validate_output: 'Checking every citation against the data',
  persist_run: 'Recording the run',
  save_briefing: 'Done',
}

function Icon({ status }: { status: NodeEvent['status'] }) {
  if (status === 'running') {
    // `block` matters: width and height are ignored on an inline element, which
    // collapses the spinner to a dot.
    return (
      <span className="block size-4 animate-spin rounded-full border-2 border-slate-200 border-t-slate-700" />
    )
  }
  const failed = status === 'failed'
  return (
    <span
      className={`flex size-4 items-center justify-center text-xs ${
        failed ? 'text-amber-600' : 'text-emerald-600'
      }`}
    >
      {failed ? '✗' : '✓'}
    </span>
  )
}

/** Seconds since `key` last changed. Reassures during the long model call. */
function useElapsed(key: number | null) {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    if (key === null) return
    setSeconds(0)
    const started = Date.now()
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500)
    return () => clearInterval(id)
  }, [key])

  return seconds
}

export function PipelineStream({ steps }: { steps: NodeEvent[] }) {
  const runningAt = steps.findIndex((s) => s.status === 'running')
  const elapsed = useElapsed(runningAt === -1 ? null : runningAt)

  return (
    <ol className="space-y-3">
      {steps.map((step, i) => {
        const running = step.status === 'running'
        return (
          <li key={i} className="animate-rise flex gap-3">
            <div className="mt-0.5">
              <Icon status={step.status} />
            </div>
            <div className="min-w-0 flex-1">
              <p
                className={`flex items-baseline justify-between gap-3 text-sm ${
                  step.status === 'failed'
                    ? 'text-amber-700'
                    : running
                      ? 'animate-pulse text-slate-900'
                      : 'text-slate-700'
                }`}
              >
                <span>{LABELS[step.node] ?? step.node}</span>
                {running && elapsed > 0 && (
                  <span className="shrink-0 text-xs text-slate-400 tabular-nums">{elapsed}s</span>
                )}
              </p>
              {step.detail && <p className="mt-0.5 text-xs text-slate-500">{step.detail}</p>}
              <p className="mt-0.5 font-mono text-[10px] text-slate-400">{step.node}</p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

const SKELETON_ROWS = [
  ['w-3/4', 'w-5/6'],
  ['w-2/3', 'w-4/5', 'w-1/2'],
  ['w-5/6', 'w-3/5'],
]

/** The shape of what's coming, so the pane isn't empty during the model call. */
export function BriefingSkeleton() {
  return (
    <div className="mt-8 space-y-6 border-t border-slate-100 pt-6" aria-hidden>
      <div className="h-7 w-32 animate-pulse rounded-full bg-slate-100" />
      {SKELETON_ROWS.map((row, i) => (
        <div key={i} className="space-y-2">
          <div className="h-2.5 w-20 animate-pulse rounded bg-slate-100" />
          {row.map((width, j) => (
            <div
              key={j}
              className={`h-3 ${width} animate-pulse rounded bg-slate-100`}
              style={{ animationDelay: `${(i * 3 + j) * 90}ms` }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

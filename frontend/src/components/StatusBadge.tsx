import type { Status } from '../types'

const STYLES: Record<Status, string> = {
  Healthy: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  'At-Risk': 'bg-amber-50 text-amber-800 ring-amber-600/20',
  Stalled: 'bg-rose-50 text-rose-700 ring-rose-600/20',
}

const DOTS: Record<Status, string> = {
  Healthy: 'bg-emerald-500',
  'At-Risk': 'bg-amber-500',
  Stalled: 'bg-rose-500',
}

/**
 * `provisional` drains the colour out.
 *
 * A confident green badge over an account with almost nothing on record is the
 * one output here that could actively mislead — the caveat lives in reasoning
 * nobody opens, while the badge is the first thing read.
 */
export function StatusBadge({
  status,
  provisional = false,
}: {
  status: Status
  provisional?: boolean
}) {
  const style = provisional
    ? 'bg-slate-100 text-slate-600 ring-slate-400/30'
    : `${STYLES[status]}`
  const dot = provisional ? 'bg-slate-400' : DOTS[status]

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset ${style}`}
      title={provisional ? 'Provisional — too little on record to judge' : undefined}
    >
      <span className={`size-2 rounded-full ${dot}`} />
      {status}
      {provisional && <span className="font-normal text-slate-500">· provisional</span>}
    </span>
  )
}

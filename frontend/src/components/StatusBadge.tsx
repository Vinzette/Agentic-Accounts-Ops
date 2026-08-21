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

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset ${STYLES[status]}`}
    >
      <span className={`size-2 rounded-full ${DOTS[status]}`} />
      {status}
    </span>
  )
}

import { useState } from 'react'
import { createManager } from '../lib/api'
import type { Manager } from '../types'

const FIELD =
  'rounded-md border border-slate-300 px-2 py-1.5 text-sm placeholder:text-slate-400 ' +
  'focus:border-slate-500 focus:ring-1 focus:ring-slate-500 focus:outline-none'

export function ManagerPicker({
  managers,
  managerId,
  onSelect,
  onAdded,
}: {
  managers: Manager[]
  managerId: number | null
  onSelect: (id: number) => void
  onAdded: (manager: Manager) => void
}) {
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [region, setRegion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setAdding(false)
    setName('')
    setRegion('')
    setError(null)
  }

  const add = async () => {
    setBusy(true)
    setError(null)
    try {
      onAdded(await createManager(name.trim(), region.trim()))
      reset()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (adding) {
    return (
      <div className="flex flex-wrap items-start gap-2">
        <div>
          <input
            autoFocus
            className={FIELD}
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && name.trim() && add()}
          />
          {error && <p className="mt-1 max-w-56 text-xs text-rose-600">{error}</p>}
        </div>
        <input
          className={FIELD}
          placeholder="Region (optional)"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && name.trim() && add()}
        />
        <button
          onClick={add}
          disabled={busy || !name.trim()}
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white hover:bg-slate-800 disabled:bg-slate-300"
        >
          {busy ? 'Adding…' : 'Add'}
        </button>
        <button onClick={reset} className="px-2 py-1.5 text-sm text-slate-500 hover:text-slate-700">
          Cancel
        </button>
      </div>
    )
  }

  const selected = managers.find((m) => m.id === managerId)

  return (
    <div className="flex items-center gap-2">
      <div className="text-right">
        <select
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm"
          value={managerId ?? ''}
          onChange={(e) => onSelect(Number(e.target.value))}
        >
          {managers.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name} · {m.account_count} account{m.account_count === 1 ? '' : 's'}
            </option>
          ))}
        </select>
        {selected?.region && (
          <p className="mt-0.5 pr-1 text-xs text-slate-500">{selected.region}</p>
        )}
      </div>
      <button
        onClick={() => setAdding(true)}
        title="Add an account manager"
        className="rounded-md border border-slate-300 px-2.5 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
      >
        +
      </button>
    </div>
  )
}

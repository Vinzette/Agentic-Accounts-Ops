import type { AccountData } from '../types'

/** Mirrors AccountData in models.py. List fields take one item per line. */
const FIELDS = [
  { key: 'account_name', label: 'Account name', kind: 'text' },
  { key: 'industry', label: 'Industry', kind: 'text' },
  { key: 'tier', label: 'Tier', kind: 'text' },
  { key: 'arr', label: 'ARR', kind: 'text' },
  { key: 'adoption', label: 'Adoption', kind: 'text' },
  { key: 'products_in_use', label: 'Products in use', kind: 'list' },
  { key: 'key_people', label: 'Key people', kind: 'list' },
  { key: 'last_90_days', label: 'Last 90 days', kind: 'list' },
  { key: 'open_issues', label: 'Open issues', kind: 'text' },
  { key: 'renewal', label: 'Renewal / decision point', kind: 'text' },
  { key: 'nps', label: 'Sentiment / NPS', kind: 'text' },
] as const

const INPUT =
  'w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-xs ' +
  'placeholder:text-slate-400 focus:border-slate-500 focus:ring-1 focus:ring-slate-500 focus:outline-none'

export function AccountForm({
  value,
  onChange,
}: {
  value: AccountData
  onChange: (next: AccountData) => void
}) {
  const set = (key: string, next: string | string[]) => onChange({ ...value, [key]: next })

  return (
    <div className="space-y-4">
      {FIELDS.map((field) => {
        const raw = value[field.key as keyof AccountData]
        return (
          <div key={field.key}>
            <label className="mb-1 block text-xs font-medium tracking-wide text-slate-600 uppercase">
              {field.label}
              {field.key === 'account_name' && <span className="ml-1 text-rose-500">*</span>}
            </label>
            {field.kind === 'list' ? (
              <textarea
                rows={3}
                className={INPUT}
                placeholder="One per line"
                value={Array.isArray(raw) ? raw.join('\n') : ''}
                onChange={(e) =>
                  set(
                    field.key,
                    e.target.value.split('\n').map((line) => line.trim()).filter(Boolean),
                  )
                }
              />
            ) : (
              <input
                className={INPUT}
                value={typeof raw === 'string' ? raw : ''}
                onChange={(e) => set(field.key, e.target.value)}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export const EMPTY_ACCOUNT: AccountData = {
  account_name: '',
  industry: '',
  tier: '',
  arr: '',
  adoption: '',
  products_in_use: [],
  key_people: [],
  last_90_days: [],
  open_issues: '',
  renewal: '',
  nps: '',
}

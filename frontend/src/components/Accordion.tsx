import { useState, type ReactNode } from 'react'

export function Accordion({
  title,
  subtitle,
  children,
  defaultOpen = false,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className={`flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition ${
          open ? 'bg-slate-50' : 'hover:bg-slate-50'
        }`}
      >
        <span className="text-sm font-medium text-slate-800">
          {title}
          {subtitle && <span className="ml-2 font-normal text-slate-400">{subtitle}</span>}
        </span>
        <span className="flex shrink-0 items-center gap-1.5 text-xs font-medium text-slate-500">
          {open ? 'Hide' : 'Show'}
          <span
            className={`flex size-5 items-center justify-center rounded-full border border-slate-300 bg-white transition-transform ${
              open ? 'rotate-180' : ''
            }`}
          >
            <svg viewBox="0 0 12 12" className="size-3" fill="none" stroke="currentColor">
              <path d="M3 4.5 6 7.5 9 4.5" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </span>
        </span>
      </button>
      {open && <div className="border-t border-slate-200 px-3 py-3">{children}</div>}
    </div>
  )
}

import { useState, type ReactNode } from 'react'

export function Accordion({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border-t border-slate-200">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between py-3 text-left hover:text-slate-900"
      >
        <span className="text-sm font-medium text-slate-700">
          {title}
          {subtitle && <span className="ml-2 font-normal text-slate-400">{subtitle}</span>}
        </span>
        <span className={`text-slate-400 transition-transform ${open ? 'rotate-90' : ''}`}>›</span>
      </button>
      {open && <div className="pb-4">{children}</div>}
    </div>
  )
}

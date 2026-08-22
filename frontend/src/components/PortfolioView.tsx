import { useEffect, useState } from 'react'
import { streamPortfolio } from '../lib/api'
import { useElapsed } from '../lib/useElapsed'
import type { Manager, PortfolioAccountEvent, PortfolioResultEvent } from '../types'
import { Accordion } from './Accordion'
import { StatusBadge } from './StatusBadge'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold tracking-wider text-slate-500 uppercase">
        {title}
      </h3>
      {children}
    </section>
  )
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-slate-700">
          <span className="text-slate-300">•</span>
          {item}
        </li>
      ))}
    </ul>
  )
}

export function PortfolioView({ manager }: { manager: Manager | undefined }) {
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState<PortfolioAccountEvent[]>([])
  const [result, setResult] = useState<PortfolioResultEvent | null>(null)
  const [error, setError] = useState<string | null>(null)

  // A different manager means a different book; nothing here still applies.
  useEffect(() => {
    setProgress([])
    setResult(null)
    setError(null)
  }, [manager?.id])

  const generate = async () => {
    if (!manager) return
    setRunning(true)
    setError(null)
    setProgress([])
    setResult(null)

    try {
      await streamPortfolio(manager.id, (event) => {
        if (event.type === 'account') setProgress((prev) => [...prev, event])
        else if (event.type === 'result') setResult(event)
        else setError(event.message)
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  const total = progress[0]?.total ?? manager?.account_count ?? 0
  const brief = result?.portfolio_brief
  const elapsed = useElapsed(running ? (manager?.id ?? 0) : null)

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 lg:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            {manager?.name ?? 'No manager selected'}
            {manager?.region && (
              <span className="ml-2 font-normal text-slate-400">{manager.region}</span>
            )}
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            One brief across all {manager?.account_count ?? 0} accounts — the view no single
            briefing can produce.
          </p>
        </div>
        <button
          onClick={generate}
          disabled={running || !manager || manager.account_count === 0}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {running ? 'Working…' : 'Generate portfolio brief'}
        </button>
      </div>

      {manager?.account_count === 0 && (
        <p className="mt-6 text-sm text-slate-500">
          This manager has no accounts yet. Add one from the Briefing tab first.
        </p>
      )}

      {error && (
        <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      {progress.length > 0 && !result && (
        <div className="mt-6">
          <p className="mb-3 flex items-baseline justify-between gap-3 text-xs text-slate-500">
            <span>
              Briefing each account in parallel — {progress.length} of {total} done
            </span>
            {elapsed > 0 && <span className="tabular-nums text-slate-400">{elapsed}s</span>}
          </p>
          <ul className="space-y-2">
            {progress.map((event, i) => (
              <li key={i} className="animate-rise flex items-center gap-3">
                <StatusBadge status={event.status} />
                <span className="text-sm text-slate-700">{event.account_name}</span>
              </li>
            ))}
          </ul>
          {progress.length === total && (
            <p className="mt-4 flex items-center gap-2 text-sm text-slate-500">
              <span className="block size-3.5 animate-spin rounded-full border-2 border-slate-200 border-t-slate-700" />
              Comparing the book…
            </p>
          )}
        </div>
      )}

      {running && progress.length === 0 && (
        <p className="mt-6 flex items-center gap-2 text-sm text-slate-500">
          <span className="block size-3.5 animate-spin rounded-full border-2 border-slate-200 border-t-slate-700" />
          Starting {total} briefing runs…
          {elapsed > 0 && <span className="tabular-nums text-slate-400">{elapsed}s</span>}
        </p>
      )}

      {brief && (
        <div className="mt-6 space-y-6 border-t border-slate-100 pt-6">
          <p className="text-base font-medium text-slate-900">{brief.headline}</p>

          <Section title="Priority order">
            <ol className="space-y-1.5">
              {brief.priority_order.map((item, i) => (
                <li key={i} className="flex gap-2 text-sm text-slate-700">
                  <span className="font-medium text-slate-400 tabular-nums">{i + 1}.</span>
                  {item}
                </li>
              ))}
            </ol>
          </Section>

          {brief.cross_account_patterns.length > 0 && (
            <Section title="Across the book">
              <Bullets items={brief.cross_account_patterns} />
            </Section>
          )}

          <Section title="Where your week goes">
            <ol className="space-y-1.5">
              {brief.where_your_week_goes.map((item, i) => (
                <li key={i} className="flex gap-2 text-sm text-slate-700">
                  <span className="font-medium text-slate-400 tabular-nums">{i + 1}.</span>
                  {item}
                </li>
              ))}
            </ol>
          </Section>

          <Section title="Portfolio risk">
            <p className="rounded-md border-l-2 border-slate-300 bg-slate-50 py-2 pl-3 text-sm text-slate-700">
              {brief.portfolio_risk}
            </p>
          </Section>

          <div className="space-y-2">
            <Accordion title="How it got there" subtitle="the model's reasoning">
              <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-600">
                {brief.reasoning}
              </p>
            </Accordion>
            <Accordion
              title="The briefings it read"
              subtitle={`${result.briefings.length} accounts`}
            >
              <div className="space-y-2">
                {result.briefings.map((b) => (
                  <Accordion
                    key={b.account_name}
                    title={b.account_name}
                    subtitle={`${b.status}${b.attempts > 1 ? ` · regenerated ${b.attempts - 1}×` : ''} · run #${b.run_id}`}
                  >
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={b.status} provisional={b.provisional} />
                        <span className="text-sm text-slate-600">{b.snapshot}</span>
                      </div>
                      <Section title="Why">
                        <Bullets items={b.why} />
                      </Section>
                      <Section title="Who to talk to">
                        <Bullets items={b.who_to_talk_to} />
                      </Section>
                      <Section title="Next actions">
                        <ol className="space-y-1.5">
                          {b.next_actions.map((item, i) => (
                            <li key={i} className="flex gap-2 text-sm text-slate-700">
                              <span className="font-medium text-slate-400 tabular-nums">
                                {i + 1}.
                              </span>
                              {item}
                            </li>
                          ))}
                        </ol>
                      </Section>
                      <Section title="One thing to watch">
                        <p className="rounded-md border-l-2 border-slate-300 bg-slate-50 py-2 pl-3 text-sm text-slate-700">
                          {b.one_thing_to_watch}
                        </p>
                      </Section>
                      <Accordion title="How it got there" subtitle="this account's reasoning">
                        <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-600">
                          {b.reasoning}
                        </p>
                      </Accordion>
                    </div>
                  </Accordion>
                ))}
              </div>
            </Accordion>
          </div>
        </div>
      )}
    </div>
  )
}

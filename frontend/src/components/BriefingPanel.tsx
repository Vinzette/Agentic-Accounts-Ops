import type { ResultEvent } from '../types'
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

export function BriefingPanel({ result }: { result: ResultEvent }) {
  const { briefing, validation, attempts, missing_fields } = result

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={briefing.status} provisional={result.provisional} />
        <span className="text-sm text-slate-600">{briefing.snapshot}</span>
      </div>

      {result.provisional && (
        <div className="rounded-md border border-slate-300 bg-slate-50 px-3 py-2.5">
          <p className="text-xs font-semibold text-slate-700">
            Provisional — not enough on record to judge this account
          </p>
          <p className="mt-1 text-xs text-slate-600">
            Nothing on file for {result.evidence_gaps.join(', ').replace(/_/g, ' ')}. Read the
            status as a placeholder and the actions below as discovery, not as an assessment.
          </p>
        </div>
      )}

      {attempts > 1 && (
        <p className="rounded-md bg-slate-100 px-3 py-2 text-xs text-slate-600">
          Regenerated {attempts - 1}× — the first draft cited figures that weren't in the data.
        </p>
      )}

      {!validation.passed && validation.errors.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
          <p className="text-xs font-semibold text-amber-800">Unverified signals</p>
          <ul className="mt-1 space-y-1 text-xs text-amber-700">
            {validation.errors.map((error, i) => (
              <li key={i}>{error}</li>
            ))}
          </ul>
        </div>
      )}

      {missing_fields.length > 0 && (
        <p className="text-xs text-slate-500">
          Built from partial data — no record of {missing_fields.join(', ').replace(/_/g, ' ')}.
        </p>
      )}

      <Section title="Why">
        <ul className="space-y-1.5">
          {briefing.why.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-700">
              <span className="text-slate-300">•</span>
              {item}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Who to talk to">
        <ul className="space-y-1.5">
          {briefing.who_to_talk_to.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-700">
              <span className="text-slate-300">•</span>
              {item}
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Next actions">
        <ol className="space-y-1.5">
          {briefing.next_actions.map((item, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-700">
              <span className="font-medium text-slate-400 tabular-nums">{i + 1}.</span>
              {item}
            </li>
          ))}
        </ol>
      </Section>

      <Section title="One thing to watch">
        <p className="rounded-md border-l-2 border-slate-300 bg-slate-50 py-2 pl-3 text-sm text-slate-700">
          {briefing.one_thing_to_watch}
        </p>
      </Section>

      <div className="space-y-2">
        <Accordion title="How it got there" subtitle="the model's reasoning">
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-600">
            {briefing.reasoning}
          </p>
        </Accordion>

        {validation.warnings.length > 0 && (
          <Accordion title="Worth a second look">
            <ul className="space-y-1 text-sm text-slate-600">
              {validation.warnings.map((warning, i) => (
                <li key={i}>{warning}</li>
              ))}
            </ul>
          </Accordion>
        )}
      </div>

      <a
        href={URL.createObjectURL(new Blob([result.markdown], { type: 'text/markdown' }))}
        download={`${briefing.snapshot.split('·')[0].trim()} briefing.md`}
        className="inline-block rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
      >
        Download as markdown
      </a>
    </div>
  )
}

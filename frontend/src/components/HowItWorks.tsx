import { useEffect, useState } from 'react'
import { getInternals, getPipeline, getPrompts } from '../lib/api'
import { NODE_LABELS, NODE_NOTES } from '../lib/nodeLabels'
import type { Internals, Pipeline, PromptDoc } from '../types'
import { Accordion } from './Accordion'

function Card({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 lg:p-6">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <p className="mt-0.5 mb-5 text-xs text-slate-500">{note}</p>
      {children}
    </div>
  )
}

function Diagram({ pipeline }: { pipeline: Pipeline }) {
  const order = new Map(pipeline.nodes.map((n, i) => [n, i]))

  return (
    <div>
      {pipeline.nodes.map((node, i) => {
        // An edge pointing at an earlier node is the cycle.
        const back = pipeline.edges.find((e) => e.source === node && (order.get(e.target) ?? 0) < i)
        return (
          <div key={node}>
            <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm font-medium text-slate-800">
                  {NODE_LABELS[node] ?? node}
                </span>
                <span className="font-mono text-[11px] text-slate-400">{node}</span>
              </div>
              <p className="mt-1 text-xs text-slate-500">{NODE_NOTES[node]}</p>
            </div>
            {back && (
              <div className="my-1 flex items-center gap-2 rounded-md border border-dashed border-amber-300 bg-amber-50 px-3 py-1.5">
                <span className="text-amber-600">↺</span>
                <p className="text-xs text-amber-800">
                  If a citation doesn't hold up, back to{' '}
                  <strong>{NODE_LABELS[back.target] ?? back.target}</strong> with the specific
                  failures attached.
                </p>
              </div>
            )}
            {i < pipeline.nodes.length - 1 && <div className="my-1 ml-5 h-4 w-px bg-slate-300" />}
          </div>
        )
      })}
    </div>
  )
}

export function HowItWorks() {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null)
  const [prompts, setPrompts] = useState<PromptDoc[]>([])
  const [internals, setInternals] = useState<Internals | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getPipeline(), getPrompts(), getInternals()])
      .then(([p, pr, i]) => {
        setPipeline(p)
        setPrompts(pr)
        setInternals(i)
      })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <p className="text-sm text-rose-600">{error}</p>
  if (!pipeline || !internals) return <p className="text-sm text-slate-500">Loading…</p>

  const fields = Object.entries(internals.briefing_schema.properties)

  return (
    <div className="space-y-6">
      <Card
        title="The pipeline"
        note="Read straight off the compiled graph, so it always matches what actually runs."
      >
        <Diagram pipeline={pipeline} />
        <dl className="mt-5 flex flex-wrap gap-x-6 gap-y-1 border-t border-slate-100 pt-4 text-xs">
          {[
            ['Model', internals.model],
            ['Temperature', String(internals.temperature)],
            ['Max attempts', String(internals.max_attempts)],
          ].map(([label, value]) => (
            <div key={label} className="flex gap-2">
              <dt className="text-slate-500">{label}</dt>
              <dd className="font-mono text-slate-700">{value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card
        title="What gets checked"
        note="Run against every briefing before anyone sees it. A failed check either sends it back to the model or ships as a visible warning."
      >
        <ul className="space-y-2">
          {internals.checks.map((check) => (
            <li
              key={check.name}
              className="flex flex-wrap items-baseline gap-x-2 rounded-md border border-slate-200 px-3 py-2"
            >
              <span className="text-sm font-medium text-slate-800">{check.name}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  check.on_failure === 'regenerates'
                    ? 'bg-slate-100 text-slate-600'
                    : 'bg-amber-50 text-amber-700'
                }`}
              >
                {check.on_failure}
              </span>
              <p className="w-full text-xs text-slate-500">{check.detail}</p>
            </li>
          ))}
        </ul>
      </Card>

      <Card
        title="The prompts"
        note="Every instruction the system sends, exactly as sent. Each run in the log records which version produced it."
      >
        <div className="space-y-2">
          {prompts.map((prompt) => (
            <Accordion
              key={prompt.file}
              title={prompt.name}
              subtitle={`${prompt.purpose} · ${prompt.version}`}
            >
              <pre className="max-h-[32rem] overflow-auto rounded-md bg-slate-50 p-3 font-mono text-[11px] whitespace-pre-wrap text-slate-700">
                {prompt.text}
              </pre>
            </Accordion>
          ))}
        </div>
      </Card>

      <Card
        title="What the model must return"
        note="The briefing is a typed contract bound to the model's function calling — not text parsed after the fact. A response that doesn't fit this shape never reaches the page."
      >
        <ul className="space-y-1.5">
          {fields.map(([name, spec]) => (
            <li key={name} className="text-xs">
              <span className="font-mono text-slate-800">{name}</span>
              {spec.description && <span className="ml-2 text-slate-500">{spec.description}</span>}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

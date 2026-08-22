/**
 * Shown in the result pane until the first briefing exists.
 *
 * The pane is empty anyway at that point, and a reviewer who isn't told what to
 * try will generate one briefing and leave — so each prompt is a button that
 * sets itself up rather than an instruction to follow.
 */
const STEP =
  'rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 ' +
  'transition hover:border-slate-400 hover:bg-slate-50'

function Step({
  n,
  title,
  note,
  action,
  onClick,
}: {
  n: number
  title: string
  note?: string
  action: string
  onClick: () => void
}) {
  return (
    <li className="flex gap-3">
      <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
        {n}
      </span>
      <div className="min-w-0">
        <p className="text-sm text-slate-800">{title}</p>
        {note && <p className="mt-0.5 text-xs text-slate-500">{note}</p>}
        <button onClick={onClick} className={`mt-2 ${STEP}`}>
          {action}
        </button>
      </div>
    </li>
  )
}

export function WelcomeCard({
  onGenerate,
  onDropAdoption,
  onOpenPortfolio,
  onOpenHowItWorks,
  canGenerate,
}: {
  onGenerate: () => void
  onDropAdoption: () => void
  onOpenPortfolio: () => void
  onOpenHowItWorks: () => void
  canGenerate: boolean
}) {
  return (
    <div className="py-4">
      <h2 className="text-base font-semibold text-slate-900">
        A pre-call briefing, in about thirty seconds
      </h2>
      <p className="mt-1 mb-6 text-sm text-slate-500">
        Reads an account and works out where it stands, who to talk to, and what to do next.
        Four things worth trying:
      </p>

      <ol className="space-y-5">
        <Step
          n={1}
          title="Generate a briefing for the account on the left"
          note="Watch each step of the pipeline as it runs."
          action={canGenerate ? 'Run it →' : 'Pick an account first'}
          onClick={() => canGenerate && onGenerate()}
        />
        <Step
          n={2}
          title="Drop adoption to 25% and generate again"
          note="The status should change. Nothing is hard-coded — it re-reads the data and re-reasons."
          action="Set the field →"
          onClick={onDropAdoption}
        />
        <Step
          n={3}
          title="See one brief across the whole book"
          note="Every account briefed in parallel, then compared for patterns no single briefing can see."
          action="Open Portfolio →"
        onClick={onOpenPortfolio}
        />
        <Step
          n={4}
          title="Look at what's under it"
          note="The pipeline, the checks that run on every briefing, all three prompts, and the shape the model must return."
          action="Open How it works →"
          onClick={onOpenHowItWorks}
        />
      </ol>

      <p className="mt-6 border-t border-slate-100 pt-4 text-xs text-slate-400">
        Everything here runs live against the model. Nothing is pre-recorded.
      </p>
    </div>
  )
}

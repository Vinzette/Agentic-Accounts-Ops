import { useEffect, useState } from 'react'
import { AccountForm, EMPTY_ACCOUNT } from './components/AccountForm'
import { BriefingPanel } from './components/BriefingPanel'
import { ModeTabs, PastePanel, UploadPanel, type Mode } from './components/InputModes'
import { ManagerPicker } from './components/ManagerPicker'
import { PortfolioView } from './components/PortfolioView'
import { HowItWorks } from './components/HowItWorks'
import { RunLog } from './components/RunLog'
import { WelcomeCard } from './components/WelcomeCard'
import { BriefingSkeleton, PipelineStream } from './components/PipelineStream'
import { getAccounts, getHealth, getManagers, saveAccount, streamBriefing } from './lib/api'
import type { Account, AccountData, Manager, NodeEvent, ResultEvent } from './types'

const NEW_ACCOUNT = 'new'

const TABS = [
  { id: 'briefing', label: 'Briefing' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'runs', label: 'Run log' },
  { id: 'how', label: 'How it works' },
] as const

type Tab = (typeof TABS)[number]['id']

/** A "running" step is replaced in place when its result arrives; the loop appends. */
function applyStep(steps: NodeEvent[], event: NodeEvent): NodeEvent[] {
  if (event.status === 'running') return [...steps, event]

  const target = steps.map((s) => s.node === event.node && s.status === 'running').lastIndexOf(true)
  if (target === -1) return [...steps, event]
  return steps.map((step, i) => (i === target ? event : step))
}

export default function App() {
  const [managers, setManagers] = useState<Manager[]>([])
  const [managerId, setManagerId] = useState<number | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [selected, setSelected] = useState<string>(NEW_ACCOUNT)
  const [form, setForm] = useState<AccountData>(EMPTY_ACCOUNT)
  const [mode, setMode] = useState<Mode>('form')
  const [tab, setTab] = useState<Tab>('briefing')
  // Tabs he hasn't opened get a dot. Everything built after the briefing view
  // is behind a click he has no reason to make unless something points at it.
  const [seen, setSeen] = useState<Set<Tab>>(new Set(['briefing']))

  const openTab = (next: Tab) => {
    setTab(next)
    setSeen((prev) => new Set(prev).add(next))
  }

  const dropAdoption = () =>
    setForm((prev) => ({
      ...prev,
      adoption: 'Daily active field users ~25% of licensed seats, down from 88%',
    }))
  const [notice, setNotice] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const [steps, setSteps] = useState<NodeEvent[]>([])
  const [result, setResult] = useState<ResultEvent | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [waking, setWaking] = useState(false)

  // A hosted container that has been idle takes a while to answer its first
  // request. Say so rather than showing a pane that looks broken.
  useEffect(() => {
    const slow = setTimeout(() => setWaking(true), 1500)
    getHealth()
      .catch(() => undefined)
      .finally(() => {
        clearTimeout(slow)
        setWaking(false)
      })
    return () => clearTimeout(slow)
  }, [])

  useEffect(() => {
    getManagers()
      .then((list) => {
        setManagers(list)
        setManagerId(list[0]?.id ?? null)
      })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (managerId === null) return
    getAccounts(managerId)
      .then((list) => {
        setAccounts(list)
        setSelected(list[0] ? String(list[0].id) : NEW_ACCOUNT)
        setForm(list[0] ? { ...EMPTY_ACCOUNT, ...list[0].data } : EMPTY_ACCOUNT)
      })
      .catch((e) => setError(e.message))
  }, [managerId])

  const pick = (value: string) => {
    setSelected(value)
    setMode('form')
    setNotice(null)
    const account = accounts.find((a) => String(a.id) === value)
    setForm(account ? { ...EMPTY_ACCOUNT, ...account.data } : EMPTY_ACCOUNT)
  }

  /** Extracted or uploaded data becomes an unsaved draft the user reviews before generating. */
  const accept = (data: AccountData, warning?: string) => {
    setForm({ ...EMPTY_ACCOUNT, ...data })
    setSelected(NEW_ACCOUNT)
    setMode('form')
    setNotice(warning ?? null)
  }

  /** Keep an ad-hoc account so it joins this manager's book instead of vanishing on reload. */
  const save = async () => {
    if (managerId === null) return
    setSaving(true)
    setError(null)
    try {
      const saved = await saveAccount(managerId, form)
      setAccounts(await getAccounts(managerId))
      setManagers(await getManagers())
      setSelected(String(saved.id))
      setNotice(`Saved to this manager's accounts.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const generate = async () => {
    setRunning(true)
    setError(null)
    setSteps([])
    setResult(null)

    try {
      await streamBriefing(
        {
          account_data: form,
          account_id: selected === NEW_ACCOUNT ? null : Number(selected),
          input_source: 'form',
        },
        (event) => {
          if (event.type === 'node') setSteps((prev) => applyStep(prev, event))
          else if (event.type === 'result') setResult(event)
          else setError(event.message)
        },
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3 lg:px-6">
          <div className="flex items-center gap-2.5">
            <span className="flex size-7 items-center justify-center rounded bg-slate-900 text-xs font-bold text-white">
              FA
            </span>
            <div>
              <h1 className="text-sm font-semibold text-slate-900">Pre-Call Briefing Agent</h1>
              <p className="text-xs text-slate-500">Global Account Management</p>
            </div>
          </div>

          <ManagerPicker
            managers={managers}
            managerId={managerId}
            onSelect={setManagerId}
            onAdded={(manager) => {
              setManagers((prev) => [...prev, manager])
              setManagerId(manager.id)
            }}
          />
        </div>
      </header>

      <nav className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl gap-5 overflow-x-auto px-4 sm:gap-6 lg:px-6">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => openTab(t.id)}
              className={`-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-1 py-2.5 text-sm font-medium whitespace-nowrap transition ${
                tab === t.id
                  ? 'border-slate-900 text-slate-900'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              {t.label}
              {!seen.has(t.id) && <span className="size-1.5 rounded-full bg-sky-500" />}
            </button>
          ))}
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-4 py-6 lg:px-6">
        {tab === 'portfolio' && (
          <PortfolioView manager={managers.find((m) => m.id === managerId)} />
        )}

        {/* Remounted on each visit so it always shows the latest runs. */}
        {tab === 'runs' && <RunLog />}

        {tab === 'how' && <HowItWorks />}

        <div
          className={`grid gap-6 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] ${
            tab === 'briefing' ? '' : 'hidden'
          }`}
        >
          <aside className="rounded-lg border border-slate-200 bg-white p-4">
            <label className="mb-1 block text-xs font-medium tracking-wide text-slate-600 uppercase">
              Account
            </label>
            <select
              className="mb-4 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={selected}
              onChange={(e) => pick(e.target.value)}
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name}
                </option>
              ))}
              <option value={NEW_ACCOUNT}>+ New account</option>
            </select>

            <ModeTabs mode={mode} onChange={setMode} />

            {mode === 'paste' && <PastePanel onExtracted={accept} />}
            {mode === 'upload' && <UploadPanel onLoaded={accept} />}

            {notice && (
              <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                {notice}
              </p>
            )}

            {mode === 'form' && (
              <>
                <AccountForm value={form} onChange={setForm} />

                <button
                  onClick={generate}
                  disabled={running || !form.account_name.trim()}
                  className="mt-5 w-full rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {running ? 'Generating…' : 'Generate briefing'}
                </button>

                {selected === NEW_ACCOUNT && form.account_name.trim() && (
                  <button
                    onClick={save}
                    disabled={saving}
                    className="mt-2 w-full rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:text-slate-300"
                  >
                    {saving ? 'Saving…' : 'Save to this manager\u2019s accounts'}
                  </button>
                )}

                <p className="mt-3 text-xs text-slate-500">
                  Edit any field and re-run. Drop adoption to ~25% and watch the status change.
                </p>
              </>
            )}
          </aside>

          <section className="rounded-lg border border-slate-200 bg-white p-5 lg:p-6">
            {error && (
              <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-3 py-3">
                <p className="text-sm text-rose-700">{error}</p>
                <button
                  onClick={generate}
                  disabled={running || !form.account_name.trim()}
                  className="mt-2 rounded-md border border-rose-300 bg-white px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                >
                  Try again
                </button>
              </div>
            )}

            {waking && !running && !result && !error && (
              <p className="flex items-center gap-2 py-16 text-sm text-slate-500">
                <span className="block size-3.5 animate-spin rounded-full border-2 border-slate-200 border-t-slate-700" />
                Waking the server — it sleeps when idle, so the first request takes a moment.
              </p>
            )}

            {!waking && !running && !result && !error && (
              <WelcomeCard
                canGenerate={Boolean(form.account_name.trim())}
                onGenerate={generate}
                onDropAdoption={dropAdoption}
                onOpenPortfolio={() => openTab('portfolio')}
                onOpenHowItWorks={() => openTab('how')}
              />
            )}

            {steps.length > 0 && !result && (
              <>
                <PipelineStream steps={steps} />
                {running && <BriefingSkeleton />}
              </>
            )}

            {result && (
              <>
                <BriefingPanel result={result} />
                {!seen.has('portfolio') && (
                  <button
                    onClick={() => openTab('portfolio')}
                    className="mt-6 w-full rounded-md border border-dashed border-slate-300 px-3 py-2.5 text-left text-sm text-slate-600 transition hover:border-slate-400 hover:bg-slate-50"
                  >
                    That's one account. See one brief across the whole book →
                  </button>
                )}
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}

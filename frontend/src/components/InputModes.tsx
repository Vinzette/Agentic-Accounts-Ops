import { useState } from 'react'
import { extractAccount, uploadAccountFile } from '../lib/api'
import { SAMPLE_NOTES } from '../lib/sampleNotes'
import type { AccountData } from '../types'

export type Mode = 'form' | 'paste' | 'upload'

const MODES: { id: Mode; label: string }[] = [
  { id: 'form', label: 'Form' },
  { id: 'paste', label: 'Paste notes' },
  { id: 'upload', label: 'Upload' },
]

export function ModeTabs({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <div className="mb-4 flex gap-1 rounded-md bg-slate-100 p-1">
      {MODES.map((m) => (
        <button
          key={m.id}
          onClick={() => onChange(m.id)}
          className={`flex-1 rounded px-2 py-1.5 text-xs font-medium transition ${
            mode === m.id ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  )
}

export function PastePanel({ onExtracted }: { onExtracted: (data: AccountData) => void }) {
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      onExtracted(await extractAccount(notes))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">
        Paste CRM notes, an email thread, meeting notes — whatever you have. The fields get
        filled in for you to check before anything is generated.
      </p>

      <div className="rounded-md border border-slate-200 bg-slate-50 p-2.5">
        <p className="mb-2 text-xs font-medium text-slate-600">Or start from a sample</p>
        <div className="space-y-1.5">
          {SAMPLE_NOTES.map((sample) => (
            <button
              key={sample.label}
              onClick={() => setNotes(sample.text)}
              className="block w-full rounded border border-slate-200 bg-white px-2.5 py-1.5 text-left transition hover:border-slate-300"
            >
              <span className="text-xs font-medium text-slate-700">{sample.label}</span>
              <span className="block text-[11px] text-slate-500">{sample.note}</span>
            </button>
          ))}
        </div>
      </div>
      <textarea
        rows={12}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder={'call w/ Brightleaf Foods tues — renewal is Sept so ~4 months out.\nthey\'re on ~£680k, was £610k last yr…'}
        className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-xs shadow-xs placeholder:text-slate-400 focus:border-slate-500 focus:ring-1 focus:ring-slate-500 focus:outline-none"
      />
      {error && <p className="text-xs text-rose-600">{error}</p>}
      <button
        onClick={run}
        disabled={busy || !notes.trim()}
        className="w-full rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-300"
      >
        {busy ? 'Reading the notes…' : 'Extract fields →'}
      </button>
    </div>
  )
}

export function UploadPanel({
  onLoaded,
}: {
  onLoaded: (data: AccountData, notice?: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const read = async (file: File) => {
    setError(null)
    setBusy(true)
    try {
      // Already-structured JSON needs no model call. Everything else is parsed
      // server-side — PDFs, decks and spreadsheets aren't readable as text here.
      if (file.name.toLowerCase().endsWith('.json')) {
        const parsed = JSON.parse(await file.text())
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
          throw new Error('That file should contain a single JSON object.')
        }
        onLoaded(parsed as AccountData)
      } else {
        const result = await uploadAccountFile(file)
        onLoaded(
          result.account,
          result.truncated
            ? `Only the first ${result.used_chars.toLocaleString()} of ` +
                `${result.total_chars.toLocaleString()} characters were read. Check the fields ` +
                `below — anything further into the document was not seen.`
            : undefined,
        )
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-slate-500">
        A QBR deck, a contract, a usage export, meeting notes. PDF, Word, Excel, PowerPoint,
        CSV or plain text — the fields land in the form for you to review.
      </p>
      <input
        type="file"
        accept=".pdf,.docx,.xlsx,.xlsm,.pptx,.csv,.tsv,.txt,.md,.json"
        disabled={busy}
        onChange={(e) => e.target.files?.[0] && read(e.target.files[0])}
        className="w-full rounded-md border border-dashed border-slate-300 px-3 py-6 text-xs text-slate-500 file:mr-3 file:rounded file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-xs file:text-white"
      />
      {busy && <p className="text-xs text-slate-500">Reading the file…</p>}
      {error && <p className="text-xs text-rose-600">{error}</p>}
      <p className="text-xs text-slate-400">
        Prefer the original file over a PDF export — PDFs lose characters and slide layout.
        Scanned PDFs hold no text at all and would need OCR first.
      </p>
    </div>
  )
}

import { useState } from 'react'
import { apiPost, apiUpload } from '../api'
import DemoToggle from '../components/DemoToggle'
import LangChip from '../components/LangChip'
import MicButton from '../components/MicButton'
import { useRecorder } from '../hooks/useRecorder'

export default function Ask({ onBack }) {
  const { recording, start, stop, error: micError } = useRecorder()
  const [q, setQ] = useState('How do I find work on KaamLink?')
  const [langHint, setLangHint] = useState('auto')
  const [answerLang, setAnswerLang] = useState('English')
  const [demoMode, setDemoMode] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const suggestions = [
    'How do I find work on KaamLink?',
    'How do I hire workers?',
    'What if wages are unpaid?',
    'How do I browse available masons?',
    'Site safety tips?',
  ]

  async function askText() {
    setLoading(true)
    setError('')
    try {
      const data = await apiPost('/api/rag/ask', {
        question: q,
        language: answerLang,
        demo_mode: demoMode,
      })
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleMic() {
    if (!recording) {
      await start()
      return
    }
    setLoading(true)
    setError('')
    try {
      const blob = await stop()
      const file = new File([blob], 'ask.webm', { type: blob.type || 'audio/webm' })
      const data = await apiUpload('/api/rag/ask/voice', file, {
        language_hint: langHint,
        language: answerLang,
        demo_mode: demoMode,
      })
      setResult(data)
    } catch (err) {
      setError(err.message || micError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-6 pb-16">
      <button type="button" onClick={onBack} className="text-sm font-semibold text-orange-600">← Home</button>
      <h1 className="mt-2 text-3xl font-bold text-[#0b1f3a]">Ask KaamLink</h1>
      <p className="mt-1 text-sm text-slate-600">KaamLink docs + general AI chat · ask anything</p>

      <div className="mt-4 space-y-3 rounded-2xl border border-slate-200 bg-white/80 p-3">
        <div className="text-xs font-semibold uppercase text-slate-500">Voice language</div>
        <LangChip value={langHint} onChange={setLangHint} />
        <div className="text-xs font-semibold uppercase text-slate-500">Answer language</div>
        <select value={answerLang} onChange={(e) => setAnswerLang(e.target.value)} className="w-full rounded-lg border border-slate-300 p-2 text-sm">
          <option>English</option>
          <option>Hindi</option>
          <option>Tamil</option>
        </select>
        <DemoToggle on={demoMode} setOn={setDemoMode} />
      </div>

      <div className="mt-6 flex flex-col items-center gap-3">
        <MicButton recording={recording} onToggle={handleMic} disabled={loading} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setQ(s)}
            className="rounded-full border border-slate-300 bg-white px-3 py-1 text-[11px] font-semibold text-slate-700"
          >
            {s}
          </button>
        ))}
      </div>
      <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={3} className="mt-3 w-full rounded-xl border border-slate-300 bg-white p-3 text-sm" />
      <button type="button" onClick={askText} disabled={loading} className="mt-2 w-full rounded-xl bg-orange-500 py-3 font-semibold text-white disabled:opacity-50">
        {loading ? 'Thinking…' : 'Ask'}
      </button>
      {error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {result && (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="font-bold text-[#0b1f3a]">Answer</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{result.answer}</p>
          {result.sources?.length > 0 && (
            <div className="mt-3 text-xs text-slate-500">
              Sources: {result.sources.join(', ')}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

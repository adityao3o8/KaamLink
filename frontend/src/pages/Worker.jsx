import { useState } from 'react'
import { apiPost, apiUpload } from '../api'
import DemoToggle from '../components/DemoToggle'
import LangChip from '../components/LangChip'
import LanguageBadge from '../components/LanguageBadge'
import MicButton from '../components/MicButton'
import { useRecorder } from '../hooks/useRecorder'

const EMPTY = {
  name: '',
  skill: '',
  experience_years: 1,
  area: '',
  availability: [],
  languages: 'Hindi',
  expected_wage: 700,
  phone: '',
  profile_text: '',
  missing_fields: [],
  clarifying_question: null,
}

export default function Worker({ onBack }) {
  const { recording, error: micError, start, stop } = useRecorder()
  const [text, setText] = useState(
    'Main Ravi, 8 saal ka raj mistri, Chengalpattu area, 850 per day, Tamil Hindi bolta hoon'
  )
  const [phone, setPhone] = useState('9876543210')
  const [langHint, setLangHint] = useState('auto')
  const [demoMode, setDemoMode] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hint, setHint] = useState('')
  const [transcript, setTranscript] = useState('')
  const [form, setForm] = useState(EMPTY)
  const [saved, setSaved] = useState(null)

  function applyExtract(data) {
    const e = data.extracted || {}
    setTranscript(data.transcript || '')
    setForm({
      name: e.name || '',
      skill: e.skill || '',
      experience_years: e.experience_years || 1,
      area: e.area || '',
      availability: e.availability || [],
      languages: e.languages || 'Hindi',
      expected_wage: e.expected_wage || 700,
      phone: e.phone || phone,
      profile_text: e.profile_text || data.transcript || '',
      missing_fields: e.missing_fields || [],
      clarifying_question: e.clarifying_question || null,
    })
    setSaved(null)
    if (e.missing_fields?.length) {
      setHint('Voice/text was incomplete. Edit the fields below or click Extract profile on the typed text.')
    } else {
      setHint('')
    }
  }

  async function handleMic() {
    setError('')
    setHint('')
    if (!recording) {
      await start()
      return
    }
    setLoading(true)
    try {
      const blob = await stop()
      const file = new File([blob], 'worker.webm', { type: blob.type || 'audio/webm' })
      const data = await apiUpload('/api/worker/voice', file, {
        phone,
        language_hint: langHint,
        demo_mode: demoMode,
      })
      // keep typed box in sync if STT returned something useful
      if (data.transcript) setText(data.transcript)
      applyExtract(data)
    } catch (err) {
      setError(err.message || 'Voice failed. Use Extract profile on the text below.')
    } finally {
      setLoading(false)
    }
  }

  async function submitText() {
    setError('')
    setHint('')
    setLoading(true)
    try {
      const data = await apiPost('/api/worker/text', {
        text,
        phone,
        language_hint: langHint,
        demo_mode: demoMode,
      })
      applyExtract(data)
    } catch (err) {
      setError(err.message || 'Could not extract profile')
    } finally {
      setLoading(false)
    }
  }

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value, missing_fields: [] }))
  }

  const canSave = form.name.trim() && form.skill.trim() && form.area.trim()

  async function confirmSave() {
    if (!canSave) {
      setError('Name, skill and area are required.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await apiPost('/api/worker/confirm', {
        transcript: transcript || text,
        name: form.name,
        skill: form.skill,
        experience_years: Number(form.experience_years) || 1,
        area: form.area,
        availability: form.availability || [],
        languages: form.languages || 'Hindi',
        expected_wage: Number(form.expected_wage) || 700,
        phone: form.phone || phone,
        profile_text: form.profile_text || transcript || text,
      })
      setSaved(data)
    } catch (err) {
      setError(err.message || 'Save failed')
    } finally {
      setLoading(false)
    }
  }

  const showCard = Boolean(transcript || form.name || form.skill || form.area || form.clarifying_question)

  return (
    <div className="mx-auto max-w-lg px-4 py-6 pb-16">
      <button type="button" onClick={onBack} className="text-sm font-semibold text-orange-600">
        ← Home
      </button>
      <h1 className="mt-2 text-3xl font-bold text-[#0b1f3a]">I need work</h1>
      <p className="mt-1 text-sm text-slate-600">Say your name, trade, area, and wage. · Groq Whisper + Llama</p>

      <div className="mt-4 space-y-3 rounded-2xl border border-slate-200 bg-white/80 p-3">
        <LangChip value={langHint} onChange={setLangHint} />
        <DemoToggle on={demoMode} setOn={setDemoMode} />
      </div>

      <div className="mt-8 flex flex-col items-center gap-3">
        <MicButton recording={recording} onToggle={handleMic} disabled={loading} />
        <p className="text-sm text-slate-500">
          {recording ? 'Listening…' : loading ? 'Working…' : 'Mic optional — or type below and Extract'}
        </p>
        {(micError || error) && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error || micError}</p>
        )}
        {hint && <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{hint}</p>}
      </div>

      <div className="mt-6 space-y-3">
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Phone</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-3 text-sm"
          />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Type profile (recommended for demo)</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-3 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={submitText}
          disabled={loading}
          className="w-full rounded-xl bg-orange-500 py-3 font-semibold text-white disabled:opacity-50"
        >
          Extract profile
        </button>
      </div>

      {showCard && (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">Extracted profile</h2>
            <LanguageBadge language={(form.languages || 'Hindi').split(',')[0]} />
          </div>
          {transcript && (
            <p className="mt-2 rounded-lg bg-slate-50 p-3 text-sm italic">“{transcript}”</p>
          )}
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <label className="block">
              <span className="text-slate-500">Name</span>
              <input value={form.name} onChange={(e) => setField('name', e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-semibold" />
            </label>
            <label className="block">
              <span className="text-slate-500">Skill</span>
              <input value={form.skill} onChange={(e) => setField('skill', e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-semibold" placeholder="mason" />
            </label>
            <label className="block">
              <span className="text-slate-500">Experience (yrs)</span>
              <input type="number" value={form.experience_years} onChange={(e) => setField('experience_years', e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-semibold" />
            </label>
            <label className="block">
              <span className="text-slate-500">Area</span>
              <input value={form.area} onChange={(e) => setField('area', e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-semibold" />
            </label>
            <label className="block">
              <span className="text-slate-500">Wage</span>
              <input type="number" value={form.expected_wage} onChange={(e) => setField('expected_wage', e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-semibold" />
            </label>
            <label className="block">
              <span className="text-slate-500">Languages</span>
              <input value={form.languages} onChange={(e) => setField('languages', e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 p-2 font-semibold" />
            </label>
          </div>
          {form.clarifying_question && !canSave && (
            <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
              {form.clarifying_question}
            </p>
          )}
          <button
            type="button"
            onClick={confirmSave}
            disabled={loading || !canSave}
            className="mt-4 w-full rounded-xl bg-[#0b1f3a] py-3 font-semibold text-white disabled:opacity-50"
          >
            Confirm & save
          </button>
        </section>
      )}

      {saved?.saved && (
        <div className="mt-4 rounded-xl border border-green-300 bg-green-50 p-4 text-sm text-green-900">
          Saved worker #{saved.worker_id}. You will show up in contractor shortlists.
        </div>
      )}
    </div>
  )
}

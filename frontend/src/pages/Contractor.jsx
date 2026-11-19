import { useEffect, useMemo, useState } from 'react'
import { apiGet, apiPost, apiUpload, playTts } from '../api'
import DemoToggle from '../components/DemoToggle'
import LangChip from '../components/LangChip'
import LanguageBadge from '../components/LanguageBadge'
import MicButton from '../components/MicButton'
import { useRecorder } from '../hooks/useRecorder'

function ScoreBars({ score }) {
  const rows = [
    ['Embedding', score.embedding],
    ['Reliability', score.reliability],
    ['Wage fit', score.wage_fit],
    ['Area', score.area_match],
  ]
  return (
    <div className="mt-2 space-y-1">
      {rows.map(([label, val]) => (
        <div key={label} className="flex items-center gap-2 text-xs">
          <span className="w-20 text-slate-500">{label}</span>
          <div className="score-bar flex-1">
            <span style={{ width: `${Math.round(val * 100)}%` }} />
          </div>
          <span className="w-10 text-right font-medium">{Math.round(val * 100)}</span>
        </div>
      ))}
      <div className="pt-1 text-sm font-bold text-[#0b1f3a]">Total {(score.total * 100).toFixed(0)}%</div>
    </div>
  )
}

export default function Contractor({ onBack, onBrowse }) {
  const { recording, error: micError, start, stop } = useRecorder()
  const [text, setText] = useState('Kal 3 mason chahiye, Chengalpattu mein, 800 per day')
  const [langHint, setLangHint] = useState('auto')
  const [demoMode, setDemoMode] = useState(false)
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [job, setJob] = useState(null)
  const [matches, setMatches] = useState([])
  const [shortlistMs, setShortlistMs] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [timeline, setTimeline] = useState([])
  const [needed, setNeeded] = useState(1)
  const [confirmedCount, setConfirmedCount] = useState(0)
  const [ratings, setRatings] = useState({})
  const [wageInfo, setWageInfo] = useState(null)

  const confirmed = useMemo(() => alerts.filter((a) => a.confirmed), [alerts])

  useEffect(() => {
    if (!job?.job_id) return undefined
    const t = setInterval(async () => {
      try {
        const data = await apiGet(`/api/alert/${job.job_id}`)
        setAlerts(data.alerts || [])
        setTimeline(data.timeline || [])
        setConfirmedCount(data.confirmed_count || 0)
        setNeeded(data.needed || 1)
      } catch {
        /* ignore poll errors */
      }
    }, 4000)
    return () => clearInterval(t)
  }, [job?.job_id])

  async function loadWage(extracted) {
    if (!extracted?.skill || !extracted?.location) {
      setWageInfo(null)
      return
    }
    try {
      const q = new URLSearchParams({
        skill: extracted.skill,
        area: extracted.location,
        offered: String(extracted.wage_per_day || ''),
      })
      const data = await apiGet(`/api/wage/suggest?${q}`)
      setWageInfo(data)
    } catch {
      setWageInfo(null)
    }
  }

  async function handleMic() {
    setError('')
    if (!recording) {
      await start()
      return
    }
    setLoading('transcribing')
    try {
      const blob = await stop()
      if (!blob) throw new Error('No audio captured')
      const file = new File([blob], 'job.webm', { type: blob.type || 'audio/webm' })
      const data = await apiUpload('/api/job/voice', file, {
        language_hint: langHint,
        demo_mode: demoMode,
      })
      setJob(data)
      setMatches([])
      setAlerts([])
      setTimeline([])
      await loadWage(data.extracted)
      if (!data.needs_clarification) await runMatch(data.job_id)
    } catch (err) {
      setError(err.message || 'Voice failed. Use the text box.')
    } finally {
      setLoading('')
    }
  }

  async function submitText() {
    setError('')
    setLoading('extracting')
    try {
      const data = await apiPost('/api/job/text', {
        text,
        language_hint: langHint,
        demo_mode: demoMode,
      })
      setJob(data)
      setMatches([])
      setAlerts([])
      setTimeline([])
      await loadWage(data.extracted)
      if (!data.needs_clarification) await runMatch(data.job_id)
    } catch (err) {
      setError(err.message || 'Could not extract job')
    } finally {
      setLoading('')
    }
  }

  async function runMatch(jobId) {
    setLoading('matching')
    try {
      const data = await apiPost(`/api/match/${jobId}`, {})
      setMatches(data.matches || [])
      setShortlistMs(data.shortlist_ms)
    } catch (err) {
      setError(err.message || 'Matching failed')
    } finally {
      setLoading('')
    }
  }

  async function sendAlerts() {
    if (!job?.job_id) return
    setLoading('alerting')
    setError('')
    try {
      const data = await apiPost(`/api/alert/${job.job_id}`, {})
      setAlerts(data.alerts || [])
      setTimeline(data.timeline || [])
      setConfirmedCount(data.confirmed_count || 0)
      setNeeded(data.needed || 1)
      setToast('Wave alerts started (timeout auto-fallback enabled)')
    } catch (err) {
      setError(err.message || 'Alert simulation failed')
    } finally {
      setLoading('')
    }
  }

  async function simulate() {
    if (!job?.job_id) return
    try {
      const data = await apiPost(`/api/alert/${job.job_id}/simulate`, {})
      setAlerts(data.alerts || [])
      setTimeline(data.timeline || [])
      setConfirmedCount(data.confirmed_count || 0)
      setNeeded(data.needed || 1)
    } catch (err) {
      setError(err.message)
    }
  }

  async function reply(alertId, response) {
    try {
      await apiPost(`/api/alert/${alertId}/reply`, { response })
      const data = await apiGet(`/api/alert/${job.job_id}`)
      setAlerts(data.alerts || [])
      setTimeline(data.timeline || [])
      setConfirmedCount(data.confirmed_count || 0)
    } catch (err) {
      setError(err.message || 'Reply failed')
    }
  }

  async function rate(workerId, stars) {
    try {
      const data = await apiPost('/api/rate', { job_id: job.job_id, worker_id: workerId, stars })
      setRatings((prev) => ({ ...prev, [workerId]: data }))
    } catch (err) {
      setError(err.message)
    }
  }

  async function adjustWage() {
    if (!wageInfo || !job) return
    setText(
      `${job.extracted.count || 1} ${job.extracted.skill} chahiye ${job.extracted.location} mein ${job.extracted.date || 'kal'}, ${wageInfo.median} per day`
    )
    setToast(`Adjusted draft wage to median ₹${wageInfo.median} — tap Extract again`)
  }

  const extracted = job?.extracted

  return (
    <div className="mx-auto max-w-lg px-4 py-6 pb-16">
      <button type="button" onClick={onBack} className="text-sm font-semibold text-orange-600">← Home</button>
      <h1 className="mt-2 text-3xl font-bold text-[#0b1f3a]">Need workers</h1>
      <p className="mt-1 text-sm text-slate-600">Groq Whisper + Llama · voice-first Hinglish / Tanglish</p>
      {onBrowse && (
        <button
          type="button"
          onClick={onBrowse}
          className="mt-3 w-full rounded-xl border border-[#0b1f3a] bg-white py-3 text-sm font-bold text-[#0b1f3a]"
        >
          Browse all available masons / workers →
        </button>
      )}

      <div className="mt-4 space-y-3 rounded-2xl border border-slate-200 bg-white/80 p-3">
        <div className="text-xs font-semibold uppercase text-slate-500">STT language</div>
        <LangChip value={langHint} onChange={setLangHint} />
        <DemoToggle on={demoMode} setOn={setDemoMode} />
      </div>

      <div className="mt-8 flex flex-col items-center gap-3">
        <MicButton recording={recording} onToggle={handleMic} disabled={!!loading} />
        <p className="text-sm text-slate-500">
          {recording ? 'Listening… tap to stop' : loading ? `Working: ${loading}` : 'Tap mic or type below'}
        </p>
        {(micError || error) && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error || micError}</p>}
        {toast && <p className="rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-800">{toast}</p>}
      </div>

      <div className="mt-6">
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Or type it</label>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} className="mt-1 w-full rounded-xl border border-slate-300 bg-white p-3 text-sm outline-none focus:border-orange-400" />
        <button type="button" onClick={submitText} disabled={!!loading} className="mt-2 w-full rounded-xl bg-orange-500 py-3 font-semibold text-white disabled:opacity-50">
          Extract & match
        </button>
      </div>

      {job && (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-bold">Transcript</h2>
            <LanguageBadge language={job.language} />
          </div>
          <p className="mt-2 rounded-lg bg-slate-50 p-3 text-sm italic text-slate-700">“{job.transcript}”</p>
          {job.demo_mode && <p className="mt-1 text-xs text-amber-700">Demo / fallback path used</p>}

          <h3 className="mt-4 text-sm font-bold uppercase tracking-wide text-[#0b1f3a]">Extracted job</h3>
          {extracted && (
            <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-slate-500">Skill</span><div className="font-semibold">{extracted.skill || '—'}</div></div>
              <div><span className="text-slate-500">Count</span><div className="font-semibold">{extracted.count || '—'}</div></div>
              <div><span className="text-slate-500">Date</span><div className="font-semibold">{extracted.date || '—'}</div></div>
              <div><span className="text-slate-500">Location</span><div className="font-semibold">{extracted.location || '—'}</div></div>
              <div><span className="text-slate-500">Wage/day</span><div className="font-semibold">{extracted.wage_per_day ? `₹${extracted.wage_per_day}` : '—'}</div></div>
            </div>
          )}

          {wageInfo && (
            <div className={`mt-3 rounded-lg border p-3 text-sm ${wageInfo.is_lowball ? 'border-amber-400 bg-amber-50 text-amber-950' : 'border-slate-200 bg-slate-50 text-slate-700'}`}>
              <div>{wageInfo.message}</div>
              {wageInfo.is_lowball && (
                <button type="button" onClick={adjustWage} className="mt-2 rounded-lg bg-[#0b1f3a] px-3 py-2 text-xs font-bold text-white">
                  Adjust to median ₹{wageInfo.median}
                </button>
              )}
            </div>
          )}

          {job.needs_clarification && (
            <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              {extracted?.clarifying_question || 'Please add missing details.'}
            </p>
          )}
        </section>
      )}

      {matches.length > 0 && (
        <section className="mt-6">
          <div className="mb-3 flex items-end justify-between">
            <h2 className="text-xl font-bold text-[#0b1f3a]">Shortlist</h2>
            {shortlistMs != null && <span className="text-xs text-slate-500">{shortlistMs} ms</span>}
          </div>
          <div className="space-y-3">
            {matches.map((m) => (
              <article key={m.worker_id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-bold">{m.name}</div>
                    <div className="text-sm text-slate-600">{m.skill} · {m.experience_years}y · {m.area}</div>
                    <div className="text-xs text-slate-500">₹{m.expected_wage}/day · ★ {m.reliability} · {m.phone_masked}</div>
                  </div>
                  <LanguageBadge language={m.languages?.[0]} />
                </div>
                <ScoreBars score={m.score} />
              </article>
            ))}
          </div>
          <button type="button" onClick={sendAlerts} disabled={!!loading} className="mt-4 w-full rounded-xl bg-[#0b1f3a] py-3 font-semibold text-white disabled:opacity-50">
            Alert in waves of 5
          </button>
        </section>
      )}

      {(alerts.length > 0 || timeline.length > 0) && (
        <section className="mt-6">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xl font-bold text-[#0b1f3a]">Wave alerts</h2>
            <span className="text-xs font-semibold text-slate-600">{confirmedCount}/{needed} confirmed</span>
          </div>
          <button type="button" onClick={simulate} className="mb-3 w-full rounded-xl border border-orange-300 bg-orange-50 py-2 text-sm font-semibold text-orange-800">
            Simulate worker replies
          </button>
          {timeline.length > 0 && (
            <div className="mb-3 max-h-40 overflow-auto rounded-xl bg-slate-100 p-3 text-xs text-slate-700">
              {timeline.map((t) => (
                <div key={t.id} className="border-b border-slate-200 py-1 last:border-0">• {t.message}</div>
              ))}
            </div>
          )}
          <div className="space-y-3 rounded-2xl bg-[#0b1f3a] p-4">
            {alerts.map((a) => (
              <div key={a.alert_id} className="rounded-2xl bg-[#12355b] p-3 text-white">
                <div className="mb-1 flex items-center justify-between text-xs text-blue-200">
                  <span>{a.worker_name} · wave {a.wave} · {a.status}</span>
                  <LanguageBadge language={a.language} />
                </div>
                <div className="rounded-2xl rounded-tl-sm bg-[#25d366] px-3 py-2 text-sm text-[#0b1f3a]">{a.message}</div>
                <div className="mt-2 flex gap-2">
                  <button type="button" onClick={() => reply(a.alert_id, 'yes')} disabled={a.status !== 'sent'} className="flex-1 rounded-lg bg-white py-2 text-sm font-bold text-green-700 disabled:opacity-40">Yes</button>
                  <button type="button" onClick={() => reply(a.alert_id, 'no')} disabled={a.status !== 'sent'} className="flex-1 rounded-lg bg-white/10 py-2 text-sm font-bold text-white disabled:opacity-40">No</button>
                  <button type="button" onClick={() => playTts(a.message, a.language).catch((e) => setError(e.message))} className="rounded-lg bg-orange-500 px-3 py-2 text-sm font-bold">▶</button>
                </div>
                {a.response && (
                  <p className="mt-2 text-xs text-blue-100">
                    {a.status.toUpperCase()}{a.confirmed && a.phone ? ` · Phone: ${a.phone}` : ''}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {confirmed.length > 0 && (
        <section className="mt-6 rounded-2xl border border-green-200 bg-green-50 p-4">
          <h2 className="text-lg font-bold text-green-900">Confirmed workers</h2>
          <ul className="mt-2 space-y-3">
            {confirmed.map((a) => (
              <li key={a.alert_id} className="rounded-xl bg-white p-3 text-sm">
                <div className="font-semibold">{a.worker_name}</div>
                <div className="text-slate-600">{a.phone}</div>
                <div className="mt-2 flex items-center gap-1">
                  <span className="mr-2 text-xs text-slate-500">Rate:</span>
                  {[1, 2, 3, 4, 5].map((s) => (
                    <button key={s} type="button" onClick={() => rate(a.worker_id, s)} className={`h-9 w-9 rounded-full text-sm font-bold ${ratings[a.worker_id]?.stars === s ? 'bg-orange-500 text-white' : 'bg-slate-100 text-slate-700'}`}>{s}</button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

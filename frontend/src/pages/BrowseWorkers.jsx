import { useEffect, useMemo, useState } from 'react'
import { apiGet } from '../api'
import LanguageBadge from '../components/LanguageBadge'

const SKILLS = ['mason', 'painter', 'plumber', 'electrician', 'helper', 'carpenter']

function tomorrowISO() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

export default function BrowseWorkers({ onBack }) {
  const [skill, setSkill] = useState('mason')
  const [area, setArea] = useState('')
  const [onlyAvailable, setOnlyAvailable] = useState(true)
  const [workers, setWorkers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const availableOn = useMemo(() => (onlyAvailable ? tomorrowISO() : ''), [onlyAvailable])

  async function load() {
    setLoading(true)
    setError('')
    try {
      const q = new URLSearchParams()
      if (skill) q.set('skill', skill)
      if (area.trim()) q.set('area', area.trim())
      if (availableOn) q.set('available_on', availableOn)
      const data = await apiGet(`/api/worker?${q}`)
      setWorkers(data.workers || [])
    } catch (err) {
      setError(err.message || 'Could not load workers')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skill, onlyAvailable])

  return (
    <div className="mx-auto max-w-lg px-4 py-6 pb-16">
      <button type="button" onClick={onBack} className="text-sm font-semibold text-orange-600">
        ← Home
      </button>
      <h1 className="mt-2 text-3xl font-bold text-[#0b1f3a]">Available workers</h1>
      <p className="mt-1 text-sm text-slate-600">Browse by trade — useful before posting a job.</p>

      <div className="mt-4 space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase text-slate-500">Skill</div>
          <div className="flex flex-wrap gap-2">
            {SKILLS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSkill(s)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${
                  skill === s
                    ? 'border-orange-500 bg-orange-500 text-white'
                    : 'border-slate-300 bg-white text-slate-700'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase text-slate-500">Area filter (optional)</span>
          <input
            value={area}
            onChange={(e) => setArea(e.target.value)}
            placeholder="Chengalpattu / Chennai…"
            className="mt-1 w-full rounded-xl border border-slate-300 p-3 text-sm"
          />
        </label>

        <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
          <input
            type="checkbox"
            checked={onlyAvailable}
            onChange={(e) => setOnlyAvailable(e.target.checked)}
            className="h-4 w-4 accent-orange-500"
          />
          Only available tomorrow ({tomorrowISO()})
        </label>

        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="w-full rounded-xl bg-[#0b1f3a] py-3 font-semibold text-white disabled:opacity-50"
        >
          {loading ? 'Loading…' : 'Refresh list'}
        </button>
      </div>

      {error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      <div className="mt-4 text-sm font-semibold text-slate-600">
        {workers.length} {skill}
        {workers.length === 1 ? '' : 's'} found
      </div>

      <div className="mt-3 space-y-3">
        {workers.map((w) => (
          <article key={w.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-lg font-bold text-[#0b1f3a]">{w.name}</div>
                <div className="text-sm text-slate-600">
                  {w.skill} · {w.experience_years}y · {w.area}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  ₹{w.expected_wage}/day · ★ {w.reliability} · {w.phone_masked}
                </div>
              </div>
              <LanguageBadge language={w.languages?.[0]} />
            </div>
            {w.availability?.length > 0 && (
              <div className="mt-2 text-xs text-slate-500">
                Free: {w.availability.slice(0, 4).join(', ')}
                {w.availability.length > 4 ? '…' : ''}
              </div>
            )}
          </article>
        ))}
        {!loading && workers.length === 0 && (
          <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
            No workers for this filter. Try another skill or turn off “only available tomorrow”.
          </p>
        )}
      </div>
    </div>
  )
}

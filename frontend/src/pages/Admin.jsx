import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiGet, apiPost } from '../api'

export default function Admin({ onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      setData(await apiGet('/api/analytics/dashboard'))
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function generate() {
    setBusy(true)
    setError('')
    try {
      await apiPost('/api/analytics/generate-demo', {})
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-6 pb-16">
      <button type="button" onClick={onBack} className="text-sm font-semibold text-orange-600">← Home</button>
      <h1 className="mt-2 text-3xl font-bold text-[#0b1f3a]">Analytics</h1>
      <p className="mt-1 text-sm text-slate-600">Jobs, acceptance, shortlist speed, reliability</p>

      <button type="button" onClick={generate} disabled={busy} className="mt-4 w-full rounded-xl bg-orange-500 py-3 font-semibold text-white disabled:opacity-50">
        {busy ? 'Generating…' : 'Generate demo data (100 jobs)'}
      </button>
      {error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {data && (
        <>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-xl bg-white p-3 shadow-sm"><div className="text-slate-500">Jobs</div><div className="text-xl font-bold">{data.totals.jobs}</div></div>
            <div className="rounded-xl bg-white p-3 shadow-sm"><div className="text-slate-500">Workers</div><div className="text-xl font-bold">{data.totals.workers}</div></div>
            <div className="rounded-xl bg-white p-3 shadow-sm"><div className="text-slate-500">Avg ms</div><div className="text-xl font-bold">{data.avg_time_to_shortlist_ms}</div></div>
          </div>

          <Chart title="Jobs per trade" data={data.jobs_per_trade} x="skill" y="count" color="#f97316" />
          <LineBlock title="Acceptance rate over time" data={data.acceptance_over_time} />
          <Chart title="Language distribution" data={data.language_distribution} x="language" y="count" color="#0b1f3a" />

          <h2 className="mt-6 text-lg font-bold">Top 10 reliable workers</h2>
          <ul className="mt-2 space-y-2">
            {data.top_workers.map((w) => (
              <li key={w.id} className="rounded-xl bg-white p-3 text-sm shadow-sm">
                <span className="font-semibold">{w.name}</span> · {w.skill} · {w.area} · ★{w.reliability}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function Chart({ title, data, x, y, color }) {
  return (
    <div className="mt-6">
      <h2 className="mb-2 text-lg font-bold">{title}</h2>
      <div className="h-56 rounded-xl bg-white p-2 shadow-sm">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey={x} tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Bar dataKey={y} fill={color} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function LineBlock({ title, data }) {
  return (
    <div className="mt-6">
      <h2 className="mb-2 text-lg font-bold">{title}</h2>
      <div className="h-56 rounded-xl bg-white p-2 shadow-sm">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} />
            <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="rate" stroke="#f97316" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

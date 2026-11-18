import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { apiGet, apiPost } from '../api'

export default function Metrics({ onBack }) {
  const [data, setData] = useState(null)
  const [evalRes, setEvalRes] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const res = await apiGet('/api/metrics')
      setData(res)
      setEvalRes(res.eval_results || null)
      const er = await apiGet('/api/eval/results')
      if (er.results) setEvalRes(er.results)
    } catch (err) {
      setError(err.message || 'Failed to load metrics')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function runEval() {
    setRunning(true)
    setError('')
    try {
      await apiPost('/api/eval/run', {})
      setError('Evaluation started — refresh in ~1 min (LLM calls take time).')
      setTimeout(load, 5000)
    } catch (err) {
      setError(err.message)
    } finally {
      setRunning(false)
    }
  }

  const chartData = evalRes
    ? Object.keys(evalRes.regex?.per_field || {}).map((field) => ({
        field,
        Regex: Math.round((evalRes.regex.per_field[field] || 0) * 100),
        LLM: Math.round((evalRes.llm?.per_field?.[field] || 0) * 100),
      }))
    : []

  return (
    <div className="mx-auto max-w-lg px-4 py-6 pb-16">
      <button type="button" onClick={onBack} className="text-sm font-semibold text-orange-600">← Home</button>
      <h1 className="mt-2 text-3xl font-bold text-[#0b1f3a]">Demo metrics</h1>
      <p className="mt-1 text-sm text-slate-600">Built-in eval + LLM vs Regex baseline (Groq Llama)</p>

      <button
        type="button"
        onClick={runEval}
        disabled={running}
        className="mt-4 w-full rounded-xl bg-[#0b1f3a] py-3 font-semibold text-white disabled:opacity-50"
      >
        {running ? 'Starting…' : 'Run evaluation'}
      </button>

      {loading && <p className="mt-8 text-slate-500">Loading…</p>}
      {error && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{error}</p>}

      {data && (
        <div className="mt-6 grid grid-cols-1 gap-3">
          <Stat label="Quick extraction accuracy" value={`${(data.extraction_accuracy * 100).toFixed(1)}%`} hint="20-sample offline check" />
          <Stat label="Avg time-to-shortlist" value={`${data.avg_time_to_shortlist_ms} ms`} hint="match timings" />
          <Stat label="Match acceptance rate" value={`${(data.match_acceptance_rate * 100).toFixed(1)}%`} hint={`${data.total_accepts}/${data.total_alerts} Yes`} />
        </div>
      )}

      {evalRes && (
        <section className="mt-8">
          <h2 className="text-lg font-bold">LLM vs Regex (50 samples)</h2>
          <p className="text-xs text-slate-500">Model: {evalRes.model}</p>
          <div className="mt-3 h-64 w-full rounded-xl bg-white p-2 shadow-sm">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="field" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="Regex" fill="#0b1f3a" />
                <Bar dataKey="LLM" fill="#f97316" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <table className="mt-4 w-full text-left text-xs">
            <thead>
              <tr className="border-b">
                <th className="py-2">Metric</th>
                <th>Regex</th>
                <th>LLM</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(evalRes.regex?.per_field || {}).map((f) => (
                <tr key={f} className="border-b border-slate-100">
                  <td className="py-1">{f}</td>
                  <td>{((evalRes.regex.per_field[f] || 0) * 100).toFixed(1)}%</td>
                  <td>{((evalRes.llm?.per_field?.[f] || 0) * 100).toFixed(1)}%</td>
                </tr>
              ))}
              <tr>
                <td className="py-1 font-bold">Exact match</td>
                <td>{((evalRes.regex?.exact_match || 0) * 100).toFixed(1)}%</td>
                <td>{((evalRes.llm?.exact_match || 0) * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td className="py-1 font-bold">Avg latency</td>
                <td>{evalRes.regex?.avg_latency_ms?.toFixed?.(1) ?? '—'} ms</td>
                <td>{evalRes.llm?.avg_latency_ms?.toFixed?.(1) ?? '—'} ms</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-3xl font-bold text-[#0b1f3a]">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{hint}</div>
    </div>
  )
}

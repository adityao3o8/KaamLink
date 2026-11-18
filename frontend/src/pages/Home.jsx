export default function Home({ onNavigate }) {
  return (
    <div className="mx-auto flex min-h-[80vh] max-w-lg flex-col justify-center gap-5 px-4 py-10">
      <div className="text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-orange-600">KaamLink</p>
        <h1 className="mt-2 text-4xl font-bold text-[#0b1f3a]">Find work. Find workers.</h1>
        <p className="mt-3 text-slate-600">
          Voice-first matching powered by <strong>Groq (Whisper + Llama)</strong> · local multilingual embeddings.
        </p>
      </div>

      <button type="button" onClick={() => onNavigate('contractor')} className="rounded-2xl bg-[#0b1f3a] px-6 py-8 text-left text-white shadow-md">
        <div className="text-2xl font-bold">I need workers</div>
        <div className="mt-1 text-sm text-blue-100">Contractor — record a job & wave-alert shortlist</div>
      </button>

      <button type="button" onClick={() => onNavigate('worker')} className="rounded-2xl bg-orange-500 px-6 py-8 text-left text-white shadow-md">
        <div className="text-2xl font-bold">I need work</div>
        <div className="mt-1 text-sm text-orange-50">Worker — onboard with a voice note</div>
      </button>

      <div className="grid grid-cols-3 gap-2">
        <button type="button" onClick={() => onNavigate('ask')} className="rounded-xl border border-slate-300 bg-white/70 px-2 py-3 text-xs font-semibold">Ask KaamLink</button>
        <button type="button" onClick={() => onNavigate('metrics')} className="rounded-xl border border-slate-300 bg-white/70 px-2 py-3 text-xs font-semibold">Metrics</button>
        <button type="button" onClick={() => onNavigate('admin')} className="rounded-xl border border-slate-300 bg-white/70 px-2 py-3 text-xs font-semibold">Analytics</button>
      </div>
    </div>
  )
}

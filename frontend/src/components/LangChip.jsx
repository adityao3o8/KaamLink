const OPTS = [
  { id: 'auto', label: 'Auto' },
  { id: 'ta', label: 'Tamil' },
  { id: 'hi', label: 'Hindi' },
  { id: 'en', label: 'English' },
]

export default function LangChip({ value, onChange }) {
  return (
    <div className="flex flex-wrap gap-2">
      {OPTS.map((o) => (
        <button
          key={o.id}
          type="button"
          onClick={() => onChange(o.id)}
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${
            value === o.id
              ? 'border-orange-500 bg-orange-500 text-white'
              : 'border-slate-300 bg-white text-slate-700'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

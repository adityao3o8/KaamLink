const COLORS = {
  Hindi: 'bg-orange-100 text-orange-800 border-orange-300',
  Tamil: 'bg-blue-100 text-blue-900 border-blue-300',
  English: 'bg-slate-100 text-slate-800 border-slate-300',
}

export default function LanguageBadge({ language }) {
  const label = language || 'English'
  const cls = COLORS[label] || COLORS.English
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${cls}`}>
      {label}
    </span>
  )
}

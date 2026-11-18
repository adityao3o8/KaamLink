export default function DemoToggle({ on, setOn }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-600">
      <input
        type="checkbox"
        checked={on}
        onChange={(e) => setOn(e.target.checked)}
        className="h-4 w-4 accent-orange-500"
      />
      Demo mode (canned STT/LLM)
    </label>
  )
}

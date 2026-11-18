export default function MicButton({ recording, onToggle, disabled }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onToggle}
      className={`mx-auto flex h-28 w-28 items-center justify-center rounded-full text-white shadow-lg transition active:scale-95 disabled:opacity-50 ${
        recording
          ? 'animate-pulse bg-red-500'
          : 'bg-gradient-to-br from-orange-500 to-orange-600'
      }`}
      aria-label={recording ? 'Stop recording' : 'Start recording'}
    >
      <span className="text-4xl">{recording ? '⏹' : '🎤'}</span>
    </button>
  )
}

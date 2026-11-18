import { useCallback, useRef, useState } from 'react'

export function useRecorder() {
  const mediaRef = useRef(null)
  const chunksRef = useRef([])
  const [recording, setRecording] = useState(false)
  const [error, setError] = useState('')

  const start = useCallback(async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mime = MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/mp4'
      const recorder = new MediaRecorder(stream, { mimeType: mime })
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      mediaRef.current = recorder
      recorder.start()
      setRecording(true)
    } catch (err) {
      setError('Mic unavailable. Type your note instead.')
      setRecording(false)
    }
  }, [])

  const stop = useCallback(async () => {
    return new Promise((resolve) => {
      const recorder = mediaRef.current
      if (!recorder) {
        resolve(null)
        return
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        recorder.stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
        resolve(blob)
      }
      recorder.stop()
    })
  }, [])

  return { recording, error, start, stop, setError }
}

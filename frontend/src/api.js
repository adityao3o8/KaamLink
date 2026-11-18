async function parseError(res) {
  try {
    const data = await res.json()
    return data.detail || data.message || JSON.stringify(data)
  } catch {
    return res.statusText || 'Request failed'
  }
}

export async function apiGet(path) {
  const res = await fetch(path)
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function apiPost(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function apiUpload(path, file, extraFields = {}) {
  const form = new FormData()
  form.append('audio', file)
  Object.entries(extraFields).forEach(([k, v]) => form.append(k, String(v)))
  const res = await fetch(path, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function playTts(text, language = 'English') {
  const res = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  await audio.play()
}

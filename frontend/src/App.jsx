import { useState } from 'react'
import Home from './pages/Home'
import Contractor from './pages/Contractor'
import Worker from './pages/Worker'
import Metrics from './pages/Metrics'
import Ask from './pages/Ask'
import Admin from './pages/Admin'

export default function App() {
  const [page, setPage] = useState('home')

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-orange-200/60 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-lg items-center justify-between px-4 py-3">
          <button type="button" onClick={() => setPage('home')} className="text-lg font-extrabold tracking-tight">
            <span className="text-orange-500">Kaam</span>
            <span className="text-[#0b1f3a]">Link</span>
          </button>
          <nav className="flex flex-wrap justify-end gap-2 text-[11px] font-semibold text-slate-600">
            <button type="button" onClick={() => setPage('contractor')}>Contractor</button>
            <button type="button" onClick={() => setPage('worker')}>Worker</button>
            <button type="button" onClick={() => setPage('ask')}>Ask</button>
            <button type="button" onClick={() => setPage('metrics')}>Metrics</button>
            <button type="button" onClick={() => setPage('admin')}>Admin</button>
          </nav>
        </div>
      </header>

      {page === 'home' && <Home onNavigate={setPage} />}
      {page === 'contractor' && <Contractor onBack={() => setPage('home')} />}
      {page === 'worker' && <Worker onBack={() => setPage('home')} />}
      {page === 'ask' && <Ask onBack={() => setPage('home')} />}
      {page === 'metrics' && <Metrics onBack={() => setPage('home')} />}
      {page === 'admin' && <Admin onBack={() => setPage('home')} />}
    </div>
  )
}

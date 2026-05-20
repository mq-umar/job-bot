import React, { useState, useEffect } from 'react'
import { Plus, X, Clock } from 'lucide-react'

const COLUMNS = ['Applied', 'Phone Screen', 'Interview', 'Offer', 'Rejected', 'Accepted']
const COL_COLORS = {
  'Applied': 'border-blue-500/40',
  'Phone Screen': 'border-yellow-500/40',
  'Interview': 'border-primary/40',
  'Offer': 'border-success/40',
  'Rejected': 'border-error/40',
  'Accepted': 'border-success/60',
}
const STORAGE_KEY = 'interview_tracker'

function Card({ card, onMove, onDelete, columns }) {
  const daysSince = Math.floor((Date.now() - new Date(card.added)) / 86400000)
  const stale = card.column === 'Applied' && daysSince >= 7

  return (
    <div className={`bg-[#0f1117] border rounded-xl p-3 space-y-2 ${stale ? 'border-yellow-500/40' : 'border-[#2a2d3e]'}`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-200 text-sm">{card.company}</p>
          <p className="text-xs text-slate-400">{card.title}</p>
        </div>
        <button onClick={() => onDelete(card.id)} className="text-slate-600 hover:text-red-400 transition-colors shrink-0"><X size={12} /></button>
      </div>
      {stale && (
        <div className="flex items-center gap-1.5 text-xs text-yellow-400">
          <Clock size={12} /> No updates in {daysSince} days
        </div>
      )}
      <select value={card.column} onChange={e => onMove(card.id, e.target.value)}
        className="w-full bg-[#1a1d27] border border-[#2a2d3e] rounded-lg px-2 py-1 text-xs text-slate-300 focus:outline-none">
        {columns.map(c => <option key={c} value={c}>{c}</option>)}
      </select>
      {card.notes && <p className="text-xs text-slate-500 italic">{card.notes}</p>}
    </div>
  )
}

export default function InterviewTracker() {
  const [cards,   setCards]   = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') } catch { return [] }
  })
  const [showAdd, setShowAdd] = useState(false)
  const [form,    setForm]    = useState({ company: '', title: '', notes: '', column: 'Applied' })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cards))
  }, [cards])

  const addCard = () => {
    if (!form.company.trim()) return
    setCards(c => [...c, { ...form, id: Date.now(), added: new Date().toISOString() }])
    setForm({ company: '', title: '', notes: '', column: 'Applied' })
    setShowAdd(false)
  }

  const moveCard = (id, column) => setCards(c => c.map(x => x.id === id ? { ...x, column } : x))
  const delCard  = (id) => { if (confirm('Remove this card?')) setCards(c => c.filter(x => x.id !== id)) }

  const staleCount = cards.filter(c => c.column === 'Applied' && Math.floor((Date.now() - new Date(c.added)) / 86400000) >= 7).length

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Interview Tracker</h1>
          <p className="text-slate-400 text-sm">{cards.length} applications tracked</p>
        </div>
        <button onClick={() => setShowAdd(true)} className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg text-sm font-medium transition-colors">
          <Plus size={16} /> Add Card
        </button>
      </div>

      {staleCount > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl px-4 py-3 flex items-center gap-3">
          <Clock size={16} className="text-yellow-400 shrink-0" />
          <p className="text-sm text-yellow-300">
            {staleCount} application{staleCount > 1 ? 's' : ''} in "Applied" with no updates for 7+ days.
            Consider following up.
          </p>
        </div>
      )}

      {showAdd && (
        <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4 space-y-3">
          <p className="font-medium text-slate-200 text-sm">New Application</p>
          <div className="grid grid-cols-2 gap-3">
            {[['company','Company *'],['title','Job Title']].map(([k,l]) => (
              <input key={k} value={form[k]} onChange={e => setForm(f => ({...f,[k]:e.target.value}))}
                className="bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary"
                placeholder={l} />
            ))}
          </div>
          <input value={form.notes} onChange={e => setForm(f => ({...f, notes: e.target.value}))}
            className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary"
            placeholder="Notes (optional)" />
          <div className="flex gap-3">
            <button onClick={() => setShowAdd(false)} className="flex-1 py-2 border border-[#2a2d3e] rounded-lg text-sm text-slate-400">Cancel</button>
            <button onClick={addCard} className="flex-1 py-2 bg-primary text-white rounded-lg text-sm font-medium">Add</button>
          </div>
        </div>
      )}

      {/* Kanban board */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {COLUMNS.map(col => {
          const colCards = cards.filter(c => c.column === col)
          return (
            <div key={col} className={`bg-[#1a1d27] border-t-2 ${COL_COLORS[col]} rounded-xl overflow-hidden`}>
              <div className="px-3 py-2.5 border-b border-[#2a2d3e] flex items-center justify-between">
                <span className="text-xs font-medium text-slate-300">{col}</span>
                <span className="text-xs text-slate-500 bg-[#0f1117] px-1.5 py-0.5 rounded-full">{colCards.length}</span>
              </div>
              <div className="p-2 space-y-2 min-h-24">
                {colCards.map(c => <Card key={c.id} card={c} onMove={moveCard} onDelete={delCard} columns={COLUMNS} />)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

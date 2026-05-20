import React, { useState, useEffect } from 'react'
import { Search, Plus, Trash2, ExternalLink, RefreshCw } from 'lucide-react'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'

export default function JobQueue() {
  const [jobs,   setJobs]   = useState([])
  const [search, setSearch] = useState('')
  const [adding, setAdding] = useState(false)
  const [newUrl, setNewUrl] = useState('')
  const [loading,setLoading]= useState(true)

  const load = () => {
    setLoading(true)
    api.getQueue().then(j => { setJobs(j); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const filtered = jobs.filter(j =>
    !search || [j.company, j.title, j.url].some(v => (v||'').toLowerCase().includes(search.toLowerCase()))
  )

  const addJob = async () => {
    if (!newUrl.trim()) return
    try {
      await api.addJob({ url: newUrl.trim() })
      setNewUrl('')
      setAdding(false)
      load()
    } catch (e) { alert(e.message) }
  }

  const del = async (id) => {
    if (!confirm('Remove this job?')) return
    await api.deleteJob(id)
    setJobs(j => j.filter(x => x.id !== id))
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Job Queue</h1>
          <p className="text-slate-400 text-sm">{jobs.length} jobs in queue</p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="p-2 rounded-lg border border-[#2a2d3e] text-slate-400 hover:text-slate-100 transition-colors"><RefreshCw size={16} /></button>
          <button onClick={() => setAdding(true)} className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg text-sm font-medium transition-colors">
            <Plus size={16} /> Add Job
          </button>
        </div>
      </div>

      {adding && (
        <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4 flex gap-3">
          <input value={newUrl} onChange={e => setNewUrl(e.target.value)} onKeyDown={e => e.key === 'Enter' && addJob()}
            className="flex-1 bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary"
            placeholder="Paste job URL here…" autoFocus />
          <button onClick={addJob} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium">Add</button>
          <button onClick={() => setAdding(false)} className="px-4 py-2 border border-[#2a2d3e] text-slate-400 rounded-lg text-sm">Cancel</button>
        </div>
      )}

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
        <input value={search} onChange={e => setSearch(e.target.value)}
          className="w-full bg-[#1a1d27] border border-[#2a2d3e] rounded-xl pl-9 pr-4 py-2.5 text-sm text-slate-100 focus:outline-none focus:border-primary"
          placeholder="Search company, title, URL…" />
      </div>

      <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#2a2d3e]">
              {['ID','Company','Title','Priority','Notes',''].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs text-slate-500 font-medium uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#2a2d3e]">
            {loading
              ? <tr><td colSpan={6} className="text-center py-12 text-slate-500">Loading…</td></tr>
              : filtered.length === 0
              ? <tr><td colSpan={6} className="text-center py-12 text-slate-500">No jobs found</td></tr>
              : filtered.map(j => (
                <tr key={j.id} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 text-slate-500 font-mono">{j.id}</td>
                  <td className="px-4 py-3 text-slate-200 font-medium">{j.company || '—'}</td>
                  <td className="px-4 py-3 text-slate-300">{j.title || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${j.priority === 'HIGH' ? 'bg-red-500/20 text-red-400' : j.priority === 'LOW' ? 'bg-slate-500/20 text-slate-400' : 'bg-blue-500/20 text-blue-400'}`}>{j.priority || 'MED'}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs max-w-xs truncate">{j.notes}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <a href={j.url} target="_blank" rel="noreferrer" className="p-1.5 text-slate-500 hover:text-primary rounded transition-colors"><ExternalLink size={14} /></a>
                      <button onClick={() => del(j.id)} className="p-1.5 text-slate-500 hover:text-red-400 rounded transition-colors"><Trash2 size={14} /></button>
                    </div>
                  </td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>
    </div>
  )
}

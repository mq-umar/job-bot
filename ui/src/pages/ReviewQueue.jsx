import React, { useState, useEffect } from 'react'
import { ExternalLink, Trash2, RefreshCw, ShieldAlert } from 'lucide-react'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'

const FIT_COLORS = {
  'Strong Fit': 'text-green-400', 'Good Fit': 'text-emerald-400',
  'Possible Fit': 'text-blue-400', 'Stretch': 'text-yellow-400', 'Low Fit': 'text-red-400',
}

export default function ReviewQueue() {
  const [items,    setItems]    = useState([])
  const [profiles, setProfiles] = useState([])
  const [profile,  setProfile]  = useState('')
  const [loading,  setLoading]  = useState(true)

  const load = () => {
    setLoading(true)
    api.getReviewQueue(profile || undefined)
      .then(data => { setItems(data.reverse()); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    api.listProfiles().then(ps => {
      setProfiles(ps)
    }).catch(() => {})
  }, [])

  useEffect(() => { load() }, [profile])

  const dismiss = async (item) => {
    if (!confirm(`Dismiss review for ${item.company} — ${item.title}?`)) return
    try {
      await api.dismissReview(item.job_url, item.profile || undefined)
      setItems(prev => prev.filter(i => i.job_url !== item.job_url || i.profile !== item.profile))
    } catch (e) { alert(e.message) }
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Review Queue</h1>
          <p className="text-slate-400 text-sm">
            {items.length} application{items.length !== 1 ? 's' : ''} flagged for human review
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <select value={profile} onChange={e => setProfile(e.target.value)}
            className="bg-[#1a1d27] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-300">
            <option value="">All profiles</option>
            {profiles.map(p => (
              <option key={p.name || p.first_name} value={p.name || p.first_name?.toLowerCase()}>
                {p.full_name || p.first_name}
              </option>
            ))}
          </select>
          <button onClick={load} className="p-2 rounded-lg border border-[#2a2d3e] text-slate-400 hover:text-slate-100 transition-colors">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {!loading && items.length === 0 && (
        <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-12 text-center">
          <ShieldAlert size={32} className="text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">No applications pending review</p>
          <p className="text-slate-600 text-sm mt-1">Applications with sensitive fields will appear here</p>
        </div>
      )}

      <div className="space-y-3">
        {loading
          ? <div className="text-center py-12 text-slate-500">Loading…</div>
          : items.map((item, i) => (
          <div key={i} className="bg-[#1a1d27] border border-yellow-500/30 rounded-xl p-5">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {/* Header row */}
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-slate-100">{item.company || '—'}</span>
                  <span className="text-slate-500">—</span>
                  <span className="text-slate-300">{item.title || '—'}</span>
                  {item.fit_label && (
                    <span className={`text-xs font-medium ${FIT_COLORS[item.fit_label] || 'text-slate-400'}`}>
                      {item.fit_label}
                    </span>
                  )}
                  {item.score && (
                    <span className="text-xs text-slate-500">score: {item.score}</span>
                  )}
                  {item.profile && (
                    <span className="text-xs bg-[#0f1117] border border-[#2a2d3e] px-2 py-0.5 rounded-full text-slate-400 capitalize">
                      {item.profile}
                    </span>
                  )}
                </div>

                {/* Meta */}
                <div className="flex gap-3 mt-1.5 text-xs text-slate-500 flex-wrap">
                  {item.timestamp && <span>{item.timestamp}</span>}
                  {item.platform && <span className="capitalize">{item.platform}</span>}
                  {item.resume && <span className="truncate max-w-[200px]">{item.resume}</span>}
                </div>

                {/* Review reasons */}
                {item.review_reasons?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.review_reasons.map((r, j) => (
                      <span key={j} className="flex items-center gap-1.5 bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs px-2.5 py-1 rounded-full">
                        <ShieldAlert size={11} />
                        {r}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-1.5 shrink-0">
                {item.job_url && (
                  <a href={item.job_url} target="_blank" rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-[#2a2d3e] text-slate-400 hover:text-slate-100 rounded-lg transition-colors">
                    <ExternalLink size={12} /> View Job
                  </a>
                )}
                <button onClick={() => dismiss(item)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-red-500/30 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                  <Trash2 size={12} /> Dismiss
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

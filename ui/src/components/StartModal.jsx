import React, { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { api } from '../api'

export default function StartModal({ onClose, onStart }) {
  const [profiles, setProfiles] = useState([])
  const [cfg, setCfg] = useState({
    profile: 'muhammad', mode: 'auto', limit: 25,
    discover: true, companies_only: false, tier_max: 3,
    min_score: 0, dry_run: false, start_id: 1,
  })

  useEffect(() => {
    api.listProfiles().then(ps => {
      setProfiles(ps)
      if (ps.length > 0) setCfg(c => ({ ...c, profile: ps[0].name || ps[0].first_name?.toLowerCase() }))
    }).catch(() => {})
  }, [])

  const set = (k, v) => setCfg(c => ({ ...c, [k]: v }))

  const FIT_LABELS = { 0: 'Disabled', 0.05: 'Low Fit only', 0.15: 'Stretch+', 0.3: 'Possible+', 0.45: 'Good+' }
  const fitLabel = FIT_LABELS[cfg.min_score] || `${cfg.min_score}`

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-2xl w-full max-w-md p-6 shadow-2xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-slate-100">Configure Session</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300"><X size={18} /></button>
        </div>

        <div className="space-y-5">
          {/* Profile */}
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Profile</label>
            <div className="flex gap-2 flex-wrap">
              {(profiles.length ? profiles.map(p => p.name || p.first_name?.toLowerCase()) : ['muhammad', 'razia']).map(p => (
                <button key={p} onClick={() => set('profile', p)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${cfg.profile === p ? 'bg-primary text-white' : 'bg-[#0f1117] border border-[#2a2d3e] text-slate-400 hover:text-slate-100'}`}>
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Mode */}
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Mode</label>
            <div className="flex gap-2">
              {[['auto', 'Auto (no prompts)'], ['review', 'Review each job']].map(([v, l]) => (
                <button key={v} onClick={() => set('mode', v)}
                  className={`flex-1 py-2 rounded-lg text-sm transition-colors ${cfg.mode === v ? 'bg-primary text-white' : 'bg-[#0f1117] border border-[#2a2d3e] text-slate-400 hover:text-slate-100'}`}>
                  {l}
                </button>
              ))}
            </div>
          </div>

          {/* Limit */}
          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1.5">
              <label>Session limit</label><span className="text-slate-300 font-medium">{cfg.limit} jobs</span>
            </div>
            <input type="range" min={1} max={100} value={cfg.limit} onChange={e => set('limit', +e.target.value)}
              className="w-full accent-primary" />
          </div>

          {/* Toggles */}
          {[
            ['discover', 'Discover new jobs from resumes'],
            ['dry_run',  "Dry run (don't actually submit)"],
          ].map(([k, label]) => (
            <div key={k} className="flex items-center justify-between">
              <span className="text-sm text-slate-300">{label}</span>
              <button onClick={() => set(k, !cfg[k])}
                className={`w-11 h-6 rounded-full transition-colors relative ${cfg[k] ? 'bg-primary' : 'bg-[#2a2d3e]'}`}>
                <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${cfg[k] ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
            </div>
          ))}

          {/* Min score */}
          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1.5">
              <label>Min score threshold</label><span className="text-slate-300 font-medium">{fitLabel}</span>
            </div>
            <input type="range" min={0} max={0.45} step={0.05} value={cfg.min_score} onChange={e => set('min_score', +e.target.value)}
              className="w-full accent-primary" />
          </div>

          {/* Tier max — only relevant when discover is on */}
          {cfg.discover && (
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Discovery sources</label>
              <div className="flex gap-2 flex-wrap">
                {[[1,'Indeed'],[2,'+LinkedIn'],[3,'+Google'],[4,'+ATS boards']].map(([v, l]) => (
                  <button key={v} onClick={() => set('tier_max', v)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${cfg.tier_max === v ? 'bg-primary text-white' : 'bg-[#0f1117] border border-[#2a2d3e] text-slate-400 hover:text-slate-100'}`}>
                    {l}
                  </button>
                ))}
              </div>
              <p className="text-xs text-slate-500 mt-1">Only open-apply platforms — no account creation needed</p>
            </div>
          )}

          {/* Start ID (advanced) */}
          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-1.5">
              <label>Skip job IDs below</label>
              <span className="text-slate-300 font-medium">#{cfg.start_id}</span>
            </div>
            <input type="range" min={1} max={500} step={1} value={cfg.start_id} onChange={e => set('start_id', +e.target.value)}
              className="w-full accent-primary" />
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 py-2.5 border border-[#2a2d3e] rounded-lg text-sm text-slate-400 hover:text-slate-100 transition-colors">Cancel</button>
          <button onClick={() => onStart(cfg)} className="flex-1 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium text-sm transition-colors">
            Start Bot
          </button>
        </div>
      </div>
    </div>
  )
}

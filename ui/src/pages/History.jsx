import React, { useState, useEffect } from 'react'
import { Download, ExternalLink } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'

export default function History() {
  const [history,      setHistory]      = useState([])
  const [profile,      setProfile]      = useState('')
  const [profiles,     setProfiles]     = useState([])
  const [stats,        setStats]        = useState({})
  const [chartData,    setChartData]    = useState([])
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    api.listProfiles().then(ps => {
      setProfiles(ps)
      if (ps.length) setProfile(ps[0].name || ps[0].first_name?.toLowerCase() || '')
    }).catch(() => {})
  }, [])

  useEffect(() => {
    api.getHistory(profile || undefined, statusFilter || undefined).then(rows => {
      setHistory(rows)
      // Build last-7-days chart
      const days = {}
      for (let i = 6; i >= 0; i--) {
        const d = new Date(); d.setDate(d.getDate() - i)
        days[d.toISOString().split('T')[0]] = 0
      }
      rows.forEach(r => {
        const d = (r.timestamp || '').split(' ')[0]
        if (d in days) days[d]++
      })
      setChartData(Object.entries(days).map(([date, count]) => ({
        date: date.slice(5), count,
      })))
    }).catch(() => {})
    api.getStats(profile || undefined).then(setStats).catch(() => {})
  }, [profile, statusFilter])

  const exportCSV = () => {
    const header = Object.keys(history[0] || {}).join(',')
    const rows   = history.map(r => Object.values(r).map(v => `"${v}"`).join(','))
    const blob   = new Blob([[header, ...rows].join('\n')], { type: 'text/csv' })
    const url    = URL.createObjectURL(blob)
    const a      = document.createElement('a'); a.href = url; a.download = `history_${profile}.csv`; a.click()
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">History</h1>
          <p className="text-slate-400 text-sm">{history.length} applications recorded</p>
        </div>
        <div className="flex gap-2 items-center">
          <select value={profile} onChange={e => setProfile(e.target.value)}
            className="bg-[#1a1d27] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-300">
            <option value="">All profiles</option>
            {profiles.map(p => <option key={p.name || p.first_name} value={p.name || p.first_name?.toLowerCase()}>{p.full_name || p.first_name}</option>)}
          </select>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="bg-[#1a1d27] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-300">
            <option value="">All statuses</option>
            <option value="submitted">Submitted</option>
            <option value="submitted_manually">Submitted manually</option>
            <option value="submit_failed">Submit failed</option>
            <option value="error">Error</option>
            <option value="button_not_found">Button not found</option>
            <option value="dry_run">Dry run</option>
            <option value="skipped_manual">Skipped (manual)</option>
            <option value="skipped_low_fit">Skipped (low fit)</option>
            <option value="closed">Closed</option>
          </select>
          <button onClick={exportCSV} disabled={!history.length} className="flex items-center gap-2 px-4 py-2 border border-[#2a2d3e] text-slate-300 hover:text-slate-100 rounded-lg text-sm transition-colors disabled:opacity-40">
            <Download size={14} /> Export
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          ['Total', stats.total || 0, 'text-slate-100'],
          ['Submitted', (stats.by_status?.submitted || 0) + (stats.by_status?.submitted_manually || 0), 'text-success'],
          ['Failed', (stats.by_status?.submit_failed || 0) + (stats.by_status?.error || 0), 'text-error'],
          ['Skipped', (stats.by_status?.skipped_manual || 0) + (stats.by_status?.skipped_low_fit || 0), 'text-slate-400'],
        ].map(([l, v, c]) => (
          <div key={l} className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4">
            <p className="text-xs text-slate-500 uppercase tracking-wide">{l}</p>
            <p className={`text-2xl font-bold mt-1 ${c}`}>{v}</p>
          </div>
        ))}
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4">
          <p className="text-sm font-medium text-slate-300 mb-4">Applications — Last 7 Days</p>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={chartData}>
              <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#1a1d27', border: '1px solid #2a2d3e', borderRadius: 8 }} labelStyle={{ color: '#f1f5f9' }} />
              <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table */}
      <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl overflow-hidden overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#2a2d3e]">
              {['Time','Company','Title','Resume','Score','Fit','Status','Method',''].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs text-slate-500 font-medium uppercase tracking-wide whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#2a2d3e]">
            {history.length === 0
              ? <tr><td colSpan={9} className="text-center py-12 text-slate-500">No applications recorded yet</td></tr>
              : history.slice(0, 200).map((r, i) => (
                <tr key={i} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">{(r.timestamp||'').slice(0,16)}</td>
                  <td className="px-4 py-3 text-slate-200 font-medium whitespace-nowrap">{r.company||'—'}</td>
                  <td className="px-4 py-3 text-slate-300 max-w-xs truncate">{r.title||'—'}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap truncate max-w-[140px]">{r.selected_resume||'—'}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{r.resume_score||'—'}</td>
                  <td className="px-4 py-3"><StatusBadge type="fit" value={r.fit_label||'—'} /></td>
                  <td className="px-4 py-3"><StatusBadge type="status" value={r.status||'—'} /></td>
                  <td className="px-4 py-3 text-xs text-slate-500">{r.apply_method||'—'}</td>
                  <td className="px-4 py-3">
                    {r.job_url && <a href={r.job_url} target="_blank" rel="noreferrer" className="text-slate-500 hover:text-primary transition-colors"><ExternalLink size={14} /></a>}
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

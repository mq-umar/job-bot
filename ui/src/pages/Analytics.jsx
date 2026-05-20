import React, { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts'
import { api } from '../api'

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#94a3b8']
const FIT_ORDER = ['Strong Fit', 'Good Fit', 'Possible Fit', 'Stretch', 'Low Fit']

export default function Analytics() {
  const [data, setData] = useState({ total: 0, by_status: {}, by_fit: {} })
  const [history, setHistory] = useState([])
  const [lineData, setLineData] = useState([])
  const [resumeData, setResumeData] = useState([])

  useEffect(() => {
    api.getStats().then(setData).catch(() => {})
    api.getHistory().then(rows => {
      setHistory(rows)

      // Line chart: last 30 days
      const days = {}
      for (let i = 29; i >= 0; i--) {
        const d = new Date(); d.setDate(d.getDate() - i)
        days[d.toISOString().split('T')[0]] = 0
      }
      rows.forEach(r => { const d = (r.timestamp||'').split(' ')[0]; if (d in days) days[d]++ })
      setLineData(Object.entries(days).map(([date, count]) => ({ date: date.slice(5), count })))

      // Resume usage
      const resumeMap = {}
      rows.forEach(r => {
        const fn = r.selected_resume; if (!fn) return
        if (!resumeMap[fn]) resumeMap[fn] = { filename: fn, count: 0, scores: [] }
        resumeMap[fn].count++
        const s = parseFloat(r.resume_score); if (s > 0) resumeMap[fn].scores.push(s)
      })
      setResumeData(
        Object.values(resumeMap)
          .sort((a, b) => b.count - a.count)
          .slice(0, 10)
          .map(r => ({ ...r, avg: r.scores.length ? +(r.scores.reduce((a,b)=>a+b,0)/r.scores.length).toFixed(3) : 0 }))
      )
    }).catch(() => {})
  }, [])

  const fitData = FIT_ORDER.map(k => ({ name: k, value: data.by_fit[k] || 0 })).filter(d => d.value > 0)
  const sourceData = [
    { name: 'Company Pages', value: history.filter(r => r.source === 'direct_company').length },
    { name: 'Indeed',        value: history.filter(r => r.source === 'indeed').length },
    { name: 'LinkedIn',      value: history.filter(r => r.source === 'linkedin').length },
    { name: 'Google Jobs',   value: history.filter(r => r.source === 'google_jobs').length },
    { name: 'Manual/CSV',    value: history.filter(r => !r.source || r.source === 'csv').length },
  ].filter(d => d.value > 0)

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Analytics</h1>
        <p className="text-slate-400 text-sm">Insights from {data.total} total applications</p>
      </div>

      {/* Top stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          ['Total Applied', data.total, 'text-slate-100'],
          ['Submitted',     data.by_status?.submitted || 0, 'text-success'],
          ['Failed',        (data.by_status?.submit_failed||0)+(data.by_status?.error||0), 'text-error'],
          ['Most Used Resume', resumeData[0]?.filename?.split('_').slice(0,2).join(' ') || '—', 'text-primary text-sm'],
        ].map(([l,v,c]) => (
          <div key={l} className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4">
            <p className="text-xs text-slate-500 uppercase tracking-wide">{l}</p>
            <p className={`text-xl font-bold mt-1 ${c}`}>{v}</p>
          </div>
        ))}
      </div>

      {/* Line chart */}
      <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-5">
        <p className="font-medium text-slate-200 mb-4">Applications — Last 30 Days</p>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={lineData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3e" />
            <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} interval={4} />
            <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: '#1a1d27', border: '1px solid #2a2d3e', borderRadius: 8 }} labelStyle={{ color: '#f1f5f9' }} />
            <Line type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Fit label donut */}
        {fitData.length > 0 && (
          <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-5">
            <p className="font-medium text-slate-200 mb-4">By Fit Label</p>
            <div className="flex items-center gap-6">
              <PieChart width={130} height={130}>
                <Pie data={fitData} cx={60} cy={60} innerRadius={35} outerRadius={60} dataKey="value">
                  {fitData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
              </PieChart>
              <div className="space-y-1.5">
                {fitData.map((d, i) => (
                  <div key={d.name} className="flex items-center gap-2 text-sm">
                    <div className="w-3 h-3 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                    <span className="text-slate-400">{d.name}</span>
                    <span className="text-slate-200 ml-auto font-medium">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Source bar */}
        {sourceData.length > 0 && (
          <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-5">
            <p className="font-medium text-slate-200 mb-4">By Source</p>
            <ResponsiveContainer width="100%" height={130}>
              <BarChart data={sourceData} layout="vertical">
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} width={100} />
                <Tooltip contentStyle={{ background: '#1a1d27', border: '1px solid #2a2d3e', borderRadius: 8 }} labelStyle={{ color: '#f1f5f9' }} />
                <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Resume performance table */}
      {resumeData.length > 0 && (
        <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#2a2d3e]"><p className="font-medium text-slate-200">Resume Performance</p></div>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-[#2a2d3e]">
              {['Resume','Times Selected','Avg Score'].map(h => <th key={h} className="px-4 py-3 text-left text-xs text-slate-500 uppercase tracking-wide">{h}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-[#2a2d3e]">
              {resumeData.map(r => (
                <tr key={r.filename} className="hover:bg-white/5 transition-colors">
                  <td className="px-4 py-3 text-slate-300 text-xs">{r.filename}</td>
                  <td className="px-4 py-3 text-slate-200 font-medium">{r.count}</td>
                  <td className="px-4 py-3 text-slate-400">{r.avg || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Play, Square, Pause, CheckCircle, XCircle, AlertTriangle, Loader, Zap } from 'lucide-react'
import { api } from '../api'
import StartModal from '../components/StartModal'
import StatusBadge from '../components/StatusBadge'

const FIT_COLORS = {
  'Strong Fit': 'text-green-400', 'Good Fit': 'text-emerald-400',
  'Possible Fit': 'text-blue-400', 'Stretch': 'text-yellow-400', 'Low Fit': 'text-red-400',
}

const JOB_RESULT_SUCCESS = new Set(['submitted', 'submitted_manually'])
const JOB_RESULT_FAIL    = new Set(['error', 'submit_failed'])

function LogEntry({ entry }) {
  let borderColor = 'border-[#2a2d3e]'
  if (entry.level === 'error')                           borderColor = 'border-red-500'
  else if (entry.type === 'captcha')                     borderColor = 'border-yellow-500'
  else if (entry.type === 'job_result') {
    const s = entry.data?.status || ''
    if (JOB_RESULT_SUCCESS.has(s))                       borderColor = 'border-green-500'
    else if (JOB_RESULT_FAIL.has(s))                     borderColor = 'border-red-400'
    else                                                  borderColor = 'border-slate-600'
  }
  else if (entry.type === 'job_done')                    borderColor = 'border-primary/50'

  const textColor = entry.level === 'error'   ? 'text-red-400'
    : entry.level === 'warning'               ? 'text-yellow-400'
    : entry.type  === 'job_result' && entry.data?.status && JOB_RESULT_SUCCESS.has(entry.data.status) ? 'text-green-400'
    : entry.type  === 'job_result' && entry.data?.status && JOB_RESULT_FAIL.has(entry.data.status)    ? 'text-red-400'
    : 'text-slate-300'

  return (
    <div className={`border-l-2 ${borderColor} pl-3 py-1.5`}>
      <div className="flex items-start gap-2">
        <span className="text-slate-500 text-xs shrink-0 font-mono mt-0.5">{entry.timestamp}</span>
        <span className={`text-sm ${textColor}`}>{entry.message}</span>
      </div>
      {entry.data && (entry.data.company || entry.data.fit_label) && (
        <div className="flex gap-2 mt-0.5 ml-14">
          {entry.data.company  && <span className="text-xs text-slate-500">{entry.data.company}</span>}
          {entry.data.fit_label && <span className={`text-xs ${FIT_COLORS[entry.data.fit_label] || 'text-slate-400'}`}>{entry.data.fit_label}</span>}
          {entry.data.score    && <span className="text-xs text-slate-600">score: {entry.data.score}</span>}
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [botStatus,   setBotStatus]   = useState({ status: 'idle', jobs_applied: 0, jobs_total: 0 })
  const [logs,        setLogs]        = useState([])
  const [showStart,   setShowStart]   = useState(false)
  const [captchaJob,  setCaptchaJob]  = useState(null)
  const [reviewJob,   setReviewJob]   = useState(null)
  const [todayCount,    setTodayCount]    = useState(0)
  const [weekCount,     setWeekCount]     = useState(0)
  const [successRate,   setSuccessRate]   = useState(0)
  const [reviewCount,   setReviewCount]   = useState(0)
  const wsRef   = useRef(null)
  const logEnd  = useRef(null)

  const connectWS = useCallback(() => {
    const token = localStorage.getItem('bot_token') || ''
    const ws = new WebSocket(`ws://${window.location.host}/ws/logs?token=${encodeURIComponent(token)}`)
    ws.onmessage = (e) => {
      try {
        const entry = JSON.parse(e.data)
        setLogs(prev => [...prev.slice(-999), entry])
        if (entry.type === 'captcha') setCaptchaJob(entry.data)
        if (entry.type === 'review')  setReviewJob(entry.data)
        if (entry.type === 'session_end' || entry.type === 'summary') {
          setBotStatus(prev => ({ ...prev, status: 'idle' }))
          setCaptchaJob(null)
        }
      } catch {}
    }
    ws.onclose = () => { setTimeout(connectWS, 2000) }
    wsRef.current = ws
    return ws
  }, [])

  useEffect(() => {
    const ws = connectWS()
    const interval = setInterval(() => {
      api.botStatus().then(setBotStatus).catch(() => {})
    }, 2000)

    // Load stats
    const today = new Date().toISOString().split('T')[0]
    api.getHistory()
      .then(rows => {
        const todayRows = rows.filter(r => (r.timestamp || '').startsWith(today))
        const weekAgo   = new Date(); weekAgo.setDate(weekAgo.getDate() - 7)
        const weekRows  = rows.filter(r => new Date(r.timestamp) >= weekAgo)
        setTodayCount(todayRows.length)
        setWeekCount(weekRows.length)
        const submitted = rows.filter(r => r.status === 'submitted' || r.status === 'submitted_manually').length
        setSuccessRate(rows.length > 0 ? Math.round((submitted / rows.length) * 100) : 0)
      })
      .catch(() => {})
    api.getReviewQueue().then(q => setReviewCount(q.length)).catch(() => {})

    return () => {
      clearInterval(interval)
      ws.close()
    }
  }, [connectWS])

  useEffect(() => {
    logEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const handleStart = async (cfg) => {
    setShowStart(false)
    setLogs([])
    await api.botStart(cfg)
    setBotStatus(prev => ({ ...prev, status: 'running' }))
  }

  const handleStop = async () => {
    await api.botStop()
    setBotStatus(prev => ({ ...prev, status: 'stopped' }))
  }

  const handlePause = async () => {
    const res = await api.botPause()
    setBotStatus(prev => ({ ...prev, status: res.status }))
  }

  const isRunning = botStatus.status === 'running'
  const isPaused  = botStatus.status === 'paused'

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
          <p className="text-slate-400 text-sm">Monitor and control your job applications</p>
        </div>
        <div className="flex items-center gap-2">
          {(isRunning || isPaused) ? (
            <>
              <button onClick={handlePause} className="flex items-center gap-2 px-4 py-2 bg-[#1a1d27] border border-[#2a2d3e] rounded-lg text-sm text-slate-300 hover:text-slate-100 transition-colors">
                {isPaused ? <Play size={14} /> : <Pause size={14} />}
                {isPaused ? 'Resume' : 'Pause'}
              </button>
              <button onClick={handleStop} className="flex items-center gap-2 px-4 py-2 bg-red-500/20 border border-red-500/40 rounded-lg text-sm text-red-400 hover:bg-red-500/30 transition-colors">
                <Square size={14} /> Stop
              </button>
            </>
          ) : (
            <button onClick={() => setShowStart(true)} className="flex items-center gap-2 px-6 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium transition-colors">
              <Zap size={16} /> Start Bot
            </button>
          )}
        </div>
      </div>

      {/* CAPTCHA alert */}
      {captchaJob && (
        <div className="bg-yellow-500/10 border border-yellow-500/40 rounded-xl p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertTriangle size={20} className="text-yellow-400 shrink-0" />
            <div>
              <p className="font-medium text-yellow-300">CAPTCHA required</p>
              <p className="text-sm text-yellow-400/80">
                {captchaJob.company ? `${captchaJob.company} — ${captchaJob.title}` : 'Solve it in the browser window'}
              </p>
            </div>
          </div>
          <button onClick={() => { api.captchaDone(); setCaptchaJob(null) }}
            className="px-4 py-2 bg-yellow-500 hover:bg-yellow-400 text-black rounded-lg text-sm font-medium transition-colors">
            Mark as Solved
          </button>
        </div>
      )}

      {/* Review mode card */}
      {reviewJob && (
        <div className="bg-[#1a1d27] border border-primary/40 rounded-xl p-4">
          <p className="font-medium text-slate-100 mb-1">Review: {reviewJob.company} — {reviewJob.title}</p>
          <p className="text-sm text-slate-400 mb-3">Approve or skip this application</p>
          <div className="flex gap-2">
            {[['y','Apply','bg-primary hover:bg-primary/90 text-white'],
              ['n','Skip','bg-[#0f1117] border border-[#2a2d3e] text-slate-300 hover:text-slate-100'],
              ['q','Quit','bg-red-500/20 border border-red-500/40 text-red-400 hover:bg-red-500/30']].map(([ans, label, cls]) => (
              <button key={ans} onClick={() => { api.reviewAns(ans); setReviewJob(null) }}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${cls}`}>
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: 'Applied Today',  value: todayCount,  color: 'text-primary' },
          { label: 'This Week',      value: weekCount,   color: 'text-blue-400' },
          { label: 'Success Rate',   value: `${successRate}%`, color: 'text-success' },
          { label: 'Session Jobs',   value: botStatus.jobs_applied, color: 'text-slate-100' },
          { label: 'Needs Review',   value: reviewCount, color: reviewCount > 0 ? 'text-yellow-400' : 'text-slate-500' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4">
            <p className="text-xs text-slate-500 uppercase tracking-wide">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      {(isRunning || isPaused) && (
        <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4 space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-slate-400 flex items-center gap-2">
              <Loader size={14} className={isRunning ? 'animate-spin text-primary' : 'text-slate-500'} />
              {botStatus.current_job
                ? `${isPaused ? 'Paused' : 'Running'}: ${botStatus.current_job.company} — ${botStatus.current_job.title}`
                : isPaused ? 'Paused' : 'Running'}
            </span>
            {botStatus.jobs_total > 0 && (
              <span className="text-slate-400">{botStatus.jobs_applied} / {botStatus.jobs_total} jobs</span>
            )}
          </div>
          {botStatus.jobs_total > 0 && (
            <div className="w-full bg-[#0f1117] rounded-full h-2">
              <div className="bg-primary rounded-full h-2 transition-all"
                style={{ width: `${Math.min(100, (botStatus.jobs_applied / botStatus.jobs_total) * 100)}%` }} />
            </div>
          )}
          <div className="flex gap-4 text-xs">
            <span className="text-green-400">✓ {botStatus.session_submitted ?? 0} submitted</span>
            <span className="text-red-400">✗ {botStatus.session_failed ?? 0} failed</span>
            <span className="text-yellow-400">⚠ {botStatus.session_errors ?? 0} errors</span>
          </div>
        </div>
      )}

      {/* Live log */}
      <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-[#2a2d3e] flex items-center justify-between">
          <span className="font-medium text-slate-200 text-sm">Live Activity</span>
          <button onClick={() => setLogs([])} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">Clear</button>
        </div>
        <div className="h-72 overflow-y-auto p-4 space-y-1 scrollbar-thin font-mono text-xs">
          {logs.length === 0
            ? <p className="text-slate-600 text-center mt-8">No activity yet. Start the bot to see logs.</p>
            : logs.map((e, i) => <LogEntry key={i} entry={e} />)
          }
          <div ref={logEnd} />
        </div>
      </div>

      {showStart && <StartModal onClose={() => setShowStart(false)} onStart={handleStart} />}
    </div>
  )
}

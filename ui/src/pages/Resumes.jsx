import React, { useState, useEffect, useRef } from 'react'
import { Upload, Trash2, Zap, FileText, RefreshCw } from 'lucide-react'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'

function ResumeCard({ resume, profile, onDelete }) {
  const [scoring, setScoring] = useState(false)
  const [result,  setResult]  = useState(null)
  const [jd,      setJd]      = useState('')
  const [showJd,  setShowJd]  = useState(false)

  const score = async () => {
    if (!jd.trim()) return
    setScoring(true)
    try {
      const r = await api.scoreResume(profile, resume.filename, jd)
      setResult(r)
    } catch (e) { alert(e.message) }
    setScoring(false)
  }

  return (
    <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-[#0f1117] rounded-lg flex items-center justify-center shrink-0">
            <FileText size={18} className="text-primary" />
          </div>
          <div className="min-w-0">
            <p className="font-medium text-slate-200 text-sm truncate" title={resume.filename}>{resume.filename}</p>
            <p className="text-xs text-slate-500 mt-0.5">{resume.size_kb} KB · Used {resume.times_used}× · Avg score: {resume.avg_score || '—'}</p>
          </div>
        </div>
        <button onClick={() => onDelete(resume.filename)} className="text-slate-600 hover:text-red-400 transition-colors shrink-0">
          <Trash2 size={14} />
        </button>
      </div>

      <button onClick={() => setShowJd(!showJd)} className="text-xs text-primary hover:text-primary/80 flex items-center gap-1 transition-colors">
        <Zap size={12} /> Test score vs JD
      </button>

      {showJd && (
        <div className="space-y-2">
          <textarea value={jd} onChange={e => setJd(e.target.value)} rows={3}
            className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-xs text-slate-300 resize-none focus:outline-none focus:border-primary"
            placeholder="Paste job description here…" />
          <button onClick={score} disabled={scoring || !jd.trim()}
            className="w-full py-1.5 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg text-xs font-medium transition-colors disabled:opacity-40">
            {scoring ? 'Scoring…' : 'Score'}
          </button>
          {result && (
            <div className="bg-[#0f1117] rounded-lg p-3 space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-slate-100">{result.score?.toFixed(3)}</span>
                <StatusBadge type="fit" value={result.fit_label} />
              </div>
              {result.keywords?.length > 0 && (
                <p className="text-xs text-slate-400">Keywords: {result.keywords.join(', ')}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function Resumes() {
  const [profiles, setProfiles] = useState([])
  const [active,   setActive]   = useState('muhammad')
  const [resumes,  setResumes]  = useState([])
  const [loading,  setLoading]  = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef()

  const load = (p) => {
    setLoading(true)
    api.listResumes(p).then(r => { setResumes(r); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => {
    api.listProfiles().then(ps => {
      setProfiles(ps)
      if (ps.length) {
        const name = ps[0].name || ps[0].first_name?.toLowerCase() || 'muhammad'
        setActive(name)
        load(name)
      } else {
        load('muhammad')
      }
    }).catch(() => load('muhammad'))
  }, [])

  const switchProfile = (p) => { setActive(p); load(p) }

  const upload = async (files) => {
    for (const f of files) {
      if (!f.name.endsWith('.pdf')) continue
      try { await api.uploadResume(active, f) } catch (e) { alert(`Failed: ${f.name} — ${e.message}`) }
    }
    load(active)
  }

  const del = async (filename) => {
    if (!confirm(`Delete ${filename}?`)) return
    await api.deleteResume(active, filename)
    setResumes(r => r.filter(x => x.filename !== filename))
  }

  const onDrop = (e) => {
    e.preventDefault(); setDragOver(false)
    upload(Array.from(e.dataTransfer.files))
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Resume Manager</h1>
          <p className="text-slate-400 text-sm">{resumes.length} resumes for {active}</p>
        </div>
        <button onClick={() => load(active)} className="p-2 rounded-lg border border-[#2a2d3e] text-slate-400 hover:text-slate-100 transition-colors"><RefreshCw size={16} /></button>
      </div>

      {/* Profile tabs */}
      <div className="flex gap-2">
        {(profiles.length ? profiles.map(p => p.name || p.first_name?.toLowerCase()) : ['muhammad', 'razia']).map(p => (
          <button key={p} onClick={() => switchProfile(p)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${active === p ? 'bg-primary text-white' : 'bg-[#1a1d27] border border-[#2a2d3e] text-slate-400 hover:text-slate-100'}`}>
            {p}
          </button>
        ))}
      </div>

      {/* Upload zone */}
      <div
        onDrop={onDrop}
        onDragOver={e => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${dragOver ? 'border-primary bg-primary/10' : 'border-[#2a2d3e] hover:border-slate-500'}`}
      >
        <Upload size={24} className="mx-auto mb-2 text-slate-500" />
        <p className="text-sm text-slate-400">Drop PDFs here or <span className="text-primary">click to upload</span></p>
        <input ref={fileRef} type="file" accept=".pdf" multiple className="hidden" onChange={e => upload(Array.from(e.target.files))} />
      </div>

      {/* Resume grid */}
      {loading
        ? <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" /></div>
        : resumes.length === 0
        ? <div className="text-center py-12 text-slate-500">No resumes uploaded yet</div>
        : <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {resumes.map(r => <ResumeCard key={r.filename} resume={r} profile={active} onDelete={del} />)}
          </div>
      }
    </div>
  )
}

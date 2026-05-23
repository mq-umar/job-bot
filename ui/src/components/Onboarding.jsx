import React, { useState } from 'react'
import { CheckCircle, Upload, Globe, ArrowRight } from 'lucide-react'
import { api } from '../api'

const STEPS = ['Welcome', 'Your Profile', 'Upload Resumes', 'Browser Setup']

export default function Onboarding({ onComplete }) {
  const [step,        setStep]        = useState(0)
  const [form,        setForm]        = useState({ first_name:'', last_name:'', email:'', phone:'', city:'', state:'', linkedin:'' })
  const [files,       setFiles]       = useState([])
  const [uploading,   setUploading]   = useState(false)
  const [browserOk,  setBrowserOk]   = useState(false)
  const [testingBr,  setTestingBr]   = useState(false)
  const [dragOver,   setDragOver]    = useState(false)

  const next = () => setStep(s => Math.min(s + 1, 3))

  const saveProfile = async () => {
    try {
      await api.createProfile({ ...form, name: form.first_name.toLowerCase() })
    } catch (e) {
      try {
        await api.updateProfile(form.first_name.toLowerCase(), form)
      } catch {}
    }
    next()
  }

  const uploadAll = async () => {
    setUploading(true)
    for (const f of files) {
      try { await api.uploadResume(form.first_name.toLowerCase() || 'default', f) } catch {}
    }
    setUploading(false)
    next()
  }

  const testBrowser = async () => {
    setTestingBr(true)
    try {
      const r = await api.testBrowser()
      setBrowserOk(r.success)
    } catch { setBrowserOk(false) }
    setTestingBr(false)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = Array.from(e.dataTransfer.files).filter(f => f.name.endsWith('.pdf'))
    setFiles(prev => [...prev, ...dropped])
  }

  return (
    <div className="min-h-screen bg-[#0f1117] flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((s, i) => (
            <React.Fragment key={s}>
              <div className={`flex items-center gap-1.5 text-xs ${i <= step ? 'text-primary' : 'text-slate-600'}`}>
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold border-2 ${i < step ? 'bg-primary border-primary text-white' : i === step ? 'border-primary text-primary' : 'border-slate-600 text-slate-600'}`}>
                  {i < step ? '✓' : i + 1}
                </div>
                <span className="hidden sm:inline">{s}</span>
              </div>
              {i < STEPS.length - 1 && <div className={`flex-1 h-px ${i < step ? 'bg-primary' : 'bg-[#2a2d3e]'}`} />}
            </React.Fragment>
          ))}
        </div>

        <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-8">
          {step === 0 && (
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-primary/20 rounded-2xl flex items-center justify-center mx-auto">
                <div className="text-3xl font-bold text-primary">JB</div>
              </div>
              <h1 className="text-2xl font-bold text-slate-100">Welcome to Job Bot</h1>
              <p className="text-slate-400">Let's get you set up in under 2 minutes. We'll configure your profile, upload resumes, and install the browser the bot uses to apply.</p>
              <button onClick={next} className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors">
                Get Started <ArrowRight size={16} />
              </button>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-slate-100">Create your profile</h2>
              <p className="text-sm text-slate-400">This info auto-fills every application.</p>
              <div className="grid grid-cols-2 gap-3">
                {[['first_name','First Name'],['last_name','Last Name'],['email','Email'],['phone','Phone'],['city','City'],['state','State']].map(([k,l]) => (
                  <div key={k} className={k === 'email' ? 'col-span-2' : ''}>
                    <label className="block text-xs text-slate-400 mb-1">{l}</label>
                    <input value={form[k]} onChange={e => setForm(f => ({...f,[k]:e.target.value}))}
                      className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-md px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary"
                      placeholder={l} />
                  </div>
                ))}
              </div>
              <input value={form.linkedin} onChange={e => setForm(f => ({...f, linkedin: e.target.value}))}
                className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-md px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary"
                placeholder="LinkedIn URL (optional)" />
              <button onClick={saveProfile} className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium transition-colors">
                Save & Continue
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h2 className="text-xl font-bold text-slate-100">Upload your resumes</h2>
              <p className="text-sm text-slate-400">The bot picks the best-matching resume for each job using TF-IDF scoring.</p>
              <div
                onDrop={onDrop}
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onClick={() => document.getElementById('resume-file-input').click()}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${dragOver ? 'border-primary bg-primary/10' : 'border-[#2a2d3e] hover:border-slate-500'}`}
              >
                <Upload size={32} className="mx-auto mb-3 text-slate-500" />
                <p className="text-slate-300 font-medium">Drop PDFs here or click to browse</p>
                <p className="text-xs text-slate-500 mt-1">Multiple files accepted</p>
                <input id="resume-file-input" type="file" accept=".pdf" multiple className="hidden"
                  onChange={e => setFiles(prev => [...prev, ...Array.from(e.target.files)])} />
              </div>
              {files.length > 0 && (
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-slate-300 bg-[#0f1117] rounded px-3 py-1.5">
                      <CheckCircle size={14} className="text-success shrink-0" />
                      {f.name}
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-3">
                <button onClick={next} className="flex-1 py-2.5 border border-[#2a2d3e] rounded-lg text-slate-400 hover:text-slate-100 text-sm transition-colors">Skip for now</button>
                <button onClick={files.length ? uploadAll : next} disabled={uploading}
                  className="flex-1 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50">
                  {uploading ? 'Uploading…' : files.length ? 'Upload & Continue' : 'Continue'}
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6 text-center">
              <h2 className="text-xl font-bold text-slate-100">Browser setup</h2>
              <p className="text-slate-400">Job Bot uses Chromium to automate applications. Click to verify it's installed.</p>
              <div className="bg-[#0f1117] rounded-xl p-6">
                {browserOk
                  ? <div className="flex flex-col items-center gap-3"><CheckCircle size={48} className="text-success" /><p className="text-success font-medium">Browser ready!</p></div>
                  : <div className="flex flex-col items-center gap-4"><Globe size={48} className="text-slate-500" />
                      <button onClick={testBrowser} disabled={testingBr}
                        className="px-6 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center gap-2">
                        {testingBr ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Checking…</> : 'Check / Install Browser'}
                      </button>
                    </div>
                }
              </div>
              <button onClick={onComplete} className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors">
                {browserOk ? "Let's go!" : 'Continue Anyway'} <ArrowRight size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

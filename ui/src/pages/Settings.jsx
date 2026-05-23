import React, { useState, useEffect } from 'react'
import { Save, Plus, CheckCircle, XCircle, X } from 'lucide-react'
import { api } from '../api'

function Toggle({ checked, onChange }) {
  return (
    <button onClick={() => onChange(!checked)}
      className={`w-11 h-6 rounded-full transition-colors relative shrink-0 ${checked ? 'bg-primary' : 'bg-[#2a2d3e]'}`}>
      <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
    </button>
  )
}

function Section({ title, children }) {
  return (
    <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-[#2a2d3e]">
        <h3 className="font-medium text-slate-200">{title}</h3>
      </div>
      <div className="p-5 space-y-4">{children}</div>
    </div>
  )
}

export default function Settings() {
  const [s,         setS]         = useState({})
  const [blacklist, setBlacklist] = useState([])
  const [saved,     setSaved]     = useState(false)
  const [browserMsg,setBrowserMsg]= useState(null)
  const [newEntry,  setNewEntry]  = useState('')
  const [apiKey,    setApiKey]    = useState('')
  const [showKey,   setShowKey]   = useState(false)

  useEffect(() => {
    api.getSettings().then(setS).catch(() => {})
    api.getBlacklist().then(setBlacklist).catch(() => {})
  }, [])

  const save = async () => {
    const payload = { ...s }
    if (apiKey) payload.anthropic_key = apiKey
    await api.saveSettings(payload)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const testBrowser = async () => {
    setBrowserMsg({ loading: true })
    const r = await api.testBrowser()
    setBrowserMsg(r)
  }

  const addToBlacklist = () => {
    if (!newEntry.trim()) return
    const updated = [...blacklist, newEntry.trim()]
    setBlacklist(updated)
    api.saveBlacklist(updated)
    setNewEntry('')
  }

  const removeFromBlacklist = (i) => {
    const updated = blacklist.filter((_, idx) => idx !== i)
    setBlacklist(updated)
    api.saveBlacklist(updated)
  }

  const field = (k, label, type = 'text') => (
    <div className="flex items-center justify-between gap-4">
      <label className="text-sm text-slate-300">{label}</label>
      {type === 'toggle'
        ? <Toggle checked={!!s[k]} onChange={v => setS(x => ({...x,[k]:v}))} />
        : <input type={type} value={s[k]||''} onChange={e => setS(x => ({...x,[k]: type==='number'?+e.target.value:e.target.value}))}
            className="w-32 bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-1.5 text-sm text-slate-100 focus:outline-none focus:border-primary text-right" />
      }
    </div>
  )

  return (
    <div className="p-6 space-y-5 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Settings</h1>
          <p className="text-slate-400 text-sm">Configure application defaults and preferences</p>
        </div>
        <button onClick={save} className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${saved ? 'bg-success/20 text-success' : 'bg-primary hover:bg-primary/90 text-white'}`}>
          <Save size={14} /> {saved ? 'Saved!' : 'Save Changes'}
        </button>
      </div>

      <Section title="Application Defaults">
        {field('session_limit',  'Default session limit', 'number')}
        {field('default_mode',   'Default mode (auto/review)')}
        {field('auto_discover',  'Auto-discover jobs',    'toggle')}
        {field('cover_letter',   'Generate cover letters','toggle')}
        <div className="flex items-center justify-between gap-4">
          <label className="text-sm text-slate-300">Min score threshold ({s.min_score || 0.05})</label>
          <input type="range" min={0} max={0.45} step={0.05} value={s.min_score || 0.05}
            onChange={e => setS(x => ({...x, min_score: +e.target.value}))}
            className="w-32 accent-primary" />
        </div>
        {field('company_cooldown_days', 'Company cooldown (days)', 'number')}
      </Section>

      <Section title="API Keys (encrypted)">
        <div>
          <label className="block text-xs text-slate-400 mb-1.5">Anthropic API Key (optional — for AI cover letters)</label>
          <div className="flex gap-2">
            <input type={showKey ? 'text' : 'password'} value={apiKey}
              onChange={e => setApiKey(e.target.value)} placeholder="sk-ant-…"
              className="flex-1 bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary font-mono" />
            <button onClick={() => setShowKey(!showKey)} className="px-3 py-2 border border-[#2a2d3e] rounded-lg text-xs text-slate-400 hover:text-slate-100 transition-colors">
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
          {s.anthropic_key_set && <p className="text-xs text-success mt-1 flex items-center gap-1"><CheckCircle size={12} /> Key stored (encrypted)</p>}
        </div>
      </Section>

      <Section title="Company Blacklist">
        <p className="text-xs text-slate-500">The bot will skip any job from these companies.</p>
        <div className="flex gap-2">
          <input value={newEntry} onChange={e => setNewEntry(e.target.value)} onKeyDown={e => e.key === 'Enter' && addToBlacklist()}
            className="flex-1 bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary"
            placeholder="Company name or domain…" />
          <button onClick={addToBlacklist} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium"><Plus size={14} /></button>
        </div>
        <div className="space-y-1.5">
          {blacklist.map((e, i) => (
            <div key={i} className="flex items-center justify-between bg-[#0f1117] rounded-lg px-3 py-2">
              <span className="text-sm text-slate-300">{e}</span>
              <button onClick={() => removeFromBlacklist(i)} className="text-slate-600 hover:text-red-400 transition-colors"><X size={14} /></button>
            </div>
          ))}
          {blacklist.length === 0 && <p className="text-xs text-slate-600">No companies blacklisted</p>}
        </div>
      </Section>

      <Section title="Browser">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-300">Test / Install Browser</p>
            <p className="text-xs text-slate-500 mt-0.5">Verifies Chromium is installed for Playwright</p>
          </div>
          <button onClick={testBrowser} disabled={browserMsg?.loading}
            className="px-4 py-2 bg-[#0f1117] border border-[#2a2d3e] rounded-lg text-sm text-slate-300 hover:text-slate-100 transition-colors disabled:opacity-50">
            {browserMsg?.loading ? 'Checking…' : 'Test Browser'}
          </button>
        </div>
        {browserMsg && !browserMsg.loading && (
          <div className={`flex items-center gap-2 text-sm ${browserMsg.success ? 'text-success' : 'text-error'}`}>
            {browserMsg.success ? <CheckCircle size={14} /> : <XCircle size={14} />}
            {browserMsg.message}
          </div>
        )}
        {field('browser_visible', 'Run browser visible (headed)', 'toggle')}
      </Section>

      <Section title="Theme">
        {field('theme', 'Theme (dark/light/system)')}
      </Section>

      <Section title="About">
        <div className="space-y-2 text-sm text-slate-400">
          <p>Job Bot v2.0 — 100% local, zero data collection</p>
          <p>All data stays on your machine. No analytics or telemetry.</p>
          <a href="https://github.com/mq-umar/job-bot" target="_blank" rel="noreferrer" className="text-primary hover:underline">View on GitHub</a>
        </div>
      </Section>
    </div>
  )
}

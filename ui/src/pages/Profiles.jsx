import React, { useState, useEffect } from 'react'
import { Save, Plus } from 'lucide-react'
import { api } from '../api'

const FIELDS = [
  ['first_name','First Name'],['last_name','Last Name'],['email','Email'],
  ['phone','Phone'],['city','City'],['state','State'],['zip','ZIP'],
  ['country','Country'],['linkedin','LinkedIn URL'],['github','GitHub URL'],
  ['citizenship','Citizenship'],['authorized_to_work','Authorized to Work'],
  ['require_sponsorship','Require Sponsorship'],['veteran','Veteran'],
  ['disability','Disability'],['gender','Gender'],['ethnicity','Ethnicity'],
]

export default function Profiles() {
  const [profiles, setProfiles] = useState([])
  const [active,   setActive]   = useState(null)
  const [form,     setForm]     = useState({})
  const [saved,    setSaved]    = useState(false)
  const [creating, setCreating] = useState(false)
  const [newName,  setNewName]  = useState('')

  const loadAll = () => {
    api.listProfiles().then(ps => {
      setProfiles(ps)
      if (!active && ps.length) {
        const n = ps[0].name || ps[0].first_name?.toLowerCase()
        setActive(n)
        setForm(ps[0])
      }
    }).catch(() => {})
  }

  useEffect(() => { loadAll() }, [])

  const select = (p) => {
    setActive(p.name || p.first_name?.toLowerCase())
    setForm(p)
    setSaved(false)
  }

  const save = async () => {
    try {
      await api.updateProfile(active, form)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) { alert(e.message) }
  }

  const create = async () => {
    if (!newName.trim()) return
    try {
      await api.createProfile({ name: newName.toLowerCase(), first_name: newName })
      setCreating(false)
      setNewName('')
      loadAll()
    } catch (e) { alert(e.message) }
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Profiles</h1>
          <p className="text-slate-400 text-sm">Manage applicant profiles</p>
        </div>
        <button onClick={() => setCreating(true)} className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 text-white rounded-lg text-sm font-medium transition-colors">
          <Plus size={16} /> New Profile
        </button>
      </div>

      {creating && (
        <div className="bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-4 flex gap-3">
          <input value={newName} onChange={e => setNewName(e.target.value)} onKeyDown={e => e.key === 'Enter' && create()}
            className="flex-1 bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary"
            placeholder="Profile name (e.g. sarah)" autoFocus />
          <button onClick={create} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium">Create</button>
          <button onClick={() => setCreating(false)} className="px-4 py-2 border border-[#2a2d3e] text-slate-400 rounded-lg text-sm">Cancel</button>
        </div>
      )}

      <div className="flex gap-6">
        {/* Profile list */}
        <div className="w-48 shrink-0 space-y-1">
          {profiles.map(p => {
            const n = p.name || p.first_name?.toLowerCase()
            return (
              <button key={n} onClick={() => select(p)}
                className={`w-full text-left px-4 py-2.5 rounded-xl text-sm transition-colors capitalize ${active === n ? 'bg-primary/20 text-primary font-medium' : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'}`}>
                {p.full_name || p.first_name || n}
              </button>
            )
          })}
        </div>

        {/* Profile form */}
        {active && (
          <div className="flex-1 bg-[#1a1d27] border border-[#2a2d3e] rounded-xl p-5 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {FIELDS.map(([k, l]) => (
                <div key={k} className={['email','linkedin','github'].includes(k) ? 'col-span-2' : ''}>
                  <label className="block text-xs text-slate-400 mb-1">{l}</label>
                  <input value={form[k] || ''} onChange={e => setForm(f => ({...f,[k]:e.target.value}))}
                    className="w-full bg-[#0f1117] border border-[#2a2d3e] rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-primary"
                    placeholder={l} />
                </div>
              ))}
            </div>
            <div className="flex gap-3 pt-2">
              <button onClick={save} className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${saved ? 'bg-success/20 text-success' : 'bg-primary hover:bg-primary/90 text-white'}`}>
                <Save size={14} /> {saved ? 'Saved!' : 'Save Changes'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

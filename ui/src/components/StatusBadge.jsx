import React from 'react'

const FIT = {
  'Strong Fit': 'bg-green-500/20 text-green-400 border-green-500/30',
  'Good Fit':   'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  'Possible Fit': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'Stretch':    'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  'Low Fit':    'bg-red-500/20 text-red-400 border-red-500/30',
}

const STATUS = {
  'submitted':           'bg-green-500/20 text-green-400 border-green-500/30',
  'submitted_manually':  'bg-green-500/20 text-green-400 border-green-500/30',
  'dry_run':             'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'error':               'bg-red-500/20 text-red-400 border-red-500/30',
  'submit_failed':       'bg-red-500/20 text-red-400 border-red-500/30',
  'button_not_found':    'bg-amber-500/20 text-amber-400 border-amber-500/30',
  'watchdog_timeout':    'bg-orange-500/20 text-orange-400 border-orange-500/30',
  'skipped_manual':      'bg-slate-500/20 text-slate-400 border-slate-500/30',
  'skipped_low_fit':     'bg-slate-500/20 text-slate-400 border-slate-500/30',
  'already_applied':     'bg-slate-500/20 text-slate-400 border-slate-500/30',
  'closed':              'bg-slate-500/20 text-slate-400 border-slate-500/30',
  'needs_review':        'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  'skipped_scam':        'bg-red-500/20 text-red-400 border-red-500/30',
  'skipped_low_salary':  'bg-slate-500/20 text-slate-400 border-slate-500/30',
  'auth_wall':           'bg-purple-500/20 text-purple-400 border-purple-500/30',
}

export default function StatusBadge({ type, value }) {
  const map = type === 'fit' ? FIT : STATUS
  const cls = map[value] || 'bg-slate-500/20 text-slate-400 border-slate-500/30'
  return (
    <span className={`inline-flex items-center whitespace-nowrap px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}>
      {value}
    </span>
  )
}

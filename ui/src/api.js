const BASE = '/api'

function getToken() {
  return localStorage.getItem('bot_token') || ''
}

async function req(method, path, body) {
  const opts = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Bot-Token': getToken(),
    },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(BASE + path, opts)
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || res.statusText)
  }
  return res.json()
}

export const api = {
  // Token
  getToken:   ()       => fetch('/api/settings/token').then(r => r.json()),

  // Bot
  botStatus:  ()       => req('GET',  '/bot/status'),
  botStart:   (cfg)    => req('POST', '/bot/start', cfg),
  botStop:    ()       => req('POST', '/bot/stop'),
  botPause:   ()       => req('POST', '/bot/pause'),
  captchaDone:()       => req('POST', '/bot/captcha/solved'),
  reviewAns:  (ans)    => req('POST', '/bot/review', { answer: ans }),

  // Jobs
  getQueue:   ()       => req('GET',  '/jobs/queue'),
  getHistory: (p, status) => {
    const params = new URLSearchParams()
    if (p)      params.set('profile', p)
    if (status) params.set('status', status)
    const qs = params.toString()
    return req('GET', '/jobs/history' + (qs ? `?${qs}` : ''))
  },
  addJob:     (b)      => req('POST', '/jobs/add', b),
  deleteJob:  (id)     => req('DELETE',`/jobs/${id}`),
  getStats:        (p) => req('GET',  '/jobs/stats' + (p ? `?profile=${p}` : '')),
  getReviewQueue:  (p) => req('GET',  '/jobs/review_queue' + (p ? `?profile=${p}` : '')),

  // Resumes
  listResumes:(p)      => req('GET',  `/resumes/${p}`),
  scoreResume:(p,f,jd) => req('GET',  `/resumes/${p}/${encodeURIComponent(f)}/score?jd=${encodeURIComponent(jd)}`),
  deleteResume:(p,f)   => req('DELETE',`/resumes/${p}/${encodeURIComponent(f)}`),
  uploadResume: async (profile, file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`/api/resumes/${profile}`, {
      method: 'POST',
      headers: { 'X-Bot-Token': getToken() },
      body: fd,
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  // Profiles
  listProfiles: ()     => req('GET',  '/profiles'),
  getProfile:  (n)     => req('GET',  `/profiles/${n}`),
  updateProfile:(n,b)  => req('PUT',  `/profiles/${n}`, b),
  createProfile:(b)    => req('POST', '/profiles', b),

  // Settings
  getSettings: ()      => req('GET',  '/settings'),
  saveSettings:(b)     => req('PUT',  '/settings', b),
  testBrowser: ()      => req('POST', '/settings/test-browser'),
  getBlacklist:()      => req('GET',  '/settings/blacklist'),
  saveBlacklist:(b)    => req('PUT',  '/settings/blacklist', b),
}

import React, { useEffect, useState, createContext, useContext } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import JobQueue from './pages/JobQueue'
import History from './pages/History'
import Resumes from './pages/Resumes'
import Analytics from './pages/Analytics'
import InterviewTracker from './pages/InterviewTracker'
import Profiles from './pages/Profiles'
import Settings from './pages/Settings'
import ReviewQueue from './pages/ReviewQueue'
import Onboarding from './components/Onboarding'
import { api } from './api'

export const AppContext = createContext({})

export default function App() {
  const [dark, setDark]           = useState(true)
  const [onboarded, setOnboarded] = useState(null)
  const [settings, setSettings]   = useState({})

  // Load token + settings on mount
  useEffect(() => {
    api.getToken()
      .then(({ token }) => {
        if (token) localStorage.setItem('bot_token', token)
      })
      .catch(() => {})
    api.getSettings()
      .then(s => {
        setSettings(s)
        setOnboarded(!!s.onboarding_complete)
        const saved = localStorage.getItem('theme')
        if (saved) setDark(saved === 'dark')
      })
      .catch(() => setOnboarded(true))
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  const completeOnboarding = () => {
    api.saveSettings({ onboarding_complete: true })
    setOnboarded(true)
  }

  if (onboarded === null) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0f1117]">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!onboarded) {
    return <Onboarding onComplete={completeOnboarding} />
  }

  return (
    <AppContext.Provider value={{ dark, setDark, settings, setSettings }}>
      <Layout>
        <Routes>
          <Route path="/"           element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard"  element={<Dashboard />} />
          <Route path="/queue"      element={<JobQueue />} />
          <Route path="/history"    element={<History />} />
          <Route path="/resumes"    element={<Resumes />} />
          <Route path="/analytics"  element={<Analytics />} />
          <Route path="/tracker"    element={<InterviewTracker />} />
          <Route path="/profiles"   element={<Profiles />} />
          <Route path="/settings"   element={<Settings />} />
          <Route path="/review"     element={<ReviewQueue />} />
        </Routes>
      </Layout>
    </AppContext.Provider>
  )
}

import React, { useContext } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, ListTodo, History, FileText, BarChart3,
  Kanban, User, Settings, Moon, Sun, ShieldAlert,
} from 'lucide-react'
import { AppContext } from '../App'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/queue',     icon: ListTodo,         label: 'Job Queue'  },
  { to: '/history',   icon: History,           label: 'History'    },
  { to: '/resumes',   icon: FileText,          label: 'Resumes'    },
  { to: '/analytics', icon: BarChart3,         label: 'Analytics'  },
  { to: '/tracker',   icon: Kanban,            label: 'Interview'  },
  { to: '/review',    icon: ShieldAlert,       label: 'Review'     },
  { to: '/profiles',  icon: User,              label: 'Profiles'   },
  { to: '/settings',  icon: Settings,          label: 'Settings'   },
]

export default function Layout({ children }) {
  const { dark, setDark } = useContext(AppContext)

  return (
    <div className="flex min-h-screen bg-[#0f1117]">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 flex flex-col bg-[#1a1d27] border-r border-[#2a2d3e]">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-[#2a2d3e]">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white font-bold text-sm">JB</div>
            <span className="font-semibold text-slate-100">Job Bot</span>
            <span className="ml-auto text-xs text-slate-500">v2.0</span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-primary/20 text-primary font-medium'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-white/5'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Dark mode toggle */}
        <div className="p-3 border-t border-[#2a2d3e]">
          <button
            onClick={() => setDark(!dark)}
            className="flex items-center gap-2 px-3 py-2 w-full rounded-md text-sm text-slate-400 hover:text-slate-100 hover:bg-white/5 transition-colors"
          >
            {dark ? <Sun size={16} /> : <Moon size={16} />}
            {dark ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  )
}

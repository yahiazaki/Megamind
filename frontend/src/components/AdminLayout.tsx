import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { BellRing, BookOpen, Briefcase, FileText, GraduationCap, Globe, LogOut, Menu, NotebookPen, Settings, UserRound, X } from "lucide-react";
import { Logo } from "./Logo";
import { api } from "../lib/api";
import { cx } from "./ui";

const NAV = [
  { to: "/admin", label: "Study", icon: GraduationCap, end: true },
  { to: "/admin/notes", label: "Notes", icon: NotebookPen },
  { to: "/admin/library", label: "Library & Book", icon: BookOpen },
  { to: "/admin/reminders", label: "Reminders", icon: BellRing },
  { to: "/admin/work", label: "Work log", icon: Briefcase },
  { to: "/admin/cv", label: "CV generator", icon: FileText },
  { to: "/admin/profile", label: "Profile", icon: UserRound },
  { to: "/admin/settings", label: "Settings", icon: Settings },
];

export default function AdminLayout() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const logout = async () => {
    await api.send("/api/auth/logout");
    nav("/");
  };
  const links = (
    <nav className="flex flex-1 flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            cx(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
              isActive
                ? "bg-brand-600 text-white shadow-sm"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
            )
          }
        >
          <Icon className="h-4 w-4" /> {label}
        </NavLink>
      ))}
      <div className="mt-auto space-y-1 pt-4">
        <a
          href="/"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          <Globe className="h-4 w-4" /> Public portfolio
        </a>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          <LogOut className="h-4 w-4" /> Log out
        </button>
      </div>
    </nav>
  );
  return (
    <div className="flex h-full">
      <aside className="hidden w-60 shrink-0 flex-col border-e border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 md:flex">
        <div className="mb-6 px-2">
          <Logo />
        </div>
        {links}
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 bg-slate-950/50 md:hidden" onClick={() => setOpen(false)}>
          <aside className="flex h-full w-64 flex-col bg-white p-4 dark:bg-slate-900" onClick={(e) => e.stopPropagation()}>
            <div className="mb-6 flex items-center justify-between px-2">
              <Logo />
              <button onClick={() => setOpen(false)} aria-label="Close menu">
                <X className="h-5 w-5" />
              </button>
            </div>
            {links}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900 md:hidden">
          <button onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <Logo size={28} />
        </header>
        <main className="min-h-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

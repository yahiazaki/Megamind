import { Suspense, lazy, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./lib/api";
import AdminLayout from "./components/AdminLayout";
import Portfolio from "./pages/Portfolio";
import Login from "./pages/Login";
import Study from "./pages/admin/Study";
const Notes = lazy(() => import("./pages/admin/Notes"));
import Library from "./pages/admin/Library";
import ProfilePage from "./pages/admin/Profile";
import Work from "./pages/admin/Work";
import Cv from "./pages/admin/Cv";
import Reminders from "./pages/admin/Reminders";
import Settings from "./pages/admin/Settings";

function RequireAdmin({ children }: { children: JSX.Element }) {
  const [state, setState] = useState<"loading" | "ok" | "no">("loading");
  const loc = useLocation();
  useEffect(() => {
    api.get("/api/auth/me").then((r) => setState(r.admin ? "ok" : "no")).catch(() => setState("no"));
  }, []);
  if (state === "loading") return <div className="p-10 text-center text-slate-400">Loading…</div>;
  if (state === "no") return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Portfolio />} />
      <Route path="/login" element={<Login />} />
      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminLayout />
          </RequireAdmin>
        }
      >
        <Route index element={<Study />} />
        <Route path="study/:id" element={<Study />} />
        <Route path="notes" element={<Suspense fallback={<div className="p-10 text-center text-slate-400">Loading…</div>}><Notes /></Suspense>} />
        <Route path="notes/:id" element={<Suspense fallback={<div className="p-10 text-center text-slate-400">Loading…</div>}><Notes /></Suspense>} />
        <Route path="library" element={<Library />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="work" element={<Work />} />
        <Route path="cv" element={<Cv />} />
        <Route path="reminders" element={<Reminders />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

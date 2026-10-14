import { FormEvent, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Lock } from "lucide-react";
import { api } from "../lib/api";
import { Logo } from "../components/Logo";
import { Button, Card, ErrorNote, Input } from "../components/ui";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [params] = useSearchParams();
  const nav = useNavigate();
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.send("/api/auth/login", { password });
      nav(params.get("next") || "/admin");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex min-h-full items-center justify-center bg-gradient-to-br from-brand-50 to-white p-4 dark:from-slate-950 dark:to-slate-900">
      <Card className="w-full max-w-sm">
        <form onSubmit={submit} className="space-y-4">
          <div className="flex flex-col items-center gap-2 text-center">
            <Logo size={64} withText={false} />
            <h1 className="text-xl font-bold">Megamind admin</h1>
            <p className="text-sm text-slate-500">Owner access to notes, study sessions and tools.</p>
          </div>
          <div className="relative">
            <Lock className="absolute start-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input type="password" autoFocus placeholder="Password" className="ps-9" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <ErrorNote error={error} />
          <Button className="w-full" loading={busy} type="submit">
            Sign in
          </Button>
          <a href="/" className="block text-center text-xs text-slate-500 hover:underline">
            ← Back to the portfolio
          </a>
        </form>
      </Card>
    </div>
  );
}

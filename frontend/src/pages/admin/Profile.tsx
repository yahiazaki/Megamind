import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { api } from "../../lib/api";
import { Profile } from "../../lib/types";
import { Button, Card, ErrorNote, Field, Input, PageHeader, Textarea } from "../../components/ui";

const ADVANCED_KEYS = ["experience", "projects", "skills", "certifications", "education", "summaries", "headlines", "languages", "interests"];

export default function ProfilePage() {
  const [p, setP] = useState<Profile | null>(null);
  const [advanced, setAdvanced] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<Profile>("/api/profile").then((data) => {
      setP(data);
      setAdvanced(JSON.stringify(Object.fromEntries(ADVANCED_KEYS.map((k) => [k, data[k] ?? []])), null, 2));
    });
  }, []);
  if (!p) return <div className="p-6 text-slate-400">Loading…</div>;

  const set = (k: string, v: any) => setP({ ...p, [k]: v });
  const save = async () => {
    setError("");
    setSaved(false);
    let adv: Record<string, any>;
    try {
      adv = JSON.parse(advanced);
    } catch (e: any) {
      setError("The advanced JSON is not valid: " + e.message);
      return;
    }
    setBusy(true);
    try {
      const out = await api.send<Profile>("/api/profile", { ...p, ...adv }, "PUT");
      setP(out);
      setSaved(true);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl p-4 sm:p-6">
      <PageHeader
        title="Profile"
        subtitle="Shown on the public portfolio and used by the CV generator and the recruiter chat."
        actions={
          <Button onClick={save} loading={busy}>
            <Save className="h-4 w-4" /> Save
          </Button>
        }
      />
      <div className="space-y-6">
        <Card className="grid gap-4 sm:grid-cols-2">
          <Field label="Full name">
            <Input value={p.name ?? ""} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field label="Headline">
            <Input value={p.headline ?? ""} onChange={(e) => set("headline", e.target.value)} />
          </Field>
          <Field label="Current role">
            <Input value={p.current?.role ?? ""} onChange={(e) => set("current", { ...p.current, role: e.target.value })} />
          </Field>
          <Field label="Current company">
            <Input value={p.current?.company ?? ""} onChange={(e) => set("current", { ...p.current, company: e.target.value })} />
          </Field>
          <Field label="Location">
            <Input value={p.location ?? ""} onChange={(e) => set("location", e.target.value)} />
          </Field>
          <Field label="Email">
            <Input value={p.email ?? ""} onChange={(e) => set("email", e.target.value)} />
          </Field>
          <Field label="Phone" hint="Used on generated CVs. Hidden from the public site unless enabled below.">
            <Input value={p.phone ?? ""} onChange={(e) => set("phone", e.target.value)} />
          </Field>
          <label className="mt-6 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!p.show_phone_publicly} onChange={(e) => set("show_phone_publicly", e.target.checked)} />
            Show phone number on the public portfolio
          </label>
          <Field label="LinkedIn URL">
            <Input value={p.links?.linkedin ?? ""} onChange={(e) => set("links", { ...p.links, linkedin: e.target.value })} />
          </Field>
          <Field label="GitHub URL">
            <Input value={p.links?.github ?? ""} onChange={(e) => set("links", { ...p.links, github: e.target.value })} />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Summary">
              <Textarea className="min-h-28" value={p.summary ?? ""} onChange={(e) => set("summary", e.target.value)} />
            </Field>
          </div>
        </Card>
        <Card>
          <Field label="Experience, projects, skills, education (JSON)" hint="Edit the structured sections directly. Keep the same shape as the existing entries.">
            <Textarea className="min-h-[480px] font-mono text-xs" spellCheck={false} value={advanced} onChange={(e) => setAdvanced(e.target.value)} />
          </Field>
        </Card>
        <ErrorNote error={error} />
        {saved && <p className="text-sm text-emerald-600">Saved.</p>}
      </div>
    </div>
  );
}

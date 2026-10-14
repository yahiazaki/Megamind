import { FormEvent, useEffect, useState } from "react";
import { Eye, EyeOff, Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../../lib/api";
import { WorkTask } from "../../lib/types";
import { Badge, Button, Card, ErrorNote, Field, Input, PageHeader, Textarea } from "../../components/ui";

const EMPTY: WorkTask = { title: "", description: "", company: "", project: "", tags: "", impact: "", date: new Date().toISOString().slice(0, 10), public: true };

export default function Work() {
  const [tasks, setTasks] = useState<WorkTask[]>([]);
  const [form, setForm] = useState<WorkTask>(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get<WorkTask[]>("/api/tasks").then(setTasks);
  useEffect(() => {
    load();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return setError("Give the task a title");
    setBusy(true);
    setError("");
    try {
      const body = { ...form, date: form.date || null };
      if (form.id) await api.send(`/api/tasks/${form.id}`, body, "PUT");
      else await api.send("/api/tasks", body);
      setForm({ ...EMPTY, company: form.company, project: form.project });
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <PageHeader title="Work log" subtitle="Tasks and achievements. Used by the CV generator; public ones also appear on your portfolio and in the recruiter chat." />
      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <Card>
          <form onSubmit={submit} className="space-y-3">
            <div className="font-semibold">{form.id ? "Edit task" : "Add a task"}</div>
            <Field label="What did you do?">
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Added a reranker to the CTIO chatbot" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Company">
                <Input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
              </Field>
              <Field label="Project">
                <Input value={form.project} onChange={(e) => setForm({ ...form, project: e.target.value })} />
              </Field>
            </div>
            <Field label="Details">
              <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="How you did it, tools, scope…" />
            </Field>
            <Field label="Impact" hint="Numbers make CV bullets stronger (time saved, accuracy, cost…).">
              <Input value={form.impact} onChange={(e) => setForm({ ...form, impact: e.target.value })} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Date">
                <Input type="date" value={form.date ?? ""} onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </Field>
              <Field label="Tags">
                <Input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="RAG, Python" />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.public} onChange={(e) => setForm({ ...form, public: e.target.checked })} />
              Show on the public portfolio
            </label>
            <ErrorNote error={error} />
            <div className="flex gap-2">
              <Button type="submit" loading={busy} className="flex-1">
                <Plus className="h-4 w-4" /> {form.id ? "Save changes" : "Add task"}
              </Button>
              {form.id && (
                <Button type="button" variant="secondary" onClick={() => setForm(EMPTY)}>
                  Cancel
                </Button>
              )}
            </div>
          </form>
        </Card>
        <div className="space-y-3">
          {tasks.length === 0 && <Card className="text-sm text-slate-500">No tasks yet. Add what you work on as you go — the CV generator will thank you.</Card>}
          {tasks.map((t) => (
            <Card key={t.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-semibold">{t.title}</div>
                  <div className="text-xs text-slate-500">{[t.company, t.project, t.date].filter(Boolean).join(" · ")}</div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {t.public ? <Eye className="h-4 w-4 text-emerald-500" aria-label="public" /> : <EyeOff className="h-4 w-4 text-slate-400" aria-label="private" />}
                  <button className="p-1 text-slate-400 hover:text-brand-600" onClick={() => setForm({ ...t, date: t.date ?? "" })} aria-label="Edit">
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    className="p-1 text-slate-400 hover:text-red-600"
                    onClick={() => confirm("Delete this task?") && api.del(`/api/tasks/${t.id}`).then(load)}
                    aria-label="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              {t.description && <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{t.description}</p>}
              {t.impact && <p className="mt-1 text-sm font-medium text-brand-700 dark:text-brand-300">↗ {t.impact}</p>}
              {t.tags && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {t.tags.split(",").map((x) => x.trim()).filter(Boolean).map((x) => (
                    <Badge key={x}>{x}</Badge>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

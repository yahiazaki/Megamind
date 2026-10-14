import { FormEvent, useEffect, useState } from "react";
import { CalendarCheck, CalendarPlus, MessageCircle, Send, Trash2, Wand2 } from "lucide-react";
import { api, fmtDate } from "../../lib/api";
import { Reminder } from "../../lib/types";
import { Badge, Button, Card, ErrorNote, Field, Input, PageHeader, Textarea } from "../../components/ui";

export default function Reminders() {
  const [items, setItems] = useState<Reminder[]>([]);
  const [text, setText] = useState("");
  const [form, setForm] = useState({ title: "", start: "", end: "", notes: "", all_day: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<{ text: string; next_run: string | null } | null>(null);
  const [sendResult, setSendResult] = useState("");

  const load = () => {
    api.get<Reminder[]>("/api/reminders").then(setItems);
    api.get("/api/briefing/preview").then(setBriefing);
  };
  useEffect(load, []);

  const quickAdd = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy("quick");
    setError("");
    try {
      await api.send("/api/reminders/parse", { text });
      setText("");
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };
  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!form.title || !form.start) return setError("Title and start are required");
    setBusy("form");
    setError("");
    try {
      await api.send("/api/reminders", { ...form, end: form.end || null });
      setForm({ title: "", start: "", end: "", notes: "", all_day: false });
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };
  const sendNow = async () => {
    setBusy("send");
    const r = await api.send("/api/briefing/send");
    setSendResult(r.status === "sent" ? "Sent to WhatsApp ✓" : `Not sent (${r.status}): ${r.error}`);
    setBusy(null);
  };

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <PageHeader title="Reminders" subtitle="Saved here and in Google Calendar (when connected). Every morning Megamind sends you today's plan on WhatsApp." />
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="space-y-6">
          <Card>
            <form onSubmit={quickAdd} className="flex gap-2">
              <Input value={text} onChange={(e) => setText(e.target.value)} placeholder='Just say it: "revise subnetting tomorrow at 6pm" or "fakarny el sabt interview 11"' dir="auto" />
              <Button type="submit" loading={busy === "quick"}>
                <Wand2 className="h-4 w-4" /> Add
              </Button>
            </form>
            <ErrorNote error={error} />
          </Card>
          <Card className="p-0">
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {items.map((r) => (
                <li key={r.id} className="flex items-start gap-3 p-4">
                  <CalendarCheck className="mt-0.5 h-5 w-5 text-brand-500" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{r.title}</div>
                    <div className="text-xs text-slate-500">
                      {r.all_day ? new Date(r.start).toLocaleDateString(undefined, { dateStyle: "full" }) + " · all day" : fmtDate(r.start)}
                    </div>
                    {r.notes && <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{r.notes}</p>}
                  </div>
                  {r.google ? <Badge tone="green">Google</Badge> : <Badge>local</Badge>}
                  <button className="p-1 text-slate-400 hover:text-red-600" onClick={() => api.del(`/api/reminders/${r.id}`).then(load)} aria-label="Delete">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
              {items.length === 0 && <li className="p-6 text-center text-sm text-slate-400">No upcoming reminders.</li>}
            </ul>
          </Card>
        </div>
        <div className="space-y-6">
          <Card>
            <form onSubmit={add} className="space-y-3">
              <div className="flex items-center gap-2 font-semibold">
                <CalendarPlus className="h-4 w-4" /> Add manually
              </div>
              <Field label="Title">
                <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
              </Field>
              <Field label="Start">
                <Input type="datetime-local" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} />
              </Field>
              <Field label="End (optional)">
                <Input type="datetime-local" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} />
              </Field>
              <Field label="Notes">
                <Textarea className="min-h-16" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </Field>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.all_day} onChange={(e) => setForm({ ...form, all_day: e.target.checked })} /> All day
              </label>
              <Button type="submit" className="w-full" loading={busy === "form"}>
                Save reminder
              </Button>
            </form>
          </Card>
          <Card>
            <div className="mb-2 flex items-center gap-2 font-semibold">
              <MessageCircle className="h-4 w-4 text-emerald-600" /> Today's WhatsApp briefing
            </div>
            <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-sm dark:bg-slate-800">{briefing?.text}</pre>
            <p className="mt-2 text-xs text-slate-500">Next automatic send: {briefing?.next_run ? fmtDate(briefing.next_run) : "—"}</p>
            <Button variant="secondary" className="mt-3 w-full" onClick={sendNow} loading={busy === "send"}>
              <Send className="h-4 w-4" /> Send now
            </Button>
            {sendResult && <p className="mt-2 text-xs text-slate-600 dark:text-slate-300">{sendResult}</p>}
          </Card>
        </div>
      </div>
    </div>
  );
}

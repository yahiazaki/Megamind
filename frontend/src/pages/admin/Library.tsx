import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, FileUp, NotebookPen, RefreshCw, Search, Trash2 } from "lucide-react";
import { api } from "../../lib/api";
import { Citation, Doc, Job } from "../../lib/types";
import { Badge, Button, Card, ErrorNote, Field, Input, PageHeader, Textarea, cx } from "../../components/ui";
import { SourceViewer } from "../../components/SourceViewer";

const statusTone = (s: string) => (s === "ready" ? "green" : s === "error" ? "red" : s === "processing" ? "blue" : "slate") as any;

export default function Library() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [subjects, setSubjects] = useState<string[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [tab, setTab] = useState<"file" | "note">("file");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState({ title: "", subject: "", translate: true, content: "" });
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<(Citation & { score: number })[]>([]);
  const [source, setSource] = useState<Partial<Citation> | null>(null);

  const load = useCallback(async () => {
    const [d, j, s, st] = await Promise.all([
      api.get<Doc[]>("/api/library/documents"),
      api.get<Job[]>("/api/library/jobs?limit=12"),
      api.get<string[]>("/api/library/subjects"),
      api.get("/api/library/stats"),
    ]);
    setDocs(d);
    setJobs(j);
    setSubjects(s);
    setStats(st);
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  const active = jobs.some((j) => j.status === "queued" || j.status === "running");
  useEffect(() => {
    if (!active) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [active, load]);

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (tab === "file") {
        const file = fileRef.current?.files?.[0];
        if (!file) throw new Error("Choose a file first");
        const fd = new FormData();
        fd.append("file", file);
        fd.append("title", form.title);
        fd.append("subject", form.subject);
        fd.append("translate", String(form.translate));
        await api.form("/api/library/upload", fd);
        if (fileRef.current) fileRef.current.value = "";
      } else {
        if (!form.title.trim() || !form.content.trim()) throw new Error("A note needs a title and some content");
        await api.send("/api/library/text", form);
      }
      setForm({ title: "", subject: form.subject, translate: true, content: "" });
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (d: Doc) => {
    if (!confirm(`Remove "${d.title}" from the book and the index?`)) return;
    await api.del(`/api/library/documents/${d.id}`);
    load();
  };

  const search = async (e: FormEvent) => {
    e.preventDefault();
    if (q.trim()) setHits(await api.get(`/api/library/search?q=${encodeURIComponent(q)}`));
  };

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <PageHeader
        title="Library & Book"
        subtitle={
          stats &&
          `${docs.length} documents · ${stats.chunks} indexed passages · book ${stats.book_exists ? "ready" : "not built yet"}`
        }
        actions={
          <>
            <a href="/api/library/book.pdf" target="_blank" rel="noreferrer">
              <Button>
                <BookOpen className="h-4 w-4" /> Open the book
              </Button>
            </a>
            <Button variant="secondary" onClick={() => api.send("/api/library/rebuild").then(load)}>
              <RefreshCw className="h-4 w-4" /> Rebuild book
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Card className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-start text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/50">
                <tr>
                  <th className="px-4 py-2 text-start">Chapter</th>
                  <th className="px-2 py-2 text-start">Status</th>
                  <th className="px-2 py-2 text-end">Pages</th>
                  <th className="px-2 py-2 text-end">Book p.</th>
                  <th className="px-2 py-2 text-end">Passages</th>
                  <th className="px-2 py-2" />
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => (
                  <tr key={d.id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className={cx("px-4 py-2.5", d.kind === "supplement" && "ps-8")}>
                      <div className="font-medium">{d.title}</div>
                      <div className="text-xs text-slate-400">
                        {d.subject || "—"} · {d.kind} · {d.file}
                      </div>
                      {d.error && <div className="text-xs text-red-600">{d.error}</div>}
                    </td>
                    <td className="px-2">
                      <Badge tone={statusTone(d.status)}>{d.status}</Badge>
                    </td>
                    <td className="px-2 text-end tabular-nums">{d.pages || ""}</td>
                    <td className="px-2 text-end tabular-nums">
                      {d.book_start_page && (
                        <a className="text-brand-600 hover:underline" href={`/api/library/book.pdf#page=${d.book_start_page}`} target="_blank" rel="noreferrer">
                          {d.book_start_page}
                        </a>
                      )}
                    </td>
                    <td className="px-2 text-end tabular-nums">{d.chunks || ""}</td>
                    <td className="whitespace-nowrap px-2 text-end">
                      <button className="p-1 text-slate-400 hover:text-brand-600" title="Re-process" onClick={() => api.send(`/api/library/documents/${d.id}/reingest`).then(load)}>
                        <RefreshCw className="h-4 w-4" />
                      </button>
                      <button className="p-1 text-slate-400 hover:text-red-600" title="Remove" onClick={() => remove(d)}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card>
            <form onSubmit={search} className="flex gap-2">
              <Input placeholder="Test retrieval: search your notes (any language)…" value={q} onChange={(e) => setQ(e.target.value)} dir="auto" />
              <Button type="submit" variant="secondary">
                <Search className="h-4 w-4" />
              </Button>
            </form>
            <ul className="mt-3 space-y-2">
              {hits.map((h, i) => (
                <li key={h.chunk_id}>
                  <button onClick={() => setSource(h)} className="w-full rounded-lg border border-slate-200 p-3 text-start text-sm hover:border-brand-300 dark:border-slate-700">
                    <div className="flex justify-between gap-2 text-xs text-slate-500">
                      <span className="font-semibold text-brand-700 dark:text-brand-300">
                        {i + 1}. {h.doc_title} › {h.section}
                      </span>
                      <span>p.{h.book_page}</span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-slate-600 dark:text-slate-300">{h.snippet}</p>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <div className="mb-4 flex rounded-lg bg-slate-100 p-1 text-sm dark:bg-slate-800">
              {(["file", "note"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cx("flex flex-1 items-center justify-center gap-1.5 rounded-md py-1.5 font-medium", tab === t ? "bg-white shadow-sm dark:bg-slate-900" : "text-slate-500")}
                >
                  {t === "file" ? <FileUp className="h-4 w-4" /> : <NotebookPen className="h-4 w-4" />}
                  {t === "file" ? "Upload file" : "Write a note"}
                </button>
              ))}
            </div>
            <form onSubmit={upload} className="space-y-3">
              {tab === "file" ? (
                <Field label="Document" hint="Word (.docx/.doc/.rtf/.odt), PDF, Markdown or text. Converted to PDF and appended to the book.">
                  <input ref={fileRef} type="file" accept=".pdf,.docx,.doc,.rtf,.odt,.md,.markdown,.txt" className="block w-full text-sm" />
                </Field>
              ) : (
                <Field label="Content" hint="Markdown supported: # headings, - bullets, ``` code, | tables |">
                  <Textarea className="min-h-48 font-mono text-xs" value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} dir="auto" />
                </Field>
              )}
              <Field label="Title">
                <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder={tab === "file" ? "Defaults to the file name" : "e.g. Kubernetes basics"} />
              </Field>
              <Field label="Subject" hint="Pick an existing subject to place it next to that chapter, or type a new one.">
                <Input list="subjects" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
                <datalist id="subjects">
                  {subjects.map((s) => (
                    <option key={s} value={s} />
                  ))}
                </datalist>
              </Field>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.translate} onChange={(e) => setForm({ ...form, translate: e.target.checked })} />
                Translate Arabic / Franco to English (local model)
              </label>
              <ErrorNote error={error} />
              <Button type="submit" className="w-full" loading={busy}>
                Add to the book
              </Button>
            </form>
          </Card>

          <Card>
            <div className="mb-3 text-sm font-semibold">Recent jobs</div>
            <ul className="space-y-2.5">
              {jobs.map((j) => (
                <li key={j.id} className="text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-slate-600 dark:text-slate-300">{j.message || j.kind}</span>
                    <Badge tone={j.status === "done" ? "green" : j.status === "error" ? "red" : "blue"}>{j.status}</Badge>
                  </div>
                  {(j.status === "running" || j.status === "queued") && (
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                      <div className="h-full bg-brand-500 transition-all" style={{ width: `${Math.round(j.progress * 100)}%` }} />
                    </div>
                  )}
                </li>
              ))}
              {jobs.length === 0 && <li className="text-xs text-slate-400">No jobs yet.</li>}
            </ul>
          </Card>
        </div>
      </div>
      <SourceViewer source={source} onClose={() => setSource(null)} />
    </div>
  );
}

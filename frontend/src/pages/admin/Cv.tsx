import { FormEvent, useEffect, useState } from "react";
import { Download, FileText, Wand2 } from "lucide-react";
import { api } from "../../lib/api";
import { Button, Card, ErrorNote, Field, Input, PageHeader, Textarea, cx } from "../../components/ui";

type Generated = { id: string; title: string; pdf: boolean; created: string };

export default function Cv() {
  const [jd, setJd] = useState("");
  const [title, setTitle] = useState("");
  const [extra, setExtra] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<Generated[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  const load = () => api.get<Generated[]>("/api/cv").then(setHistory);
  useEffect(() => {
    load();
  }, []);

  const generate = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api.send("/api/cv", { job_description: jd, target_title: title, extra });
      setResult(r);
      setSelected(r.id);
      load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl p-4 sm:p-6">
      <PageHeader title="CV generator" subtitle="Paste a job description. Megamind tailors your real experience and work log into a one-page CV (Word + PDF). It never invents facts." />
      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <div className="space-y-6">
          <Card>
            <form onSubmit={generate} className="space-y-3">
              <Field label="Target job title">
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Senior AI Engineer" />
              </Field>
              <Field label="Job description">
                <Textarea className="min-h-56" value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job post…" />
              </Field>
              <Field label="Anything to emphasise? (optional)">
                <Textarea className="min-h-16" value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="e.g. focus on security, keep the Siemens internship short" />
              </Field>
              <ErrorNote error={error} />
              <Button type="submit" className="w-full" loading={busy}>
                <Wand2 className="h-4 w-4" /> {busy ? "Writing your CV…" : "Generate CV"}
              </Button>
            </form>
          </Card>
          {result?.cv?.match_notes && (
            <Card className="border-brand-200 bg-brand-50/50 dark:border-brand-900 dark:bg-brand-950/30">
              <div className="mb-1 text-sm font-semibold">Fit notes (not printed on the CV)</div>
              <p className="text-sm text-slate-700 dark:text-slate-300">{result.cv.match_notes}</p>
            </Card>
          )}
          <Card>
            <div className="mb-2 text-sm font-semibold">Previous CVs</div>
            <ul className="space-y-1">
              {history.map((h) => (
                <li key={h.id}>
                  <button
                    onClick={() => setSelected(h.id)}
                    className={cx("flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-start text-sm", selected === h.id ? "bg-brand-50 dark:bg-brand-950" : "hover:bg-slate-100 dark:hover:bg-slate-800")}
                  >
                    <FileText className="h-4 w-4 text-brand-500" />
                    <span className="flex-1 truncate">{h.title || h.id}</span>
                    <span className="text-xs text-slate-400">{h.created.slice(0, 8)}</span>
                  </button>
                </li>
              ))}
              {history.length === 0 && <li className="text-xs text-slate-400">Nothing generated yet.</li>}
            </ul>
          </Card>
        </div>
        <Card className="min-h-[70vh] p-0">
          {selected ? (
            <div className="flex h-full flex-col">
              <div className="flex flex-wrap justify-end gap-2 border-b border-slate-200 p-3 dark:border-slate-800">
                <a href={`/api/cv/${selected}/docx`}>
                  <Button variant="secondary" size="sm">
                    <Download className="h-4 w-4" /> Word
                  </Button>
                </a>
                <a href={`/api/cv/${selected}/pdf`} target="_blank" rel="noreferrer">
                  <Button size="sm">
                    <Download className="h-4 w-4" /> PDF
                  </Button>
                </a>
              </div>
              <iframe title="CV preview" src={`/api/cv/${selected}/pdf`} className="min-h-[75vh] w-full flex-1 rounded-b-2xl" />
            </div>
          ) : (
            <div className="flex h-full min-h-[60vh] items-center justify-center p-6 text-center text-sm text-slate-400">The generated CV will appear here.</div>
          )}
        </Card>
      </div>
    </div>
  );
}

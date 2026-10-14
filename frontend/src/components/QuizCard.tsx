import { useState } from "react";
import { CheckCircle2, GraduationCap, XCircle } from "lucide-react";
import { QuizItem, Citation } from "../lib/types";
import { api } from "../lib/api";
import { Button, ErrorNote, Textarea, cx } from "./ui";

export function QuizCard({
  sessionId,
  items: initial,
  onSource,
}: {
  sessionId: number;
  items: QuizItem[];
  onSource: (c: Partial<Citation>) => void;
}) {
  const [items, setItems] = useState(initial);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const graded = items.every((q) => q.answered);
  const total = items.reduce((s, q) => s + (q.score ?? 0), 0);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const { results } = await api.send(`/api/sessions/${sessionId}/grade`, { answers });
      setItems((prev) => prev.map((q) => results.find((r: QuizItem) => r.id === q.id) ?? q));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border border-brand-200 bg-brand-50/60 p-4 dark:border-brand-900 dark:bg-brand-950/40">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 font-semibold text-brand-800 dark:text-brand-200">
          <GraduationCap className="h-5 w-5" /> Quiz · {items.length} questions
        </div>
        {graded && (
          <span className="rounded-full bg-white px-3 py-1 text-sm font-bold text-brand-700 shadow-sm dark:bg-slate-900 dark:text-brand-300">
            {total.toFixed(1)} / {items.length}
          </span>
        )}
      </div>
      <ol className="space-y-4">
        {items.map((q, i) => {
          const correct = (q.score ?? 0) >= 0.7;
          return (
            <li key={q.id} className="rounded-xl bg-white p-3 shadow-sm dark:bg-slate-900">
              <div className="mb-2 flex gap-2 text-sm font-medium" dir="auto">
                <span className="text-brand-600">{i + 1}.</span>
                <span>{q.question}</span>
              </div>
              {q.type === "mcq" ? (
                <div className="grid gap-1.5">
                  {q.options.map((opt, oi) => {
                    const chosen = (q.answered ? q.user_answer : answers[q.id]) === String(oi);
                    const isAnswer = q.answered && q.answer === String(oi);
                    return (
                      <label
                        key={oi}
                        className={cx(
                          "flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-sm transition",
                          isAnswer
                            ? "border-emerald-400 bg-emerald-50 dark:bg-emerald-950/40"
                            : chosen && q.answered
                              ? "border-red-300 bg-red-50 dark:bg-red-950/30"
                              : chosen
                                ? "border-brand-400 bg-brand-50 dark:bg-brand-950/40"
                                : "border-slate-200 hover:border-brand-300 dark:border-slate-700",
                        )}
                      >
                        <input
                          type="radio"
                          className="mt-0.5"
                          name={`q${q.id}`}
                          disabled={q.answered}
                          checked={chosen}
                          onChange={() => setAnswers((a) => ({ ...a, [q.id]: String(oi) }))}
                        />
                        <span dir="auto">{opt}</span>
                      </label>
                    );
                  })}
                </div>
              ) : q.answered ? (
                <div className="rounded-lg bg-slate-50 p-2 text-sm dark:bg-slate-800" dir="auto">
                  <span className="text-xs font-semibold text-slate-400">Your answer: </span>
                  {q.user_answer}
                </div>
              ) : (
                <Textarea
                  placeholder="Type your answer (any language)…"
                  value={answers[q.id] ?? ""}
                  onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
                  className="min-h-16"
                />
              )}
              {q.answered && (
                <div className="mt-2 space-y-1 text-sm">
                  <div className={cx("flex items-center gap-1.5 font-medium", correct ? "text-emerald-700 dark:text-emerald-400" : "text-red-600 dark:text-red-400")}>
                    {correct ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                    {q.feedback}
                  </div>
                  {q.type === "short" && q.answer && (
                    <p className="text-slate-600 dark:text-slate-300" dir="auto">
                      <span className="font-semibold">Model answer: </span>
                      {q.answer}
                    </p>
                  )}
                  {q.explanation && <p className="text-slate-500" dir="auto">{q.explanation}</p>}
                  {q.source?.document_id && (
                    <button className="text-xs font-medium text-brand-600 hover:underline" onClick={() => onSource(q.source)}>
                      📖 {q.source.doc_title} › {q.source.section}
                      {q.source.book_page ? ` (p. ${q.source.book_page})` : ""}
                    </button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <ErrorNote error={error} />
      {!graded && (
        <div className="mt-3 flex justify-end">
          <Button onClick={submit} loading={busy} disabled={Object.keys(answers).length === 0}>
            Submit answers
          </Button>
        </div>
      )}
    </div>
  );
}

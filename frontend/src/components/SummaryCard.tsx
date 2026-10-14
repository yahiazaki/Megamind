import { MessageCircle, Sparkles } from "lucide-react";
import { SessionSummary } from "../lib/types";
import { Badge } from "./ui";

export function SummaryCard({ data }: { data: SessionSummary }) {
  const wa = data.whatsapp;
  return (
    <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-5 dark:border-emerald-900 dark:from-emerald-950/40 dark:to-slate-900">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-lg font-bold">
          <Sparkles className="h-5 w-5 text-emerald-600" /> {data.title || "Session summary"}
        </div>
        <Badge tone="blue">Quiz: {data.score}</Badge>
      </div>
      <p className="mb-4 text-sm text-slate-700 dark:text-slate-300">{data.summary}</p>
      <div className="grid gap-4 md:grid-cols-2">
        <Section title="💪 Strengths" items={data.strengths} />
        <Section title="⚠️ Weak spots" items={data.weaknesses} />
      </div>
      {!!data.study_next?.length && (
        <div className="mt-4">
          <div className="mb-1 text-sm font-semibold">📚 Study next</div>
          <ul className="space-y-1.5 text-sm">
            {data.study_next.map((s, i) => (
              <li key={i}>
                <span className="font-medium">{s.topic}</span>
                {s.why && <span className="text-slate-600 dark:text-slate-400"> — {s.why}</span>}
                {s.where && (
                  <a
                    className="ms-1 text-xs text-brand-600 hover:underline"
                    href={s.book_page ? `/api/library/book.pdf#page=${s.book_page}` : undefined}
                    target="_blank"
                    rel="noreferrer"
                  >
                    ↳ {s.where}
                  </a>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {wa && (
        <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
          <MessageCircle className="h-4 w-4" />
          WhatsApp:{" "}
          {wa.status === "sent" ? (
            <Badge tone="green">sent</Badge>
          ) : wa.status === "skipped" ? (
            <Badge tone="amber">not configured — saved in Outbox</Badge>
          ) : (
            <Badge tone="red">failed — {wa.error?.slice(0, 80)}</Badge>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="mb-1 text-sm font-semibold">{title}</div>
      <ul className="list-disc space-y-1 ps-5 text-sm text-slate-700 dark:text-slate-300">
        {items.map((x, i) => (
          <li key={i}>{x}</li>
        ))}
      </ul>
    </div>
  );
}

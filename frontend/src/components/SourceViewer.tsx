import { useEffect, useState } from "react";
import { BookOpen, ExternalLink, X } from "lucide-react";
import { Citation } from "../lib/types";
import { api } from "../lib/api";
import { Button } from "./ui";

/** Modal showing the exact page of the notes a citation came from, with the passage highlighted. */
export function SourceViewer({ source, onClose }: { source: Partial<Citation> | null; onClose: () => void }) {
  const [full, setFull] = useState<string>("");
  useEffect(() => {
    setFull("");
    if (source?.chunk_id) api.get(`/api/library/chunks/${source.chunk_id}`).then((c) => setFull(c.text)).catch(() => {});
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [source, onClose]);
  if (!source?.document_id) return null;
  const img = `/api/library/page.png?doc_id=${source.document_id}&page=${source.page}&chunk_id=${source.chunk_id ?? ""}`;
  const bookLink = source.book_page ? `/api/library/book.pdf#page=${source.book_page}` : `/api/library/documents/${source.document_id}/pdf#page=${source.page}`;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-3 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 p-4 dark:border-slate-800">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-semibold text-brand-700 dark:text-brand-300">
              <BookOpen className="h-4 w-4" /> {source.doc_title}
            </div>
            <div className="truncate text-sm text-slate-500">{source.section}</div>
            <div className="mt-0.5 text-xs text-slate-400">
              {source.book_page ? `Book page ${source.book_page} · ` : ""}chapter page {source.page}
            </div>
          </div>
          <div className="flex shrink-0 gap-2">
            <a href={bookLink} target="_blank" rel="noreferrer">
              <Button variant="secondary" size="sm">
                <ExternalLink className="h-4 w-4" /> Open in book
              </Button>
            </a>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="grid min-h-0 flex-1 gap-0 md:grid-cols-[1fr_320px]">
          <div className="min-h-0 overflow-auto bg-slate-100 p-3 dark:bg-slate-950">
            <img src={img} alt="Page from your notes with the cited passage highlighted" className="mx-auto rounded shadow" />
          </div>
          <div className="min-h-0 overflow-auto border-t border-slate-200 p-4 text-sm dark:border-slate-800 md:border-t-0 md:border-s">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Cited passage</div>
            <p className="whitespace-pre-wrap leading-relaxed text-slate-700 dark:text-slate-300">{full || source.snippet}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

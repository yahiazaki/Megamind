import { KeyboardEvent, forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { FileText } from "lucide-react";
import { api } from "../lib/api";
import { NoteSummary } from "../lib/types";
import { cx } from "./ui";

export type Mention = { id: number; title: string };

type Props = {
  value: string;
  onChange: (v: string) => void;
  mentions: Mention[];
  onMentionsChange: (m: Mention[]) => void;
  onSubmit: () => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
  className?: string;
};

/** Mentions whose "@Title" is still present in the text (the user may have deleted some). */
export const activeMentions = (text: string, mentions: Mention[]) =>
  mentions.filter((m, i, all) => text.includes("@" + m.title) && all.findIndex((x) => x.id === m.id) === i);

/** Textarea with "@" autocomplete over the notes workspace. Enter sends, Shift+Enter adds a line. */
export const MentionTextarea = forwardRef<HTMLTextAreaElement, Props>(function MentionTextarea(
  { value, onChange, mentions, onMentionsChange, onSubmit, placeholder, rows = 1, disabled, className },
  ref,
) {
  const inner = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => inner.current as HTMLTextAreaElement);
  const [notes, setNotes] = useState<NoteSummary[]>([]);
  const [query, setQuery] = useState<string | null>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    if (query !== null && notes.length === 0) api.get<NoteSummary[]>("/api/notes").then(setNotes).catch(() => {});
  }, [query, notes.length]);

  const matches = query === null ? [] : notes.filter((n) => n.title.toLowerCase().includes(query.toLowerCase())).slice(0, 6);

  const detect = (text: string, caret: number) => {
    const m = /(^|\s)@([^\s@]{0,40})$/.exec(text.slice(0, caret));
    setQuery(m ? m[2] : null);
    setActive(0);
  };

  const pick = (n: NoteSummary) => {
    const el = inner.current!;
    const caret = el.selectionStart ?? value.length;
    const before = value.slice(0, caret).replace(/@([^\s@]{0,40})$/, `@${n.title} `);
    const next = before + value.slice(caret);
    onChange(next);
    onMentionsChange([...mentions.filter((m) => m.id !== n.id), { id: n.id, title: n.title }]);
    setQuery(null);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(before.length, before.length);
    });
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (matches.length) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => (a + (e.key === "ArrowDown" ? 1 : matches.length - 1)) % matches.length);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        pick(matches[active]);
        return;
      }
      if (e.key === "Escape") {
        setQuery(null);
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="relative flex-1">
      {matches.length > 0 && (
        <div className="absolute bottom-full z-30 mb-1 w-full max-w-sm overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
          <div className="px-3 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">Mention a note</div>
          {matches.map((n, i) => (
            <button
              key={n.id}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                pick(n);
              }}
              className={cx(
                "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                i === active ? "bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-200" : "hover:bg-slate-50 dark:hover:bg-slate-800",
              )}
            >
              <FileText className="h-4 w-4 shrink-0 opacity-60" />
              <span className="truncate">{n.title}</span>
            </button>
          ))}
        </div>
      )}
      <textarea
        ref={inner}
        rows={rows}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => {
          onChange(e.target.value);
          detect(e.target.value, e.target.selectionStart ?? e.target.value.length);
        }}
        onKeyDown={onKey}
        onBlur={() => setTimeout(() => setQuery(null), 150)}
        className={cx(
          "w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 dark:border-slate-700 dark:bg-slate-900 dark:focus:ring-brand-900",
          className,
        )}
      />
    </div>
  );
});

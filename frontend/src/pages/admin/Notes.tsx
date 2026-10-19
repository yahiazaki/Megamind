import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Highlight from "@tiptap/extension-highlight";
import TextStyle from "@tiptap/extension-text-style";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Placeholder from "@tiptap/extension-placeholder";
import Link from "@tiptap/extension-link";
import Table from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import TableHeader from "@tiptap/extension-table-header";
import TableCell from "@tiptap/extension-table-cell";
import {
  BookOpen,
  BookPlus,
  Check,
  ChevronDown,
  Download,
  FileText,
  Loader2,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Search,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { api, fmtDate } from "../../lib/api";
import { AssistResult, Note, NoteSummary } from "../../lib/types";
import { htmlToMarkdown, markdownToHtml } from "../../lib/markdown";
import { FontSize } from "../../components/editor/FontSize";
import { Toolbar } from "../../components/editor/Toolbar";
import { Markdown } from "../../components/Markdown";
import { Mention, MentionTextarea, activeMentions } from "../../components/MentionTextarea";
import { Badge, Button, cx } from "../../components/ui";

type SaveState = "saved" | "saving" | "dirty" | "error";

export default function Notes() {
  const { id } = useParams();
  const noteId = id ? Number(id) : null;
  const nav = useNavigate();
  const [list, setList] = useState<NoteSummary[]>([]);
  const [filter, setFilter] = useState("");

  const loadList = useCallback(() => api.get<NoteSummary[]>("/api/notes").then(setList), []);
  useEffect(() => {
    loadList();
  }, [loadList]);

  const newNote = async () => {
    const n = await api.send<Note>("/api/notes", { title: "Untitled" });
    await loadList();
    nav(`/admin/notes/${n.id}`);
  };

  const shown = list.filter((n) => n.title.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="flex h-full">
      <aside className="hidden w-60 shrink-0 flex-col border-e border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 lg:flex">
        <div className="space-y-2 p-3">
          <Button className="w-full" onClick={newNote}>
            <Plus className="h-4 w-4" /> New note
          </Button>
          <div className="relative">
            <Search className="absolute start-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search notes"
              className="w-full rounded-lg border border-slate-200 bg-white py-2 ps-8 pe-2 text-sm outline-none focus:border-brand-400 dark:border-slate-700 dark:bg-slate-900"
            />
          </div>
        </div>
        <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
          {shown.map((n) => (
            <button
              key={n.id}
              onClick={() => nav(`/admin/notes/${n.id}`)}
              className={cx(
                "w-full rounded-lg px-3 py-2 text-left transition",
                n.id === noteId ? "bg-brand-50 dark:bg-brand-950" : "hover:bg-slate-50 dark:hover:bg-slate-800",
              )}
            >
              <div className="flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                <span className={cx("truncate text-sm", n.id === noteId && "font-medium text-brand-700 dark:text-brand-300")}>{n.title}</span>
              </div>
              <div className="mt-0.5 flex items-center gap-1.5 ps-5 text-[11px] text-slate-400">
                {fmtDate(n.updated_at)}
                {n.in_book && <BookOpen className={cx("h-3 w-3", n.stale ? "text-amber-500" : "text-emerald-500")} />}
              </div>
            </button>
          ))}
          {list.length > 0 && shown.length === 0 && <p className="px-3 py-4 text-sm text-slate-400">No matching notes.</p>}
        </div>
      </aside>

      {noteId ? (
        <NoteEditor key={noteId} noteId={noteId} onSaved={loadList} onDeleted={() => (loadList(), nav("/admin/notes"))} />
      ) : (
        <div className="grid flex-1 place-items-center p-8">
          <div className="max-w-md text-center">
            <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-950">
              <FileText className="h-7 w-7" />
            </div>
            <h2 className="text-xl font-semibold">Your notes workspace</h2>
            <p className="mt-2 text-sm text-slate-500">
              Write with headings, lists, highlights and sizes. Ask the assistant to explain or rewrite parts, mention other notes with
              <code className="mx-1 rounded bg-slate-100 px-1 dark:bg-slate-800">@name</code>, then download the note or add it to your book so the
              study chat can answer from it.
            </p>
            <Button className="mt-5" onClick={newNote}>
              <Plus className="h-4 w-4" /> New note
            </Button>
            {list.length > 0 && (
              <div className="mt-6 space-y-1 text-left lg:hidden">
                {list.map((n) => (
                  <button key={n.id} onClick={() => nav(`/admin/notes/${n.id}`)} className="block w-full truncate rounded-lg px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800">
                    {n.title}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------

function NoteEditor({ noteId, onSaved, onDeleted }: { noteId: number; onSaved: () => void; onDeleted: () => void }) {
  const [note, setNote] = useState<Note | null>(null);
  const [title, setTitle] = useState("");
  const [save, setSave] = useState<SaveState>("saved");
  const [panel, setPanel] = useState(true);
  const [publishOpen, setPublishOpen] = useState(false);
  const timer = useRef<number | null>(null);
  const pending = useRef<{ title?: string; html?: string; markdown?: string }>({});

  const flush = useCallback(async () => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = null;
    const body = pending.current;
    if (!Object.keys(body).length) return;
    pending.current = {};
    setSave("saving");
    try {
      await api.send(`/api/notes/${noteId}`, body, "PUT");
      setSave("saved");
      onSaved();
    } catch {
      pending.current = { ...body, ...pending.current };
      setSave("error");
    }
  }, [noteId, onSaved]);

  const queue = useCallback(
    (patch: { title?: string; html?: string; markdown?: string }) => {
      pending.current = { ...pending.current, ...patch };
      setSave("dirty");
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(flush, 800);
    },
    [flush],
  );

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
      Underline,
      Highlight,
      TextStyle,
      FontSize,
      TaskList,
      TaskItem.configure({ nested: true }),
      Link.configure({ openOnClick: false, autolink: true }),
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({ placeholder: "Start writing… (select text and ask the assistant to rewrite it)" }),
    ],
    editorProps: { attributes: { class: "mm-editor focus:outline-none" } },
    onUpdate: ({ editor: e }) => {
      const html = e.getHTML();
      queue({ html, markdown: htmlToMarkdown(html) });
    },
  });

  const load = useCallback(() => api.get<Note>(`/api/notes/${noteId}`).then(setNote), [noteId]);
  useEffect(() => {
    load().catch(() => onDeleted());
  }, [load]); // eslint-disable-line react-hooks/exhaustive-deps

  // fill the editor once both the note and the editor exist
  const filled = useRef(false);
  useEffect(() => {
    if (!editor || !note || filled.current) return;
    filled.current = true;
    setTitle(note.title);
    editor.commands.setContent(note.html || "", false);
    if (!note.html) editor.commands.focus();
  }, [editor, note]);

  // save on leave / tab close
  useEffect(() => {
    const before = () => {
      if (Object.keys(pending.current).length) {
        flush();
      }
    };
    window.addEventListener("beforeunload", before);
    return () => {
      window.removeEventListener("beforeunload", before);
      flush();
    };
  }, [flush, noteId]);

  // poll while the book chapter is being built
  useEffect(() => {
    if (note?.document_status !== "pending" && note?.document_status !== "processing") return;
    const t = window.setInterval(() => load(), 3000);
    return () => window.clearInterval(t);
  }, [note?.document_status, load]);

  const remove = async () => {
    if (!confirm(`Delete "${title}"?`)) return;
    const fromBook = note?.in_book ? confirm("This note is in your book. Remove it from the book and the study chat too?") : false;
    await api.del(`/api/notes/${noteId}?remove_from_book=${fromBook}`);
    onDeleted();
  };

  const download = async (fmt: string) => {
    await flush();
    window.location.href = `/api/notes/${noteId}/export?format=${fmt}`;
  };

  if (!note || !editor) {
    return (
      <div className="grid flex-1 place-items-center text-slate-400">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  const status =
    note.document_status === "pending" || note.document_status === "processing" ? (
      <Badge tone="blue">
        <Loader2 className="me-1 inline h-3 w-3 animate-spin" />
        adding to book…
      </Badge>
    ) : note.document_status === "error" ? (
      <Badge tone="red">book update failed</Badge>
    ) : note.in_book ? (
      <Badge tone={note.stale ? "amber" : "green"}>
        {note.stale ? "changed since added to book" : `in book · ${note.book_mode === "section" ? `inside "${note.book_chapter}"` : note.book_part}${note.book_page ? ` · p. ${note.book_page}` : ""}`}
      </Badge>
    ) : null;

  return (
    <div className="flex min-w-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col bg-white dark:bg-slate-950">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-4 py-2.5 dark:border-slate-800">
          <input
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              queue({ title: e.target.value });
            }}
            onBlur={flush}
            placeholder="Untitled"
            className="min-w-0 flex-1 bg-transparent text-lg font-semibold outline-none"
          />
          <span className="text-xs text-slate-400">
            {save === "saving" ? "Saving…" : save === "dirty" ? "Unsaved" : save === "error" ? "Save failed — retrying on next edit" : "Saved"}
          </span>
          {status}
          <DownloadMenu onPick={download} />
          <Button size="sm" onClick={() => flush().then(() => setPublishOpen(true))}>
            <BookPlus className="h-4 w-4" /> {note.in_book ? "Update in book" : "Add to book"}
          </Button>
          <button onClick={remove} title="Delete note" className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950">
            <Trash2 className="h-4 w-4" />
          </button>
          <button onClick={() => setPanel(!panel)} title={panel ? "Hide assistant" : "Show assistant"} className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            {panel ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
          </button>
        </div>
        <Toolbar editor={editor} />
        {note.document_status === "error" && note.document_error && (
          <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">{note.document_error}</div>
        )}
        <div className="flex-1 overflow-y-auto" onClick={(e) => e.target === e.currentTarget && editor.commands.focus("end")}>
          <div className="mx-auto max-w-3xl px-6 py-6">
            <EditorContent editor={editor} />
          </div>
        </div>
      </div>
      {panel && <AssistantPanel noteId={noteId} editor={editor} onClose={() => setPanel(false)} />}
      {publishOpen && (
        <PublishDialog
          note={note}
          onClose={() => setPublishOpen(false)}
          onDone={() => {
            setPublishOpen(false);
            load();
            onSaved();
          }}
        />
      )}
    </div>
  );
}

function DownloadMenu({ onPick }: { onPick: (fmt: string) => void }) {
  const [open, setOpen] = useState(false);
  const items = [
    { fmt: "docx", label: "Word document (.docx)" },
    { fmt: "pdf", label: "PDF" },
    { fmt: "txt", label: "Plain text (.txt)" },
    { fmt: "md", label: "Markdown (.md)" },
  ];
  return (
    <div className="relative">
      <Button size="sm" variant="secondary" onClick={() => setOpen(!open)}>
        <Download className="h-4 w-4" /> Download <ChevronDown className="h-3.5 w-3.5" />
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute end-0 z-40 mt-1 w-52 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-900">
            {items.map((it) => (
              <button
                key={it.fmt}
                onClick={() => {
                  setOpen(false);
                  onPick(it.fmt);
                }}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                {it.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add to book
// ---------------------------------------------------------------------------

type BookPart = { part: string; chapters: { id: number; title: string; can_insert: boolean }[] };

function PublishDialog({ note, onClose, onDone }: { note: Note; onClose: () => void; onDone: () => void }) {
  const [structure, setStructure] = useState<BookPart[]>([]);
  const [part, setPart] = useState(note.book_part || "");
  const [custom, setCustom] = useState("");
  const [mode, setMode] = useState<"chapter" | "section">("chapter");
  const [chapterId, setChapterId] = useState<number | null>(null);
  const [update, setUpdate] = useState<"replace" | "append">("append");
  const [polish, setPolish] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<BookPart[]>("/api/notes/book-structure").then((s) => {
      setStructure(s);
      if (!part) setPart(s[0]?.part ?? "__new");
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const chapters = (structure.find((p) => p.part === part)?.chapters ?? []).filter((c) => c.can_insert);
  useEffect(() => {
    setChapterId(chapters.length ? chapters[chapters.length - 1].id : null); // default: the part's last chapter
    if (!chapters.length) setMode("chapter");
  }, [part, structure.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    const target = part === "__new" ? custom.trim() : part;
    if (!note.in_book && !target) return setError("Choose a part of the book or name a new one");
    if (!note.in_book && mode === "section" && !chapterId) return setError("Choose the chapter to add the note into");
    setBusy(true);
    setError("");
    try {
      await api.send(`/api/notes/${note.id}/publish`, { part: target, polish, mode, chapter_id: chapterId, update });
      onDone();
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm(`Remove "${note.title}" from the book? The note itself stays in your workspace.`)) return;
    setBusy(true);
    await api.send(`/api/notes/${note.id}/unpublish`);
    onDone();
  };

  const radio = "mt-0.5";
  const box = "mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900";
  const where =
    note.book_mode === "section"
      ? `a section at the end of "${note.book_chapter}" (${note.book_part})`
      : `its own chapter in ${note.book_part}`;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl dark:bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold">{note.in_book ? "Update in book" : "Add to book"}</h3>
            <p className="mt-1 text-sm text-slate-500">
              {note.in_book
                ? `This note is in your book as ${where}.`
                : `"${note.title}" goes into your book and the study chat can answer from it, with page references.`}
            </p>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="h-4 w-4" />
          </button>
        </div>

        {note.in_book ? (
          <div className="mt-4 space-y-2 text-sm">
            <div className="font-medium">What should the book get?</div>
            <label className="flex items-start gap-2">
              <input type="radio" className={radio} checked={update === "append"} onChange={() => setUpdate("append")} />
              <span>
                <span className="font-medium">Add only what's new</span>
                <span className="block text-slate-500">Appends the paragraphs you added since the last time; what is already in the book stays as it is.</span>
              </span>
            </label>
            <label className="flex items-start gap-2">
              <input type="radio" className={radio} checked={update === "replace"} onChange={() => setUpdate("replace")} />
              <span>
                <span className="font-medium">Replace with the current note</span>
                <span className="block text-slate-500">The whole section is rewritten from the note as it is now, including your edits and deletions.</span>
              </span>
            </label>
          </div>
        ) : (
          <>
            <label className="mt-4 block text-sm font-medium">Part of the book</label>
            <select value={part} onChange={(e) => setPart(e.target.value)} className={box}>
              {structure.map((p) => (
                <option key={p.part} value={p.part}>
                  {p.part}
                </option>
              ))}
              <option value="__new">+ New part…</option>
            </select>
            {part === "__new" && (
              <input
                autoFocus
                value={custom}
                onChange={(e) => setCustom(e.target.value)}
                placeholder="e.g. AI & Machine Learning"
                className={box + " outline-none focus:border-brand-400"}
              />
            )}
            <div className="mt-4 space-y-2 text-sm">
              <div className="font-medium">Where in that part?</div>
              <label className="flex items-start gap-2">
                <input type="radio" className={radio} checked={mode === "chapter"} onChange={() => setMode("chapter")} />
                <span>
                  <span className="font-medium">As a new chapter</span>
                  <span className="block text-slate-500">Added after the last chapter of the part.</span>
                </span>
              </label>
              <label className={cx("flex items-start gap-2", !chapters.length && "opacity-50")}>
                <input type="radio" className={radio} disabled={!chapters.length} checked={mode === "section"} onChange={() => setMode("section")} />
                <span className="flex-1">
                  <span className="font-medium">Inside a chapter</span>
                  <span className="block text-slate-500">Appended as a new section after the chapter's last section.</span>
                  {mode === "section" && (
                    <select value={chapterId ?? ""} onChange={(e) => setChapterId(Number(e.target.value))} className={box}>
                      {chapters.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.title}
                        </option>
                      ))}
                    </select>
                  )}
                </span>
              </label>
            </div>
          </>
        )}

        <label className="mt-4 flex items-start gap-2 text-sm">
          <input type="checkbox" checked={polish} onChange={(e) => setPolish(e.target.checked)} className="mt-0.5" />
          <span>
            <span className="font-medium">Rewrite into book style with AI</span>
            <span className="block text-slate-500">
              Adds clear headings and fixes wording. Every fact is kept; sections where the AI would change facts stay as you wrote them. Takes about a
              minute per page.
            </span>
          </span>
        </label>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <div className="mt-5 flex items-center justify-between gap-2">
          {note.in_book ? (
            <button onClick={remove} disabled={busy} className="text-sm text-red-600 hover:underline">
              Remove from book
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={submit} loading={busy}>
              <BookPlus className="h-4 w-4" /> {note.in_book ? "Update" : "Add to book"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assistant
// ---------------------------------------------------------------------------

type Turn = {
  id: number;
  request: string;
  selection: string;
  range: { from: number; to: number };
  result?: AssistResult;
  error?: string;
  state: "loading" | "proposed" | "applied" | "discarded" | "reply";
};

const ACTION_LABEL: Record<AssistResult["action"], string> = {
  insert: "Add to note",
  replace_selection: "Replace selection",
  replace_note: "Rewritten note",
  reply: "Answer",
};

const IDEAS = ["Add a section that explains this topic simply", "Add an example and restructure the note", "Rewrite the selected text more clearly", "Turn the selection into a table"];

function AssistantPanel({ noteId, editor, onClose }: { noteId: number; editor: NonNullable<ReturnType<typeof useEditor>>; onClose: () => void }) {
  const [input, setInput] = useState("");
  const [mentions, setMentions] = useState<Mention[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const bottom = useRef<HTMLDivElement>(null);
  const busy = turns.some((t) => t.state === "loading");

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const update = (id: number, patch: Partial<Turn>) => setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, ...patch } : t)));

  const send = async (text = input) => {
    if (!text.trim() || busy) return;
    const { from, to } = editor.state.selection;
    const selection = from !== to ? editor.state.doc.textBetween(from, to, "\n") : "";
    const turn: Turn = { id: Date.now(), request: text, selection, range: { from, to }, state: "loading" };
    setTurns((ts) => [...ts, turn]);
    setInput("");
    try {
      const result = await api.send<AssistResult>(`/api/notes/${noteId}/assist`, {
        instruction: text,
        selection,
        mentions: activeMentions(text, mentions).map((m) => m.id),
        markdown: htmlToMarkdown(editor.getHTML()),
      });
      update(turn.id, { result, state: result.action === "reply" ? "reply" : "proposed" });
    } catch (e: any) {
      update(turn.id, { error: e.message, state: "discarded" });
    }
  };

  const apply = (t: Turn, asInsert = false) => {
    if (!t.result) return;
    const html = markdownToHtml(t.result.content);
    const action = asInsert ? "insert" : t.result.action;
    const size = editor.state.doc.content.size;
    const clamp = (n: number) => Math.max(0, Math.min(n, size));
    if (action === "replace_note") {
      editor.chain().focus().setContent(html, true).run();
    } else if (action === "replace_selection") {
      editor.chain().focus().insertContentAt({ from: clamp(t.range.from), to: clamp(t.range.to) }, html).run();
    } else {
      // insert where the cursor was when the request was sent (end of the note if it was at the very start of an empty doc)
      const at = t.range.to > 1 ? clamp(t.range.to) : size;
      editor.chain().focus().insertContentAt(at, html).run();
    }
    update(t.id, { state: "applied" });
  };

  return (
    <aside className="hidden w-[380px] shrink-0 flex-col border-s border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-900 md:flex">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <div className="flex items-center gap-2 font-semibold">
          <Sparkles className="h-4 w-4 text-brand-600" /> Assistant
        </div>
        <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {turns.length === 0 && (
          <div className="space-y-3 text-sm text-slate-500">
            <p>
              Ask me to write, explain, rewrite or restructure. Select text in the note first to work on just that part. Type
              <code className="mx-1 rounded bg-white px-1 dark:bg-slate-800">@</code>to bring in another note.
            </p>
            <p>
              I answer from my own knowledge (not your book). When you ask me to add something, I rewrite the whole note with it included and
              restructured — keeping everything you already wrote. Nothing changes until you press Apply.
            </p>
            <div className="space-y-1.5">
              {IDEAS.map((s) => (
                <button key={s} onClick={() => setInput(s)} className="block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-left text-xs hover:border-brand-300 dark:border-slate-700 dark:bg-slate-950">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t) => (
          <div key={t.id} className="space-y-2">
            <div className="ms-6 rounded-xl bg-brand-600 px-3 py-2 text-sm text-white">
              {t.request}
              {t.selection && <div className="mt-1 truncate border-t border-white/20 pt-1 text-xs opacity-80">on selection: “{t.selection.slice(0, 80)}”</div>}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-700 dark:bg-slate-950">
              {t.state === "loading" && (
                <div className="flex items-center gap-2 text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" /> Writing…
                </div>
              )}
              {t.error && <p className="text-red-600">{t.error}</p>}
              {t.result && (
                <>
                  <div className="mb-2 flex flex-wrap items-center gap-1.5 text-xs">
                    <Badge tone={t.result.action === "reply" ? "slate" : "blue"}>{ACTION_LABEL[t.result.action]}</Badge>
                  </div>
                  {t.result.message && <p className="mb-2 text-xs text-slate-500">{t.result.message}</p>}
                  <div className={cx("max-h-80 overflow-y-auto rounded-lg p-2", t.state === "proposed" && "bg-emerald-50/60 ring-1 ring-emerald-200 dark:bg-emerald-950/30 dark:ring-emerald-900")}>
                    <Markdown text={t.result.content} />
                  </div>
                  <div className="mt-2 flex gap-2">
                    {t.state === "proposed" && (
                      <>
                        <Button size="sm" onClick={() => apply(t)}>
                          <Check className="h-3.5 w-3.5" /> Apply
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => update(t.id, { state: "discarded" })}>
                          Discard
                        </Button>
                      </>
                    )}
                    {t.state === "reply" && (
                      <Button size="sm" variant="secondary" onClick={() => apply(t, true)}>
                        <Plus className="h-3.5 w-3.5" /> Insert into note
                      </Button>
                    )}
                    {t.state === "applied" && <span className="text-xs text-emerald-600">Applied ✓ (Ctrl+Z to undo)</span>}
                    {t.state === "discarded" && t.result && <span className="text-xs text-slate-400">Discarded</span>}
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <div className="border-t border-slate-200 p-3 dark:border-slate-800">
        <div className="flex items-end gap-2">
          <MentionTextarea
            value={input}
            onChange={setInput}
            mentions={mentions}
            onMentionsChange={setMentions}
            onSubmit={() => send()}
            rows={2}
            placeholder="e.g. add a line that explains transformers"
          />
          <Button onClick={() => send()} disabled={busy || !input.trim()} aria-label="Send">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}

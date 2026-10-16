import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { BellRing, BookOpen, Loader2, Plus, Send, Square, Trash2 } from "lucide-react";
import { api, fmtDate, streamEvents } from "../../lib/api";
import { ChatMessage, Citation, Session } from "../../lib/types";
import { Markdown } from "../../components/Markdown";
import { QuizCard } from "../../components/QuizCard";
import { SummaryCard } from "../../components/SummaryCard";
import { SourceViewer } from "../../components/SourceViewer";
import { Button, cx } from "../../components/ui";
import { Mention, MentionTextarea, activeMentions } from "../../components/MentionTextarea";

const COMMANDS = [
  { cmd: "/quiz 5 ", label: "/quiz", hint: "test me" },
  { cmd: "/remind ", label: "/remind", hint: "add a reminder" },
  { cmd: "/end", label: "/end", hint: "summary → WhatsApp" },
  { cmd: "/help", label: "/help", hint: "commands" },
];

const STARTERS = [
  "Explain the TCP 3-way handshake with an example",
  "What's the difference between IDS and IPS?",
  "اشرحلي الـ Strategy design pattern",
  "ezay el semaphore bysh8al fl RTOS?",
];

export default function Study() {
  const { id } = useParams();
  const sessionId = id ? Number(id) : null;
  const nav = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [current, setCurrent] = useState<Session | null>(null);
  const [input, setInput] = useState("");
  const [mentions, setMentions] = useState<Mention[]>([]);
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState<Partial<Citation> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const justCreated = useRef<number | null>(null); // session created by send(): keep the optimistic messages
  const bottom = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const loadSessions = useCallback(() => api.get<Session[]>("/api/sessions").then(setSessions), []);
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);
  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      setCurrent(null);
      return;
    }
    if (justCreated.current === sessionId) {
      justCreated.current = null;
      return;
    }
    api.get(`/api/sessions/${sessionId}`).then((r) => {
      setCurrent(r.session);
      setMessages(r.messages);
    });
  }, [sessionId]);
  useEffect(() => {
    // braces matter: newer browsers return a Promise from scrollIntoView, which React would treat as a cleanup
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const newSession = async () => {
    const s = await api.send<Session>("/api/sessions");
    await loadSessions();
    nav(`/admin/study/${s.id}`);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const removeSession = async (sid: number) => {
    if (!confirm("Delete this session and its quiz history?")) return;
    await api.del(`/api/sessions/${sid}`);
    await loadSessions();
    if (sid === sessionId) nav("/admin");
  };

  const updateLast = (fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => {
      const copy = [...prev];
      copy[copy.length - 1] = fn(copy[copy.length - 1]);
      return copy;
    });

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    let sid = sessionId;
    if (!sid) {
      const s = await api.send<Session>("/api/sessions");
      sid = s.id;
      justCreated.current = s.id;
      setCurrent(s);
      nav(`/admin/study/${s.id}`, { replace: true });
    }
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: text, kind: "text" }, { role: "assistant", content: "", kind: "text", streaming: true }]);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await streamEvents(
        `/api/sessions/${sid}/messages`,
        { text, mentions: activeMentions(text, mentions).map((m) => m.id) },
        (e) => {
          switch (e.type) {
            case "status":
              updateLast((m) => ({ ...m, status: e.text }));
              break;
            case "sources":
              updateLast((m) => ({ ...m, sources: e.items }));
              break;
            case "token":
              updateLast((m) => ({ ...m, status: undefined, content: m.content + e.text }));
              break;
            case "quiz":
              updateLast((m) => ({ ...m, kind: "quiz", items: e.items, status: undefined }));
              break;
            case "summary":
              updateLast((m) => ({ ...m, kind: "summary", data: e.data, status: undefined }));
              break;
            case "reminder":
              updateLast((m) => ({ ...m, kind: "reminder", data: e.data, content: e.text, status: undefined }));
              break;
            case "error":
              updateLast((m) => ({ ...m, error: e.text, status: undefined }));
              break;
            case "done":
              updateLast((m) => ({ ...m, streaming: false, status: undefined }));
              break;
          }
        },
        ctrl.signal,
      );
    } catch (err: any) {
      if (err.name !== "AbortError") updateLast((m) => ({ ...m, error: err.message }));
    } finally {
      updateLast((m) => ({ ...m, streaming: false, status: undefined }));
      setBusy(false);
      abortRef.current = null;
      loadSessions();
      api.get(`/api/sessions/${sid}`).then((r) => setCurrent(r.session)).catch(() => {});
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div className="flex h-full">
      {/* sessions */}
      <aside className="hidden w-64 shrink-0 flex-col border-e border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 lg:flex">
        <div className="p-3">
          <Button className="w-full" onClick={newSession}>
            <Plus className="h-4 w-4" /> New study session
          </Button>
        </div>
        <div className="flex-1 space-y-1 overflow-auto px-2 pb-3">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={cx(
                "group flex cursor-pointer items-start gap-2 rounded-lg px-3 py-2 text-sm",
                s.id === sessionId ? "bg-brand-50 text-brand-800 dark:bg-brand-950 dark:text-brand-200" : "hover:bg-slate-100 dark:hover:bg-slate-800",
              )}
              onClick={() => nav(`/admin/study/${s.id}`)}
            >
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{s.title}</div>
                <div className="text-xs text-slate-400">
                  {fmtDate(s.created_at)} {s.ended_at && "· ended"}
                </div>
              </div>
              <button
                className="invisible text-slate-400 hover:text-red-600 group-hover:visible"
                onClick={(e) => {
                  e.stopPropagation();
                  removeSession(s.id);
                }}
                aria-label="Delete session"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
          {sessions.length === 0 && <p className="px-3 text-xs text-slate-400">No sessions yet.</p>}
        </div>
      </aside>

      {/* chat */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5 dark:border-slate-800 dark:bg-slate-900">
          <div className="min-w-0">
            <div className="truncate font-semibold">{current?.title ?? "Study with Megamind"}</div>
            <div className="text-xs text-slate-400">Answers come from your book, with page references</div>
          </div>
          <div className="flex gap-2">
            <a href="/api/library/book.pdf" target="_blank" rel="noreferrer">
              <Button variant="secondary" size="sm">
                <BookOpen className="h-4 w-4" /> <span className="hidden sm:inline">Book</span>
              </Button>
            </a>
            <Button variant="secondary" size="sm" className="lg:hidden" onClick={newSession}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          <div className="mx-auto max-w-3xl space-y-5 px-4 py-6">
            {messages.length === 0 && (
              <div className="py-10 text-center">
                <img src="/megamind-logo.svg" className="mx-auto mb-4 h-20 w-20" alt="" />
                <h2 className="text-xl font-bold">What are we studying today?</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Ask in English, Arabic or Franco. Use <code className="text-brand-600">/quiz</code> to test yourself and{" "}
                  <code className="text-brand-600">/end</code> to get your summary on WhatsApp.
                </p>
                <div className="mx-auto mt-6 grid max-w-xl gap-2 sm:grid-cols-2">
                  {STARTERS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      dir="auto"
                      className="rounded-xl border border-slate-200 bg-white p-3 text-start text-sm hover:border-brand-300 hover:bg-brand-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <MessageView key={m.id ?? `l${i}`} m={m} sessionId={sessionId ?? 0} onSource={setSource} />
            ))}
            <div ref={bottom} />
          </div>
        </div>

        <form onSubmit={submit} className="border-t border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <div className="mx-auto max-w-3xl">
            <div className="mb-2 flex flex-wrap gap-1.5">
              {COMMANDS.map((c) => (
                <button
                  key={c.label}
                  type="button"
                  onClick={() => {
                    setInput(c.cmd);
                    inputRef.current?.focus();
                  }}
                  className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600 hover:border-brand-300 hover:text-brand-700 dark:border-slate-700 dark:text-slate-300"
                >
                  <span className="font-mono font-semibold">{c.label}</span> <span className="text-slate-400">{c.hint}</span>
                </button>
              ))}
            </div>
            <div className="flex items-end gap-2">
              <MentionTextarea
                ref={inputRef}
                value={input}
                onChange={setInput}
                mentions={mentions}
                onMentionsChange={setMentions}
                onSubmit={() => send(input)}
                placeholder="Ask about your notes… type @ to include a note (Enter to send, Shift+Enter for a new line)"
                className="max-h-40 min-h-11 resize-y border-slate-300"
              />
              {busy ? (
                <Button type="button" variant="secondary" onClick={() => abortRef.current?.abort()} aria-label="Stop">
                  <Square className="h-4 w-4" />
                </Button>
              ) : (
                <Button type="submit" aria-label="Send" disabled={!input.trim()}>
                  <Send className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </form>
      </div>
      <SourceViewer source={source} onClose={() => setSource(null)} />
    </div>
  );
}

function MessageView({ m, sessionId, onSource }: { m: ChatMessage; sessionId: number; onSource: (c: Partial<Citation>) => void }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-brand-600 px-4 py-2.5 text-sm text-white" dir="auto">
          {m.content}
        </div>
      </div>
    );
  }
  if (m.kind === "quiz" && m.items) return <QuizCard sessionId={sessionId} items={m.items} onSource={onSource} />;
  if (m.kind === "quiz_result") return null;
  if (m.kind === "summary" && m.data) return <SummaryCard data={m.data} />;
  if (m.kind === "reminder")
    return (
      <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900 dark:bg-amber-950/30">
        <BellRing className="h-4 w-4 text-amber-600" />
        <Markdown text={m.content} />
      </div>
    );
  const sources = m.sources ?? [];
  const cite = (n: number) => {
    const s = sources.find((x) => x.n === n) ?? sources[n - 1];
    if (s) onSource(s);
  };
  return (
    <div className="flex gap-3">
      <img src="/megamind-logo.svg" className="mt-1 h-7 w-7 shrink-0" alt="" />
      <div className="min-w-0 flex-1">
        {m.status && (
          <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
            <Loader2 className="h-3 w-3 animate-spin" /> {m.status}
          </div>
        )}
        {m.content ? (
          <Markdown text={m.content} onCite={cite} />
        ) : (
          m.streaming && !m.status && <span className="animate-pulse text-slate-400">…</span>
        )}
        {m.error && <p className="mt-2 text-sm text-red-600">{m.error}</p>}
        {sources.length > 0 && !m.streaming && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {sources.map((s, i) => (
              <button
                key={s.chunk_id}
                onClick={() => onSource(s)}
                className="flex max-w-full items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1 text-start text-xs hover:border-brand-300 hover:bg-brand-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800"
                title={s.snippet}
              >
                <span className="cite-chip !mx-0">{s.n ?? i + 1}</span>
                <span className="truncate">
                  {s.doc_title} › {s.section.split(" > ").slice(-1)[0]}
                </span>
                {s.book_page && <span className="shrink-0 text-slate-400">p.{s.book_page}</span>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


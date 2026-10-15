import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Briefcase, Github, GraduationCap, Linkedin, Lock, Mail, MapPin, MessageSquare, Send, Sparkles, X } from "lucide-react";
import { api, streamEvents } from "../lib/api";
import { Profile } from "../lib/types";
import { Logo } from "../components/Logo";
import { Markdown } from "../components/Markdown";
import { Button, cx } from "../components/ui";

type RecentWork = { title: string; company: string; project: string; date: string | null; impact: string; tags: string };

export default function Portfolio() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [recent, setRecent] = useState<RecentWork[]>([]);
  const [chatOpen, setChatOpen] = useState(false);

  useEffect(() => {
    api.get("/api/public/profile").then((r) => {
      setProfile(r.profile);
      setRecent(r.recent_work);
    });
  }, []);

  if (!profile) return <div className="flex h-full items-center justify-center text-slate-400">Loading…</div>;
  const links = profile.links ?? {};

  return (
    <div className="min-h-full bg-white dark:bg-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Logo size={32} />
          <nav className="hidden gap-6 text-sm text-slate-600 dark:text-slate-300 sm:flex">
            {["About", "Experience", "Projects", "Skills", "Contact"].map((s) => (
              <a key={s} href={`#${s.toLowerCase()}`} className="hover:text-brand-600">
                {s}
              </a>
            ))}
          </nav>
          <a href="/admin" className="text-slate-400 hover:text-brand-600" title="Owner login" aria-label="Owner login">
            <Lock className="h-4 w-4" />
          </a>
        </div>
      </header>

      {/* Hero */}
      <section id="about" className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-gradient-to-b from-brand-50 via-white to-white dark:from-brand-950/50 dark:via-slate-950 dark:to-slate-950" />
        <div className="mx-auto grid max-w-5xl gap-10 px-4 py-16 md:grid-cols-[1fr_auto] md:py-24">
          <div>
            {profile.current?.role && (
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-medium text-brand-700 dark:border-brand-800 dark:bg-slate-900 dark:text-brand-300">
                <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
                {profile.current.role} @ {profile.current.company}
              </div>
            )}
            <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">{profile.name}</h1>
            <p className="mt-3 text-xl font-medium text-brand-700 dark:text-brand-300">{profile.headline}</p>
            <p className="mt-5 max-w-2xl leading-relaxed text-slate-600 dark:text-slate-300">{profile.summary}</p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              {links.linkedin && (
                <a href={links.linkedin} target="_blank" rel="noreferrer">
                  <Button>
                    <Linkedin className="h-4 w-4" /> LinkedIn
                  </Button>
                </a>
              )}
              {links.github && (
                <a href={links.github} target="_blank" rel="noreferrer">
                  <Button variant="secondary">
                    <Github className="h-4 w-4" /> GitHub
                  </Button>
                </a>
              )}
              <Button variant="secondary" onClick={() => setChatOpen(true)}>
                <Sparkles className="h-4 w-4 text-brand-500" /> Ask Megamind about me
              </Button>
            </div>
            {profile.location && (
              <p className="mt-4 flex items-center gap-1.5 text-sm text-slate-500">
                <MapPin className="h-4 w-4" /> {profile.location}
              </p>
            )}
          </div>
          <div className="hidden items-center md:flex">
            <img src="/megamind-logo.svg" alt="" className="h-48 w-48 drop-shadow-xl" />
          </div>
        </div>
      </section>

      {/* Experience */}
      <Section id="experience" title="Experience" icon={<Briefcase className="h-5 w-5" />}>
        <ol className="relative space-y-8 border-s-2 border-brand-100 ps-6 dark:border-brand-900">
          {profile.experience?.map((e, i) => (
            <li key={i} className="relative">
              <span className="absolute -start-[33px] top-1.5 h-4 w-4 rounded-full border-4 border-white bg-brand-500 dark:border-slate-950" />
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h3 className="text-lg font-semibold">{e.role}</h3>
                <span className="text-sm text-slate-500">
                  {e.start} – {e.end}
                </span>
              </div>
              <div className="text-sm font-medium text-brand-700 dark:text-brand-300">
                {e.company}
                {e.location ? ` · ${e.location}` : ""}
              </div>
              <BulletList items={e.highlights} limit={4} className="leading-relaxed" />
            </li>
          ))}
        </ol>
      </Section>

      {/* Projects */}
      <Section id="projects" title="Projects" icon={<Sparkles className="h-5 w-5" />}>
        <div className="grid gap-4 sm:grid-cols-2">
          {profile.projects?.map((p, i) => (
            <div key={i} className="group rounded-2xl border border-slate-200 p-5 transition hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-lg dark:border-slate-800">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold">{p.name}</h3>
                {p.link && (
                  <a href={p.link} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-brand-600">
                    <ArrowUpRight className="h-4 w-4" />
                  </a>
                )}
              </div>
              <BulletList items={p.highlights} limit={3} />
              <div className="mt-3 flex flex-wrap gap-1.5">
                {p.stack?.map((s) => (
                  <span key={s} className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-950 dark:text-brand-300">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Recent work */}
      {recent.length > 0 && (
        <Section id="recent" title="Recent work" icon={<Briefcase className="h-5 w-5" />}>
          <ul className="grid gap-3 sm:grid-cols-2">
            {recent.map((t, i) => (
              <li key={i} className="rounded-xl bg-slate-50 p-4 text-sm dark:bg-slate-900">
                <div className="font-semibold">{t.title}</div>
                <div className="text-xs text-slate-500">
                  {[t.company, t.project, t.date].filter(Boolean).join(" · ")}
                </div>
                {t.impact && <p className="mt-1 text-slate-600 dark:text-slate-300">{t.impact}</p>}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* Skills */}
      <Section id="skills" title="Skills" icon={<Sparkles className="h-5 w-5" />}>
        <div className="grid gap-5 sm:grid-cols-2">
          {Object.entries(profile.skills ?? {}).map(([cat, items]) => (
            <div key={cat}>
              <div className="mb-2 text-sm font-semibold text-slate-500">{cat}</div>
              <div className="flex flex-wrap gap-1.5">
                {items.map((s) => (
                  <span key={s} className="rounded-full border border-slate-200 px-2.5 py-1 text-xs dark:border-slate-700">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Education */}
      <Section id="education" title="Education & certifications" icon={<GraduationCap className="h-5 w-5" />}>
        <div className="space-y-3">
          {profile.education?.map((e, i) => (
            <div key={i} className="flex flex-wrap justify-between gap-2">
              <div>
                <div className="font-semibold">{e.degree}</div>
                <div className="text-sm text-slate-500">{e.school}</div>
              </div>
              <div className="text-sm text-slate-500">
                {e.start} – {e.end}
              </div>
            </div>
          ))}
          <ul className="list-disc space-y-1 ps-5 text-sm text-slate-600 dark:text-slate-300">
            {profile.certifications?.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      </Section>

      {/* Contact */}
      <Section id="contact" title="Contact" icon={<Mail className="h-5 w-5" />}>
        <div className="flex flex-wrap gap-3">
          {profile.email && (
            <a href={`mailto:${profile.email}`}>
              <Button variant="secondary">
                <Mail className="h-4 w-4" /> {profile.email}
              </Button>
            </a>
          )}
          {links.linkedin && (
            <a href={links.linkedin} target="_blank" rel="noreferrer">
              <Button variant="secondary">
                <Linkedin className="h-4 w-4" /> LinkedIn
              </Button>
            </a>
          )}
          {links.github && (
            <a href={links.github} target="_blank" rel="noreferrer">
              <Button variant="secondary">
                <Github className="h-4 w-4" /> GitHub
              </Button>
            </a>
          )}
        </div>
      </Section>

      <footer className="border-t border-slate-200 py-8 text-center text-xs text-slate-400 dark:border-slate-800">
        Built with Megamind — a local-first AI assistant · © {new Date().getFullYear()} {profile.name}
      </footer>

      {!chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-5 end-5 z-40 flex items-center gap-2 rounded-full bg-brand-600 px-4 py-3 text-sm font-semibold text-white shadow-xl transition hover:bg-brand-700"
        >
          <MessageSquare className="h-5 w-5" /> Ask about Yahia
        </button>
      )}
      {chatOpen && <PublicChat name={profile.name ?? ""} onClose={() => setChatOpen(false)} />}
    </div>
  );
}

/** Bullet list that shows the first `limit` items (the strongest come first) with a toggle for the rest. */
function BulletList({ items = [], limit, className = "" }: { items?: string[]; limit: number; className?: string }) {
  const [open, setOpen] = useState(false);
  const shown = open ? items : items.slice(0, limit);
  return (
    <>
      <ul className={cx("mt-2 list-disc space-y-1 ps-5 text-sm text-slate-600 dark:text-slate-300", className)}>
        {shown.map((h, j) => (
          <li key={j}>{h}</li>
        ))}
      </ul>
      {items.length > limit && (
        <button onClick={() => setOpen(!open)} className="mt-1 ps-5 text-xs font-medium text-brand-600 hover:underline dark:text-brand-400">
          {open ? "Show less" : `Show all ${items.length}`}
        </button>
      )}
    </>
  );
}

function Section({ id, title, icon, children }: { id: string; title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-5xl scroll-mt-20 px-4 py-12">
      <h2 className="mb-6 flex items-center gap-2 text-2xl font-bold tracking-tight">
        <span className="text-brand-600">{icon}</span> {title}
      </h2>
      {children}
    </section>
  );
}

type Msg = { role: "user" | "assistant"; content: string };
const SUGGESTIONS = ["What is Yahia working on now?", "What RAG experience does he have?", "Summarise his security background"];

function PublicChat({ name, onClose }: { name: string; onClose: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "assistant", content: `Hi! I'm Megamind, ${name.split(" ")[0]}'s assistant. Ask me anything about his experience, skills or projects.` },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [msgs]);

  const ask = async (q: string) => {
    if (!q.trim() || busy) return;
    const history = msgs.slice(1);
    setMsgs((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);
    try {
      await streamEvents("/api/public/chat", { question: q, history }, (e) => {
        if (e.type === "token" || e.type === "error")
          setMsgs((m) => {
            const copy = [...m];
            copy[copy.length - 1] = { role: "assistant", content: copy[copy.length - 1].content + e.text };
            return copy;
          });
      });
    } catch (err: any) {
      setMsgs((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `⚠️ ${err.message}` };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    ask(input);
  };

  return (
    <div className="fixed inset-x-3 bottom-3 z-50 flex h-[70vh] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900 sm:inset-x-auto sm:end-5 sm:w-[400px]">
      <div className="flex items-center justify-between bg-brand-600 px-4 py-3 text-white">
        <div className="flex items-center gap-2 font-semibold">
          <img src="/megamind-logo.svg" className="h-7 w-7 rounded-full bg-white/20 p-0.5" alt="" /> Ask Megamind
        </div>
        <button onClick={onClose} aria-label="Close chat">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="flex-1 space-y-3 overflow-auto p-4">
        {msgs.map((m, i) => (
          <div key={i} className={cx("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div
              className={cx(
                "max-w-[85%] rounded-2xl px-3 py-2 text-sm",
                m.role === "user" ? "bg-brand-600 text-white" : "bg-slate-100 dark:bg-slate-800",
              )}
            >
              {m.role === "assistant" ? (m.content ? <Markdown text={m.content} /> : <span className="animate-pulse">…</span>) : m.content}
            </div>
          </div>
        ))}
        {msgs.length === 1 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => ask(s)} className="rounded-full border border-brand-200 px-3 py-1 text-xs text-brand-700 hover:bg-brand-50 dark:border-brand-800 dark:text-brand-300">
                {s}
              </button>
            ))}
          </div>
        )}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="flex gap-2 border-t border-slate-200 p-3 dark:border-slate-800">
        <input
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-950"
          placeholder="Ask about experience, skills…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          dir="auto"
        />
        <Button type="submit" loading={busy} aria-label="Send">
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

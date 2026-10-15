import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CalendarDays, Cpu, Inbox, MessageCircle, Save } from "lucide-react";
import { api, fmtDate } from "../../lib/api";
import { Badge, Button, Card, ErrorNote, Field, Input, PageHeader } from "../../components/ui";

export default function Settings() {
  const [data, setData] = useState<any>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [outbox, setOutbox] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [params] = useSearchParams();

  const load = () => {
    api.get("/api/settings").then((d) => {
      setData(d);
      setValues(d.values);
    });
    api.get("/api/outbox").then(setOutbox);
  };
  useEffect(() => {
    load();
    if (params.get("google") === "connected") {
      const n = Number(params.get("synced") ?? 0);
      setMsg("Google Calendar connected ✓" + (n ? ` — copied ${n} saved reminder${n > 1 ? "s" : ""} to your calendar` : ""));
    }
    if (params.get("google") === "error") setError("Google sign-in failed: " + (params.get("message") ?? ""));
  }, []);

  const save = async () => {
    setBusy("save");
    setError("");
    try {
      const d = await api.send("/api/settings", values, "PUT");
      setData(d);
      setValues(d.values);
      setMsg("Settings saved ✓");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };
  const testWhatsapp = async () => {
    setBusy("wa");
    const r = await api.send("/api/whatsapp/test");
    setMsg(r.status === "sent" ? "Test message sent to WhatsApp ✓" : "");
    setError(r.status === "sent" ? "" : `WhatsApp ${r.status}: ${r.error}`);
    setBusy(null);
    load();
  };
  const connectGoogle = async () => {
    try {
      const { url } = await api.get("/api/google/auth");
      location.href = url;
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (!data) return <div className="p-6 text-slate-400">Loading…</div>;
  const v = (k: string) => values[k] ?? "";
  const set = (k: string) => (e: any) => setValues({ ...values, [k]: e.target.value });

  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-6">
      <PageHeader
        title="Settings"
        actions={
          <Button onClick={save} loading={busy === "save"}>
            <Save className="h-4 w-4" /> Save
          </Button>
        }
      />
      {msg && <p className="mb-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">{msg}</p>}
      <div className="mb-4">
        <ErrorNote error={error} />
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="space-y-3">
          <div className="flex items-center gap-2 font-semibold">
            <MessageCircle className="h-4 w-4 text-emerald-600" /> WhatsApp (CallMeBot, free)
          </div>
          <ol className="list-decimal space-y-1 ps-5 text-xs text-slate-500">
            <li>Save CallMeBot's number from callmebot.com in your phone contacts.</li>
            <li>Send it the WhatsApp message: <code>I allow callmebot to send me messages</code></li>
            <li>Paste the API key it replies with below. Activation can take a while.</li>
          </ol>
          <Field label="Your WhatsApp number (international format)">
            <Input value={v("whatsapp_phone")} onChange={set("whatsapp_phone")} placeholder="+2010xxxxxxxx" />
          </Field>
          <Field label="CallMeBot API key">
            <Input value={v("callmebot_apikey")} onChange={set("callmebot_apikey")} />
          </Field>
          <Field label="Daily briefing time" hint={`Next run: ${data.briefing_next_run ? fmtDate(data.briefing_next_run) : "—"} (${data.timezone})`}>
            <Input type="time" value={v("daily_briefing_time")} onChange={set("daily_briefing_time")} />
          </Field>
          <Button variant="secondary" onClick={testWhatsapp} loading={busy === "wa"}>
            Send a test message
          </Button>
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center gap-2 font-semibold">
            <CalendarDays className="h-4 w-4 text-brand-600" /> Google Calendar
          </div>
          <div className="flex gap-2">
            {data.google.client_configured ? <Badge tone="green">client file found</Badge> : <Badge tone="amber">client file missing</Badge>}
            {data.google.connected ? <Badge tone="green">connected</Badge> : <Badge>not connected</Badge>}
          </div>
          <ol className="list-decimal space-y-1 ps-5 text-xs text-slate-500">
            <li>In Google Cloud Console create a project and enable the Google Calendar API (free).</li>
            <li>OAuth consent screen: External, add yourself as a test user.</li>
            <li>
              Credentials → OAuth client ID → <b>Web application</b>, authorised redirect URI:
              <code className="mt-1 block break-all">{data.google.redirect_uri}</code>
            </li>
            <li>
              Download the JSON and save it as <code>data/google/client_secret.json</code>, then click Connect.
            </li>
          </ol>
          <div className="flex gap-2">
            <Button onClick={connectGoogle} disabled={!data.google.client_configured}>
              {data.google.connected ? "Reconnect" : "Connect Google Calendar"}
            </Button>
            {data.google.connected && (
              <Button variant="secondary" onClick={() => api.send("/api/google/disconnect").then(load)}>
                Disconnect
              </Button>
            )}
          </div>
        </Card>

        <Card className="space-y-3">
          <div className="flex items-center gap-2 font-semibold">
            <Cpu className="h-4 w-4 text-violet-600" /> AI model
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            {data.llm.ollama ? <Badge tone="green">Ollama running</Badge> : <Badge tone="red">Ollama not reachable</Badge>}
            {data.llm.models.map((m: string) => (
              <Badge key={m}>{m}</Badge>
            ))}
          </div>
          <Field label="Provider" hint="ollama = local and free. anthropic = any Anthropic Messages-compatible API (e.g. the Claude API, paid).">
            <select className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950" value={v("llm_provider")} onChange={set("llm_provider")}>
              <option value="ollama">ollama</option>
              <option value="anthropic">anthropic</option>
            </select>
          </Field>
          <Field label="Local chat model (Ollama)">
            <Input value={v("chat_model")} onChange={set("chat_model")} />
          </Field>
          {v("llm_provider") === "anthropic" && (
            <>
              <Field label="API base URL">
                <Input value={v("anthropic_base_url")} onChange={set("anthropic_base_url")} />
              </Field>
              <Field label="API key">
                <Input value={v("anthropic_api_key")} onChange={set("anthropic_api_key")} />
              </Field>
              <Field label="Model">
                <Input value={v("anthropic_model")} onChange={set("anthropic_model")} />
              </Field>
            </>
          )}
        </Card>

        <Card>
          <div className="mb-3 flex items-center gap-2 font-semibold">
            <Inbox className="h-4 w-4" /> Outbox
          </div>
          <ul className="max-h-80 space-y-2 overflow-auto">
            {outbox.map((o) => (
              <li key={o.id} className="rounded-lg border border-slate-200 p-2 text-xs dark:border-slate-700">
                <div className="flex justify-between gap-2">
                  <span className="font-semibold">{o.subject || "Message"}</span>
                  <Badge tone={o.status === "sent" ? "green" : o.status === "failed" ? "red" : "amber"}>{o.status}</Badge>
                </div>
                <div className="text-slate-400">{fmtDate(o.created_at)}</div>
                <details className="mt-1">
                  <summary className="cursor-pointer text-slate-500">Show message</summary>
                  <pre className="mt-1 whitespace-pre-wrap font-sans">{o.body}</pre>
                  {o.error && <p className="text-red-600">{o.error}</p>}
                </details>
              </li>
            ))}
            {outbox.length === 0 && <li className="text-xs text-slate-400">Nothing sent yet.</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* not JSON */
    }
    if (res.status === 401 && !location.pathname.startsWith("/login") && location.pathname.startsWith("/admin")) {
      location.href = "/login?next=" + encodeURIComponent(location.pathname);
    }
    throw new ApiError(res.status, msg);
  }
  const type = res.headers.get("content-type") || "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export const api = {
  get: <T = any>(url: string) => fetch(url, { credentials: "same-origin" }).then((r) => handle<T>(r)),
  del: <T = any>(url: string) => fetch(url, { method: "DELETE", credentials: "same-origin" }).then((r) => handle<T>(r)),
  send: <T = any>(url: string, body?: unknown, method = "POST") =>
    fetch(url, {
      method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then((r) => handle<T>(r)),
  form: <T = any>(url: string, form: FormData) =>
    fetch(url, { method: "POST", credentials: "same-origin", body: form }).then((r) => handle<T>(r)),
};

/** POST a JSON body and consume a text/event-stream response, one parsed event at a time. */
export async function streamEvents(url: string, body: unknown, onEvent: (e: any) => void, signal?: AbortSignal) {
  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    await handle(res);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = raw.split("\n").find((l) => l.startsWith("data:"));
      if (line) {
        try {
          onEvent(JSON.parse(line.slice(5).trim()));
        } catch {
          /* ignore malformed */
        }
      }
    }
  }
}

export const fmtDate = (s?: string | null) =>
  s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";

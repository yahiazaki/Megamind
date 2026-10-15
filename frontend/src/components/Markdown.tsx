import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Markdown renderer; inline citations like [2], [n2] or [1, 3] become clickable chips. */
export function Markdown({ text, onCite }: { text: string; onCite?: (n: number) => void }) {
  const withCites = onCite
    ? text.replace(/\[((?:n?\d{1,2}\s*,\s*)*n?\d{1,2})\](?!\()/g, (_, list: string) =>
        list
          .split(",")
          .map((s) => s.trim().replace(/^n/, ""))
          .map((n) => `[${n}](#cite-${n})`)
          .join(""),
      )
    : text;
  return (
    <div className="prose-mm" dir="auto">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#cite-") && onCite) {
              const n = Number(href.slice(6));
              return (
                <span className="cite-chip" onClick={() => onCite(n)} title="Open the source in your notes">
                  {n}
                </span>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {withCites}
      </ReactMarkdown>
    </div>
  );
}

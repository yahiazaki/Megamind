import { marked } from "marked";
import TurndownService from "turndown";
// @ts-expect-error: the plugin ships without type declarations
import { gfm } from "turndown-plugin-gfm";

const td = new TurndownService({ headingStyle: "atx", bulletListMarker: "-", codeBlockStyle: "fenced", emDelimiter: "*" });
td.use(gfm);
// TipTap task items: <li data-type="taskItem" data-checked="true"><label>…</label><div><p>text</p></div></li>
td.addRule("taskItem", {
  filter: (node) => node.nodeName === "LI" && (node as HTMLElement).getAttribute("data-type") === "taskItem",
  replacement: (content, node) => {
    const el = node as HTMLElement;
    const body = el.querySelector("div");
    const text = body ? td.turndown(body.innerHTML) : content;
    return `- [${el.getAttribute("data-checked") === "true" ? "x" : " "}] ${text.trim()}\n`;
  },
});

/** Editor HTML → markdown (what the RAG system and the AI assistant read). */
export const htmlToMarkdown = (html: string) => td.turndown(html || "");

/** Markdown from the AI assistant → HTML the editor can insert. */
export const markdownToHtml = (md: string) => marked.parse(md || "", { async: false, gfm: true }) as string;

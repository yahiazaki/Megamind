import { Editor, useEditorState } from "@tiptap/react";
import {
  Bold,
  Code2,
  Highlighter,
  Italic,
  Link2,
  List,
  ListChecks,
  ListOrdered,
  Minus,
  Quote,
  Redo2,
  RemoveFormatting,
  Strikethrough,
  Table2,
  Underline as UnderlineIcon,
  Undo2,
} from "lucide-react";
import { ReactNode } from "react";
import { cx } from "../ui";

const SIZES = [
  { label: "Small", value: "13px" },
  { label: "Normal", value: "" },
  { label: "Large", value: "20px" },
  { label: "Huge", value: "28px" },
];

function Btn({ on, active, title, children, disabled }: { on: () => void; active?: boolean; title: string; children: ReactNode; disabled?: boolean }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()} // keep the editor selection
      onClick={on}
      className={cx(
        "grid h-8 w-8 place-items-center rounded-md text-slate-600 transition hover:bg-slate-100 disabled:opacity-40 dark:text-slate-300 dark:hover:bg-slate-800",
        active && "bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200",
      )}
    >
      {children}
    </button>
  );
}

const Sep = () => <span className="mx-1 h-5 w-px bg-slate-200 dark:bg-slate-700" />;

export function Toolbar({ editor }: { editor: Editor }) {
  // re-render the toolbar when the selection or marks change
  const s = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      block: e.isActive("heading", { level: 1 }) ? "h1" : e.isActive("heading", { level: 2 }) ? "h2" : e.isActive("heading", { level: 3 }) ? "h3" : "p",
      size: (e.getAttributes("textStyle").fontSize as string) || "",
      bold: e.isActive("bold"),
      italic: e.isActive("italic"),
      underline: e.isActive("underline"),
      strike: e.isActive("strike"),
      highlight: e.isActive("highlight"),
      bullet: e.isActive("bulletList"),
      ordered: e.isActive("orderedList"),
      task: e.isActive("taskList"),
      quote: e.isActive("blockquote"),
      code: e.isActive("codeBlock"),
      link: e.isActive("link"),
      canUndo: e.can().undo(),
      canRedo: e.can().redo(),
    }),
  });
  const c = () => editor.chain().focus();

  const setBlock = (v: string) => {
    if (v === "p") c().setParagraph().run();
    else c().toggleHeading({ level: Number(v[1]) as 1 | 2 | 3 }).run();
  };
  const setSize = (v: string) => (v ? c().setFontSize(v).run() : c().unsetFontSize().run());
  const setLink = () => {
    const prev = editor.getAttributes("link").href as string | undefined;
    const url = window.prompt("Link address (leave empty to remove)", prev ?? "https://");
    if (url === null) return;
    if (!url.trim()) c().extendMarkRange("link").unsetLink().run();
    else c().extendMarkRange("link").setLink({ href: url.trim() }).run();
  };

  const select = "h-8 rounded-md border border-slate-200 bg-white px-2 text-sm dark:border-slate-700 dark:bg-slate-900";
  return (
    <div className="flex flex-wrap items-center gap-0.5 border-b border-slate-200 px-3 py-1.5 dark:border-slate-800">
      <select className={select} value={s.block} onChange={(e) => setBlock(e.target.value)} title="Text style">
        <option value="p">Normal text</option>
        <option value="h1">Heading 1</option>
        <option value="h2">Heading 2</option>
        <option value="h3">Heading 3</option>
      </select>
      <select className={cx(select, "ms-1")} value={s.size} onChange={(e) => setSize(e.target.value)} title="Font size">
        {SIZES.map((z) => (
          <option key={z.label} value={z.value}>
            {z.label}
          </option>
        ))}
      </select>
      <Sep />
      <Btn title="Bold (Ctrl+B)" active={s.bold} on={() => c().toggleBold().run()}>
        <Bold className="h-4 w-4" />
      </Btn>
      <Btn title="Italic (Ctrl+I)" active={s.italic} on={() => c().toggleItalic().run()}>
        <Italic className="h-4 w-4" />
      </Btn>
      <Btn title="Underline (Ctrl+U)" active={s.underline} on={() => c().toggleUnderline().run()}>
        <UnderlineIcon className="h-4 w-4" />
      </Btn>
      <Btn title="Strikethrough" active={s.strike} on={() => c().toggleStrike().run()}>
        <Strikethrough className="h-4 w-4" />
      </Btn>
      <Btn title="Highlight" active={s.highlight} on={() => c().toggleHighlight().run()}>
        <Highlighter className="h-4 w-4" />
      </Btn>
      <Btn title="Link" active={s.link} on={setLink}>
        <Link2 className="h-4 w-4" />
      </Btn>
      <Sep />
      <Btn title="Bullet list" active={s.bullet} on={() => c().toggleBulletList().run()}>
        <List className="h-4 w-4" />
      </Btn>
      <Btn title="Numbered list" active={s.ordered} on={() => c().toggleOrderedList().run()}>
        <ListOrdered className="h-4 w-4" />
      </Btn>
      <Btn title="Checklist" active={s.task} on={() => c().toggleTaskList().run()}>
        <ListChecks className="h-4 w-4" />
      </Btn>
      <Btn title="Quote" active={s.quote} on={() => c().toggleBlockquote().run()}>
        <Quote className="h-4 w-4" />
      </Btn>
      <Btn title="Code block" active={s.code} on={() => c().toggleCodeBlock().run()}>
        <Code2 className="h-4 w-4" />
      </Btn>
      <Btn title="Insert table" on={() => c().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>
        <Table2 className="h-4 w-4" />
      </Btn>
      <Btn title="Divider" on={() => c().setHorizontalRule().run()}>
        <Minus className="h-4 w-4" />
      </Btn>
      <Btn title="Clear formatting" on={() => c().unsetAllMarks().clearNodes().run()}>
        <RemoveFormatting className="h-4 w-4" />
      </Btn>
      <Sep />
      <Btn title="Undo (Ctrl+Z)" disabled={!s.canUndo} on={() => c().undo().run()}>
        <Undo2 className="h-4 w-4" />
      </Btn>
      <Btn title="Redo (Ctrl+Y)" disabled={!s.canRedo} on={() => c().redo().run()}>
        <Redo2 className="h-4 w-4" />
      </Btn>
    </div>
  );
}

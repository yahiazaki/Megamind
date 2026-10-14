"""Manual translation round-trip for the source notes.

  python scripts/translate_tool.py extract          # list paragraphs needing translation
  python scripts/translate_tool.py show <slug> <n>  # print batch n of a document as JSON
  python scripts/translate_tool.py apply            # write translated .docx files

Translations live in data/translation/<slug>.en.json (or per-batch <slug>.en.<n>.json files)
as {"<paragraph id>": "english", ...}.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ingest import translate  # noqa: E402

DATA = ROOT.parent / "data"
SRC = DATA / "sources"
TR = DATA / "translation"
OUT = DATA / "translated"
BATCH_CHARS = 6000


def batches(items):
    batch, size = [], 0
    for it in items:
        if batch and size + len(it["text"]) > BATCH_CHARS:
            yield batch
            batch, size = [], 0
        batch.append(it)
        size += len(it["text"])
    if batch:
        yield batch


def cmd_extract():
    TR.mkdir(parents=True, exist_ok=True)
    for f in sorted(SRC.glob("*.docx")):
        items = translate.extract(f)
        (TR / f"{f.stem}.items.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        n_batches = len(list(batches(items)))
        chars = sum(len(i["text"]) for i in items)
        print(f"{f.stem:20} paragraphs={len(items):5} chars={chars:7} batches={n_batches}")


def cmd_show(slug, n):
    items = json.loads((TR / f"{slug}.items.json").read_text(encoding="utf-8"))
    b = list(batches(items))[int(n)]
    print(json.dumps({str(i["id"]): i["text"] for i in b}, ensure_ascii=False, indent=0))


def cmd_apply():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in sorted(SRC.glob("*.docx")):
        items_file = TR / f"{f.stem}.items.json"
        tr = {}
        for en_file in sorted(TR.glob(f"{f.stem}.en*.json")):  # <slug>.en.json or per-batch <slug>.en.<n>.json
            tr.update({int(k): v for k, v in json.loads(en_file.read_text(encoding="utf-8")).items()})
        need = len(json.loads(items_file.read_text(encoding="utf-8"))) if items_file.exists() else 0
        changed = translate.apply(f, OUT / f.name, tr)
        print(f"{f.stem:20} translated {changed}/{need}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    {"extract": cmd_extract, "show": lambda: cmd_show(sys.argv[2], sys.argv[3]), "apply": cmd_apply}[cmd]()

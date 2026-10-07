"""Hierarchical document memory.

Builds a navigable tree (Doc -> Chapters -> Sections -> Paragraphs) for any uploaded
file. Summarizes non-leaf nodes with Haiku 4.5 and embeds every node with OpenAI
text-embedding-3-small. At query time, walks the tree top-down and returns the few
passages that actually matter, with a DOC_MAP the engine can navigate.

Public surface:
    extract(filename, mime, base64_str) -> (vision_blocks, inline_text, tree_id_or_None)
        - Small file (<= INLINE_TOKEN_CAP): returns inline text, no tree.
        - Big file: kicks off async indexing, returns tree_id placeholder.
    build_tree_sync(tree_id, raw_text, filename) -> None     # ran in BackgroundTasks
    recall(thread_id, user_msg, max_passages=5) -> str        # ready-to-inject DOC block
    list_active_trees(thread_id) -> list of {filename, status, node_count}
"""
import io
import re
import base64
import logging
import time
import uuid
from datetime import datetime, timezone

import numpy as np
from typing import Optional
from db import db

log = logging.getLogger(__name__)

# Budgets / thresholds (tuned for cost vs. quality)
INLINE_TOKEN_CAP = 8_000          # chars below this -> inline, no tree
CHUNK_TOKENS_TARGET = 500          # ~500 tokens per leaf paragraph
CHUNK_OVERLAP = 50                 # token overlap between leaves
CHARS_PER_TOKEN = 4                # rough conversion
MAX_LEAVES_PER_SECTION = 12        # group leaves into sections when no native headings
MAX_SECTIONS_PER_CHAPTER = 8
EMBED_MODEL = "BAAI/bge-small-en-v1.5"   # local fastembed (ONNX, ~80MB), 384-dim, no API quota
EMBED_DIM = 384
SUMMARIZE_MODEL = "deepseek-flash"     # cheap summarizer for cascade
TOP_CHAPTERS = 3
TOP_SECTIONS = 3
TOP_PARAGRAPHS = 5

# Collection handles for doc trees and their nodes.
trees_col = db.doc_trees if db is not None else None
nodes_col = db.doc_nodes if db is not None else None

# ---------------------------------------------------------------- clients (lazy)
_embedder = None
_anth = None
def _get_embedder():
    """Lazy-load fastembed once per process. Model weights cached on disk after first run."""
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(EMBED_MODEL)
    return _embedder

# Lazily get the shared LLM client for summarization.
def _llm_client():
    from llm_client import client
    return client()

# ---------------------------------------------------------------- file parsing
def _parse_pdf(b: bytes):
    """Returns (full_text, structured_chapters) where chapters is a list of
    {title, text} pulled from PDF outline/bookmarks (if present)."""
    import fitz
    chapters = []
    full = []
    with fitz.open(stream=b, filetype="pdf") as d:
        # try outline first
        toc = d.get_toc() or []
        page_texts = [p.get_text() for p in d]
        full = "\n".join(page_texts)
        if toc:
            # outline rows: [level, title, page_number(1-indexed)]
            outline = [(lvl, title.strip(), max(0, pg - 1)) for lvl, title, pg in toc]
            for i, (lvl, title, start) in enumerate(outline):
                end = outline[i + 1][2] if i + 1 < len(outline) else len(page_texts)
                chunk = "\n".join(page_texts[start:end]).strip()
                if chunk:
                    chapters.append({"title": title, "text": chunk, "level": min(lvl, 3)})
    return full, chapters

def _parse_docx(b: bytes):
    """Reads paragraph styles. Heading 1/2/3 -> chapters with hierarchy."""
    import docx
    d = docx.Document(io.BytesIO(b))
    chapters, current = [], None
    full = []
    for p in d.paragraphs:
        t = (p.text or "").strip()
        if not t:
            continue
        full.append(t)
        style = (p.style.name or "").lower() if p.style else ""
        if style.startswith("heading"):
            level = 1
            m = re.search(r"\d+", style)
            if m:
                level = int(m.group(0))
            if current:
                chapters.append(current)
            current = {"title": t, "text": "", "level": min(level, 3)}
        else:
            if current is None:
                current = {"title": "Opening", "text": "", "level": 1}
            current["text"] += t + "\n"
    if current:
        chapters.append(current)
    return "\n".join(full), chapters

def _parse_pptx(b: bytes):
    """Each slide is a section; slide title is the heading."""
    import pptx
    pres = pptx.Presentation(io.BytesIO(b))
    chapters, full = [], []
    for i, slide in enumerate(pres.slides, 1):
        title = f"Slide {i}"
        bullets = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for p in shape.text_frame.paragraphs:
                txt = "".join(r.text for r in p.runs).strip()
                if not txt:
                    continue
                if not bullets and not title.lower().startswith("slide"):
                    pass
                if shape == slide.shapes[0] and title.startswith("Slide "):
                    title = txt
                else:
                    bullets.append(txt)
        body = "\n".join(bullets)
        full.append(f"# {title}\n{body}")
        if body or title != f"Slide {i}":
            chapters.append({"title": title, "text": body, "level": 1})
    return "\n".join(full), chapters

def _parse_markdown(text: str):
    """Splits on # / ## / ### headings."""
    lines = text.split("\n")
    chapters, current = [], None
    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m:
            if current:
                chapters.append(current)
            current = {"title": m.group(2).strip(), "text": "", "level": min(len(m.group(1)), 3)}
        else:
            if current is None:
                current = {"title": "Opening", "text": "", "level": 1}
            current["text"] += line + "\n"
    if current:
        chapters.append(current)
    return text, chapters

# Parse HTML into chapters from heading tags.
def _parse_html(b: bytes):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(b, "lxml")
    for s in soup(["script", "style"]):
        s.decompose()
    # collect h1/h2/h3 + following content
    chapters, current = [], None
    for el in soup.find_all(["h1", "h2", "h3", "p", "li", "pre", "code"]):
        t = el.get_text(" ", strip=True)
        if not t:
            continue
        if el.name in ("h1", "h2", "h3"):
            if current:
                chapters.append(current)
            current = {"title": t, "text": "", "level": int(el.name[1])}
        else:
            if current is None:
                current = {"title": "Opening", "text": "", "level": 1}
            current["text"] += t + "\n"
    if current:
        chapters.append(current)
    full = soup.get_text("\n", strip=True)
    return full, chapters

def _parse_json(b: bytes):
    """Pretty-print and treat top-level keys as chapters."""
    import json as _j
    try:
        data = _j.loads(b.decode("utf-8", errors="replace"))
    except Exception:
        return b.decode("utf-8", errors="replace"), []
    chapters = []
    if isinstance(data, dict):
        for k, v in data.items():
            txt = _j.dumps(v, indent=2)[:20000]
            chapters.append({"title": str(k), "text": txt, "level": 1})
    elif isinstance(data, list):
        for i, v in enumerate(data[:50]):
            txt = _j.dumps(v, indent=2)[:8000]
            chapters.append({"title": f"Item {i}", "text": txt, "level": 1})
    full = _j.dumps(data, indent=2)
    return full, chapters

def _parse_xlsx(b: bytes):
    """Sheet -> chapter; header row -> section labels; row clusters -> sub-sections."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(b), data_only=True, read_only=True)
    chapters, full = [], []
    for sheet in wb.sheetnames[:10]:
        ws = wb[sheet]
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= 5000:
                break
            rows.append("\t".join("" if v is None else str(v) for v in row))
        body = "\n".join(rows)
        chapters.append({"title": f"Sheet: {sheet}", "text": body, "level": 1})
        full.append(f"### Sheet: {sheet}\n{body}")
    return "\n".join(full), chapters

def _parse_csv(b: bytes):
    """Treat the whole CSV as one chapter (rows are leaves; header is the title)."""
    import csv as _csv
    text = b.decode("utf-8", errors="replace")
    rdr = _csv.reader(io.StringIO(text))
    rows = list(rdr)
    if not rows:
        return text, []
    header = ", ".join(rows[0])
    body = "\n".join(", ".join(r) for r in rows[1:5000])
    return text, [{"title": f"CSV columns: {header}", "text": body, "level": 1}]

def _parse_plain(text: str):
    """No structure -> single chapter, semantic chunking handles leaves later."""
    return text, [{"title": "Document", "text": text, "level": 1}]

# Extension-to-parser mapping for structured files.
EXT_DISPATCH = {
    ".pdf": ("pdf", _parse_pdf, True),
    ".docx": ("docx", _parse_docx, True),
    ".pptx": ("pptx", _parse_pptx, True),
    ".md": ("md", lambda b: _parse_markdown(b.decode("utf-8", errors="replace")), True),
    ".markdown": ("md", lambda b: _parse_markdown(b.decode("utf-8", errors="replace")), True),
    ".html": ("html", _parse_html, True),
    ".htm": ("html", _parse_html, True),
    ".json": ("json", _parse_json, True),
    ".xlsx": ("xlsx", _parse_xlsx, True),
    ".xls": ("xlsx", _parse_xlsx, True),
    ".csv": ("csv", _parse_csv, True),
}
# Extensions treated as unstructured plain text.
PLAIN_EXTS = (".txt", ".log", ".py", ".js", ".ts", ".tsx", ".jsx",
              ".sql", ".yaml", ".yml", ".ini", ".conf", ".sh", ".rb", ".go", ".rs",
              ".java", ".c", ".cpp", ".h", ".css", ".scss", ".env", ".toml")

def parse_file(filename: str, mime: str, raw: bytes):
    """Returns (kind, full_text, chapters[]).  chapters may be empty for plain files."""
    lower = (filename or "").lower()
    for ext, (kind, fn, _binary) in EXT_DISPATCH.items():
        if lower.endswith(ext):
            try:
                full, chapters = fn(raw)
                return kind, full, chapters
            except Exception as e:
                log.warning(f"{ext} parser failed for {filename}: {e}")
                break
    if mime == "application/pdf":
        try:
            full, chapters = _parse_pdf(raw)
            return "pdf", full, chapters
        except Exception:
            pass
    if any(lower.endswith(e) for e in PLAIN_EXTS) or mime.startswith("text/"):
        text = raw.decode("utf-8", errors="replace")
        return "plain", *_parse_plain(text)
    # last resort: decode and treat as text
    text = raw.decode("utf-8", errors="replace")
    return "plain", *_parse_plain(text)

# ---------------------------------------------------------------- chunking
def _semantic_chunks(text: str, target_tokens: int = CHUNK_TOKENS_TARGET):
    """Split text into ~target_tokens chunks, prefer paragraph boundaries."""
    if not text:
        return []
    target_chars = target_tokens * CHARS_PER_TOKEN
    paragraphs = re.split(r"\n\s*\n", text)
    chunks, buf = [], ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) + 2 > target_chars and buf:
            chunks.append(buf.strip())
            buf = p
        else:
            buf = (buf + "\n\n" + p) if buf else p
    if buf.strip():
        chunks.append(buf.strip())
    # if some chunks are still too big (single huge paragraph) -> hard-split
    out = []
    for c in chunks:
        if len(c) <= target_chars * 1.5:
            out.append(c)
        else:
            for i in range(0, len(c), target_chars):
                out.append(c[i:i + target_chars])
    return out

# ---------------------------------------------------------------- embeddings
def _embed_batch(texts):
    """Batch embed up to 100 texts at once. Returns list[np.array(384,)]."""
    if not texts:
        return []
    # fastembed handles batching internally; trim each item defensively so the ONNX session
    # never sees an unbounded input.
    trimmed = [(t or " ")[:8_000] for t in texts]
    vecs = list(_get_embedder().embed(trimmed))
    return [np.asarray(v, dtype=np.float32) for v in vecs]

# Embed a single text into a vector.
def _embed_one(text: str):
    return _embed_batch([text])[0]

# Cosine similarity between two embedding vectors.
def _cos(a: np.ndarray, b: np.ndarray):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

# ---------------------------------------------------------------- summarization (Haiku cascade)
def _summarize(title: str, children_summaries: list, max_words: int = 60):
    """One Haiku call to compress N child summaries into a single tight gist."""
    if not children_summaries:
        return title or ""
    if len(children_summaries) == 1 and len(children_summaries[0]) < 200:
        return children_summaries[0]
    bullets = "\n".join(f"- {s[:400]}" for s in children_summaries[:30])
    prompt = (
        f"Below are summaries of the children of a section titled '{title}'.\n"
        f"Write ONE plain-English summary of the whole section in at most {max_words} words. "
        f"Capture the concrete facts/numbers/claims that matter. No fluff, no preamble.\n\n{bullets}"
    )
    try:
        r = _llm_client().messages.create(
            model=SUMMARIZE_MODEL, max_tokens=180,
            messages=[{"role": "user", "content": prompt}]
        )
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        return txt or (title or "")
    except Exception as e:
        log.warning(f"summarize failed: {e}")
        # fallback: just concat first parts of children
        return (" ".join(children_summaries))[:max_words * 6]

# ---------------------------------------------------------------- tree build
def extract(filename: str, mime: str, b64: str, thread_id: Optional[str]):
    """Entry point called on every attachment.

    Small files: return (vision_blocks, inline_text, None) -> engine reads inline.
    Big files:   return ([], "", tree_id) and schedule async indexing -> engine
                 will retrieve passages via recall() instead of seeing inline text.
    Image files: return vision_blocks (unchanged behaviour).
    Returns (vision_blocks: list, inline_text: str, tree_id: str | None).
    """
    if not b64:
        return [], "", None
    mime_l = (mime or "").lower()
    # Images go through the existing vision pipeline.
    IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
    if mime_l in IMAGE_MIMES:
        return ([{"type": "image", "source": {"type": "base64", "media_type": mime_l, "data": b64}}],
                f"\n\nATTACHED_IMAGE: {filename} - read it as evidence/context for the user's situation.",
                None)
    try:
        raw = base64.b64decode(b64)
    except Exception:
        return [], f"\n\n[attached file '{filename}' could not be decoded]", None
    try:
        kind, full_text, chapters = parse_file(filename, mime_l, raw)
    except Exception as e:
        log.warning(f"parse_file failed {filename}: {e}")
        return [], f"\n\n[attached file '{filename}' could not be parsed: {e}]", None

    # Small enough -> inline (faster + cheaper, no indexing needed)
    if len(full_text) <= INLINE_TOKEN_CAP * CHARS_PER_TOKEN:
        return [], f"\n\n--- ATTACHED FILE: {filename} ---\n{full_text[:50_000]}\n--- END FILE ---", None

    # Big -> create tree row, defer indexing
    tree_id = "tree_" + uuid.uuid4().hex[:16]
    trees_col.insert_one({
        "tree_id": tree_id, "thread_id": thread_id, "filename": filename,
        "mime": mime_l, "kind": kind, "status": "processing",
        "total_chars": len(full_text), "node_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # caller is responsible for invoking build_tree_sync(tree_id, full_text, chapters, filename)
    # in a BackgroundTask so the user response isn't blocked.
    return [], (f"\n\n[ATTACHED FILE: {filename} - {len(full_text):,} chars. "
                f"Being indexed in the background as a navigable tree. "
                f"For THIS turn, here's the first 4,000 chars as a preview:]\n"
                f"{full_text[:16_000]}\n[...truncated, full doc will be queryable shortly]"), tree_id


def build_tree_sync(tree_id: str, full_text: str, chapters: list, filename: str):
    """Build the hierarchical tree.  Runs in a BackgroundTasks worker.

    Levels:
      0 = document root (has summary + embedding)
      1 = chapter (native heading OR synthesised cluster)
      2 = section (only used when native headings have 2+ levels)
      4 = leaf paragraph (has raw text + embedding)
    """
    started = time.time()
    try:
        # 1. Pick the chapter structure.  If no native chapters, synthesise them
        #    by clustering semantic chunks (no Haiku titles -> keeps cost low).
        if not chapters:
            chunks = _semantic_chunks(full_text)
            # group every MAX_LEAVES_PER_SECTION chunks into one "chapter"
            chapters = []
            for i in range(0, len(chunks), MAX_LEAVES_PER_SECTION):
                group = chunks[i:i + MAX_LEAVES_PER_SECTION]
                chapters.append({
                    "title": f"Part {i // MAX_LEAVES_PER_SECTION + 1}",
                    "text": "\n\n".join(group),
                    "level": 1,
                })

        nodes_to_insert = []
        chapter_summaries = []
        for ch_idx, ch in enumerate(chapters):
            ch_id = "node_" + uuid.uuid4().hex[:16]
            leaf_texts = _semantic_chunks(ch.get("text", ""))
            if not leaf_texts:
                leaf_texts = [ch.get("title", "")]
            # Embed all leaves in this chapter in one batch
            leaf_vecs = _embed_batch(leaf_texts)
            leaf_summaries = []
            for li, (ltxt, lvec) in enumerate(zip(leaf_texts, leaf_vecs)):
                leaf_id = "node_" + uuid.uuid4().hex[:16]
                # Short summary = first sentence
                first_sent = (ltxt.split(".", 1)[0] + ".")[:240]
                leaf_summaries.append(first_sent)
                nodes_to_insert.append({
                    "node_id": leaf_id, "tree_id": tree_id, "parent_id": ch_id,
                    "level": 4, "position": li,
                    "title": None, "summary": first_sent, "text": ltxt,
                    "summary_embedding": lvec.tolist(),
                    "text_embedding": lvec.tolist(),  # leaves: summary == text vector
                    "token_count": len(ltxt) // CHARS_PER_TOKEN,
                })
            # Chapter summary via Haiku cascade
            ch_title = ch.get("title") or f"Chapter {ch_idx + 1}"
            ch_summary = _summarize(ch_title, leaf_summaries, max_words=60)
            ch_vec = _embed_one(ch_summary or ch_title)
            chapter_summaries.append(ch_summary)
            nodes_to_insert.append({
                "node_id": ch_id, "tree_id": tree_id, "parent_id": None,
                "level": 1, "position": ch_idx,
                "title": ch_title, "summary": ch_summary, "text": None,
                "summary_embedding": ch_vec.tolist(),
                "text_embedding": None,
                "token_count": sum((len(t) // CHARS_PER_TOKEN) for t in leaf_texts),
            })

        # Insert all nodes in one go
        if nodes_to_insert:
            nodes_col.insert_many(nodes_to_insert)
        # Doc-level summary (root)
        doc_summary = _summarize(filename, chapter_summaries, max_words=80)
        trees_col.update_one({"tree_id": tree_id}, {"$set": {
            "status": "ready",
            "node_count": len(nodes_to_insert),
            "doc_summary": doc_summary,
            "build_seconds": round(time.time() - started, 1),
            "ready_at": datetime.now(timezone.utc).isoformat(),
        }})
        log.info(f"tree {tree_id} ready: {len(nodes_to_insert)} nodes in {time.time() - started:.1f}s")
    except Exception as e:
        log.exception(f"tree build failed {tree_id}: {e}")
        trees_col.update_one({"tree_id": tree_id}, {"$set": {
            "status": "failed", "error": str(e)[:500],
        }})


# ---------------------------------------------------------------- retrieval
def recall(thread_id: str, user_msg: str, max_passages: int = TOP_PARAGRAPHS) -> str:
    """Return a ready-to-inject DOC block for the engine prompt.

    Returns "" if no indexed trees on this thread, or retrieval fails.
    """
    if not thread_id or not user_msg or trees_col is None:
        return ""
    trees = list(trees_col.find({"thread_id": thread_id, "status": "ready"}).limit(3))
    if not trees:
        return ""
    try:
        qvec = _embed_one(user_msg)
    except Exception as e:
        log.warning(f"recall embed failed: {e}")
        return ""

    chosen_passages = []  # [(score, tree, chapter, paragraph_doc)]
    doc_map_lines = []
    for tr in trees:
        tree_id = tr["tree_id"]
        # 1. score chapters
        chapters = list(nodes_col.find({"tree_id": tree_id, "level": 1}))
        if not chapters:
            continue
        scored_chapters = []
        for ch in chapters:
            vec = np.array(ch.get("summary_embedding") or [], dtype=np.float32)
            if vec.size == 0:
                continue
            scored_chapters.append((_cos(qvec, vec), ch))
        scored_chapters.sort(key=lambda x: x[0], reverse=True)
        top_ch = scored_chapters[:TOP_CHAPTERS]
        # Build the DOC_MAP for this tree
        doc_map_lines.append(f"From '{tr['filename']}':")
        for s, ch in scored_chapters[:6]:
            marker = " <-- relevant" if (s, ch) in top_ch else ""
            doc_map_lines.append(f"  - {ch['title']} [score {s:.2f}]{marker}")
        # 2. for each top chapter, score its paragraphs
        for s_ch, ch in top_ch:
            paragraphs = list(nodes_col.find({"tree_id": tree_id, "parent_id": ch["node_id"], "level": 4}))
            scored_paragraphs = []
            for p in paragraphs:
                pv = np.array(p.get("text_embedding") or [], dtype=np.float32)
                if pv.size == 0:
                    continue
                scored_paragraphs.append((_cos(qvec, pv), tr, ch, p))
            scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
            chosen_passages.extend(scored_paragraphs[:TOP_PARAGRAPHS])

    if not chosen_passages:
        return ""
    chosen_passages.sort(key=lambda x: x[0], reverse=True)
    chosen_passages = chosen_passages[:max_passages]

    out = ["", "DOC_MAP (the engine can navigate these chapters):"]
    out.extend(doc_map_lines)
    out.append("")
    out.append("RETRIEVED_PASSAGES (the most relevant evidence for the user's current message - ground your answer here, cite by chapter):")
    for score, tr, ch, p in chosen_passages:
        snippet = (p.get("text") or "")[:1200]
        out.append(f"[{tr['filename']} -> {ch['title']}] (score {score:.2f})")
        out.append(snippet)
        out.append("")
    return "\n".join(out)

def list_active_trees(thread_id: str):
    """Used by ThreadPage to show indexing progress / file list."""
    if trees_col is None or not thread_id:
        return []
    return list(trees_col.find(
        {"thread_id": thread_id},
        {"_id": 0, "tree_id": 1, "filename": 1, "status": 1, "node_count": 1, "kind": 1, "created_at": 1, "doc_summary": 1}
    ).sort("created_at", -1).limit(10))

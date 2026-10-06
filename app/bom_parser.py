"""
Coordinate based BOM extraction.

The plain-text extractor in summary.py reads the PDF as a stream of lines and
only finds the first BOM block of a drawing.  Engineering drawings usually carry
several dispatchable-unit (DU) BOM blocks stacked on top of each other, so this
module reads the text *with positions* instead:

  * every part row is anchored on its specification cell (IS:2062 ...)
  * stray annotation digits (smaller font / different baseline) are ignored
  * each part is attached to the DU row of its block, so the DU quantity can be
    applied and the totals can be cross-checked against the DU weights.
"""

import re
from statistics import median

import pymupdf

from app.summary import _extract_abstract, _clean

# Specification cell, e.g.  IS:2062 / IS 2062 / ASTM A36 / EN10025
SPEC_RE = re.compile(
    r"^(?:IS|ASTM|EN|BS|DIN|JIS)\s*[:\-]?\s*[A-Z]*\d[\w./\-]*$",
    re.IGNORECASE,
)

# Dispatchable unit row:  CODE  DESCRIPTION  [ITEMCODE]  TYPE  UOM  QTY  WEIGHT  [REMARK]
DU_RE = re.compile(
    r"^(?P<code>\S+)\s+(?P<desc>.*?)\s+(?P<type>[A-Z])\s+"
    r"(?P<uom>[A-Z]{1,4})\s+(?P<qty>\d+)\s+(?P<wt>\d+(?:\.\d+)?)(?:\s+\S+)?$"
)

NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
ITEM_CODE_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9]{8,}$", re.IGNORECASE)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _page_spans(page):
    """All text spans of a page with their position and font size."""
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = _clean(span["text"])
                if not text:
                    continue
                x0, y0, x1, y1 = span["bbox"]
                spans.append(
                    {
                        "text": text,
                        "x0": x0,
                        "x1": x1,
                        "y0": y0,
                        "y1": y1,
                        "size": span["size"],
                    }
                )
    return spans


def _same_size(a, b, tolerance=0.12):
    return abs(a - b) <= tolerance * max(a, b)


def _parse_part_row(tokens):
    """tokens (left -> right) of a row that contains a specification cell."""
    spec_index = next(
        (i for i, t in enumerate(tokens) if SPEC_RE.fullmatch(t)), None
    )
    if spec_index is None:
        return None

    left = [t for t in tokens[:spec_index] if t != "0"]
    right = list(tokens[spec_index + 1:])

    if not left or not re.fullmatch(r"\d+", left[0]):
        return None

    # Locate "<qty> <weight>" followed by at most an item code and a stray
    # one-character cell (e.g. the sheet grid letter printed in the border).
    found = None
    for j in range(len(right) - 1, 0, -1):
        after = right[j + 1:]
        if len(after) > 2:
            break
        if (
            NUMBER_RE.fullmatch(right[j])
            and re.fullmatch(r"\d+", right[j - 1])
            and all(len(t) == 1 or ITEM_CODE_RE.fullmatch(t) for t in after)
        ):
            found = j
            break

    if found is None:
        return None

    weight, qty = right[found], right[found - 1]
    item_code = next(
        (t for t in right[found + 1:] if ITEM_CODE_RE.fullmatch(t)), ""
    )
    size_tokens = right[: found - 1]  # size = everything before the quantity

    return {
        "part_no": left[0],
        "description": _clean(" ".join(left[1:])),
        "specification": tokens[spec_index],
        "size": _clean(" ".join(size_tokens)),
        "qty": int(qty),
        "weight_kg": float(weight),
        "item_code": item_code,
    }


def _group_rows(spans, size, tolerance):
    """Cluster spans of the BOM font size into rows by baseline."""
    spans = sorted(
        (s for s in spans if _same_size(s["size"], size)),
        key=lambda s: (s["y0"], s["x0"]),
    )
    rows = []
    for span in spans:
        if rows and abs(span["y0"] - rows[-1]["y"]) <= tolerance:
            rows[-1]["spans"].append(span)
        else:
            rows.append({"y": span["y0"], "spans": [span]})
    for row in rows:
        row["spans"].sort(key=lambda s: s["x0"])
    return rows


# --------------------------------------------------------------------------
# DU grouping
# --------------------------------------------------------------------------

def _assign_to_blocks(entries, bottom_up):
    """
    entries: rows sorted by y, each ("part", dict) or ("du", dict).
    bottom_up=True  -> a DU row sits BELOW the parts that belong to it.
    bottom_up=False -> a DU row sits ABOVE the parts that belong to it.
    Returns list of blocks: {"du": dict|None, "parts": [..]}
    """
    sequence = entries if bottom_up else list(reversed(entries))
    blocks, pending = [], []

    for kind, item in sequence:
        if kind == "part":
            pending.append(item)
        else:
            blocks.append({"du": item, "parts": pending})
            pending = []

    if pending:
        blocks.append({"du": None, "parts": pending})

    return blocks


def _block_score(blocks):
    """How many DU blocks have parts that add up to the DU weight."""
    score = 0
    for block in blocks:
        du = block["du"]
        if not du or not block["parts"]:
            continue
        total = sum(p["weight_kg"] for p in block["parts"])
        target = du["weight_kg"]
        for candidate in (target, target / max(du["qty"], 1)):
            if abs(total - candidate) <= max(0.05, 0.002 * candidate):
                score += 1
                break
    return score


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def parse_page(page):
    """
    Returns {"blocks": [...], "anchor": fitz.Rect|None} for one page or None
    when the page has no BOM rows.
    """
    spans = _page_spans(page)
    anchors = [s for s in spans if SPEC_RE.fullmatch(s["text"])]
    if not anchors:
        return None

    size = median(s["size"] for s in anchors)
    spec_x = median(s["x0"] for s in anchors)

    # Row pitch from the anchors; cells of one row may be offset by ~1 pt, so
    # rows are clustered with a tolerance of 40 % of the pitch.
    anchor_ys = sorted(s["y0"] for s in anchors)
    gaps = [b - a for a, b in zip(anchor_ys, anchor_ys[1:]) if b - a > 0.5 * size]
    pitch = median(gaps) if gaps else 2.5 * size
    tolerance = max(0.6, 0.4 * pitch)

    rows = _group_rows(spans, size, tolerance)

    # --- Part-number column: the left-most cell of the part rows (median, so a
    # stray digit next to the table cannot move it).
    wide_limit = spec_x - 40 * size
    first_x = []
    for row in rows:
        row_spans = [s for s in row["spans"] if s["x0"] >= wide_limit]
        if row_spans and any(SPEC_RE.fullmatch(t) for s in row_spans for t in s["text"].split()):
            first_x.append(row_spans[0]["x0"])
    if not first_x:
        return None
    pno_x = median(first_x)
    left_limit = pno_x - 2 * size

    entries = []
    part_rows = []

    for row in rows:
        row_spans = [s for s in row["spans"] if s["x0"] >= left_limit]
        if not row_spans:
            continue
        tokens = " ".join(s["text"] for s in row_spans).split()
        if any(SPEC_RE.fullmatch(t) for t in tokens):
            part = _parse_part_row(tokens)
            if part:
                part["_y"] = row["y"]
                entries.append(("part", part))
                part_rows.append(part)

    if not part_rows:
        return None

    # --- DU rows: same font size, inside the BOM y-range, left of the P.NO. column
    ys = sorted(p["_y"] for p in part_rows)
    y_min, y_max = ys[0] - 2 * pitch, ys[-1] + 2 * pitch

    part_ys = {round(p["_y"], 1) for p in part_rows}
    du_left_limit = pno_x - 40 * size
    for row in rows:
        if not (y_min <= row["y"] <= y_max) or round(row["y"], 1) in part_ys:
            continue
        row_spans = [s for s in row["spans"] if s["x0"] >= du_left_limit]
        if not row_spans or row_spans[0]["x0"] >= pno_x - 2 * size:
            continue
        text = " ".join(s["text"] for s in row_spans)
        match = DU_RE.match(text)
        if not match or match.group("code") == "0":
            continue
        entries.append(
            (
                "du",
                {
                    "code": match.group("code"),
                    "qty": int(match.group("qty")),
                    "weight_kg": float(match.group("wt")),
                    "_y": row["y"],
                },
            )
        )

    entries.sort(key=lambda e: e[1]["_y"])

    bottom_up = _assign_to_blocks(entries, True)
    top_down = _assign_to_blocks(entries, False)
    blocks = bottom_up if _block_score(bottom_up) >= _block_score(top_down) else top_down

    return {"blocks": blocks}


def extract_bom(pdf_path):
    """
    Read every page of the drawing and return:
      {
        "parts":      [part dicts incl. dispatch qty / block info],
        "blocks":     [DU blocks],
        "bom_page":   index of the first page holding a BOM,
        "checks":     [human readable consistency notes],
      }
    Returns None when no BOM rows could be located by coordinates.
    """
    doc = pymupdf.open(pdf_path)
    parts, blocks_all, bom_page, checks = [], [], None, []

    try:
        for page_index, page in enumerate(doc):
            parsed = parse_page(page)
            if not parsed:
                continue
            if bom_page is None:
                bom_page = page_index
            blocks_all.extend(parsed["blocks"])
    finally:
        doc.close()

    if bom_page is None:
        return None

    for number, block in enumerate(blocks_all, start=1):
        du = block["du"]
        multiplier = du["qty"] if du else 1
        block_total = round(sum(p["weight_kg"] for p in block["parts"]), 2)

        if du:
            ok = abs(block_total - du["weight_kg"]) <= max(0.05, 0.002 * du["weight_kg"])
            checks.append(
                f"{du['code']}: parts {block_total} vs DU weight {du['weight_kg']} "
                f"-> {'OK' if ok else 'MISMATCH'}"
            )

        for part in block["parts"]:
            parts.append(
                {
                    **{k: v for k, v in part.items() if not k.startswith("_")},
                    "dispatch_unit": du["code"] if du else "",
                    "dispatch_qty": multiplier,
                    "block": number,
                    # weight used for the abstract = part weight x number of DUs
                    "weight_kg": round(part["weight_kg"] * multiplier, 4),
                }
            )

    # keep the abstract in part-number order (1,2,3 ...), blocks in drawing order
    parts.sort(key=lambda p: (int(p["part_no"]), p["block"]))

    return {
        "parts": parts,
        "blocks": blocks_all,
        "bom_page": bom_page,
        "checks": checks,
    }


def build_abstract(parts):
    """Abstract rows [{sr_no, section, total}, ..., Grand Total] for the parts."""
    return _extract_abstract(parts)
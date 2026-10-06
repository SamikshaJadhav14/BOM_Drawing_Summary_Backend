"""
Stamp the ABSTRACT table onto the uploaded drawing PDF.

Nothing is hard coded to one drawing.  For every PDF the page is rasterised,
the drawing frame is detected, and the biggest EMPTY rectangle is searched,
first in the right-hand part of the sheet and only then (fallback) on the whole
sheet.  The table is drawn as vector graphics, scaled to fit that rectangle.
If no usable gap exists, the table is appended on an extra page instead of
being drawn over existing drawing content.
"""

import numpy as np
import pymupdf

# ---- table look (same palette as the previous generated summary) -----------
HEADER_BG = (0x1F / 255, 0x4E / 255, 0x78 / 255)
ROW_ALT_BG = (0xF2 / 255, 0xF2 / 255, 0xF2 / 255)
TOTAL_BG = (0xD9 / 255, 0xEA / 255, 0xF7 / 255)
GRID = (0.5, 0.5, 0.5)
WHITE = (1, 1, 1)
BLACK = (0, 0, 0)

FONT = "helv"
FONT_BOLD = "hebo"

# ---- layout rules ------------------------------------------------------------
ROW_H = 1.55          # row height  = ROW_H  x font size
TITLE_H = 1.25        # "ABSTRACT" heading row
PAD_X = 0.55          # horizontal cell padding = PAD_X x font size
MAX_FONT = 6.0        # never draw bigger than this (pt)
MIN_FONT = 3.0        # below this the right-hand gap is rejected
FREE_GAP = 1.5        # clearance kept around existing drawing content (pt)
RIGHT_FRACTION = 0.30  # "right side" = right 30 % of the sheet frame
WHITE_LEVEL = 248     # gray level at/above which a pixel counts as empty


# ----------------------------------------------------------------------------
# table geometry
# ----------------------------------------------------------------------------

def _text_len(text, bold, size):
    return pymupdf.get_text_length(text, fontname=FONT_BOLD if bold else FONT, fontsize=size)


def _table_text(rows):
    """Header + body cells as strings (same formatting as the summary PDF)."""
    body = []
    for row in rows:
        total = row.get("total", 0)
        try:
            total_text = f"{float(total):.2f}"
        except (TypeError, ValueError):
            total_text = str(total)
        body.append(
            (
                str(row.get("sr_no", "")),
                str(row.get("section", "")),
                total_text,
                str(row.get("section", "")).strip().lower() == "grand total",
            )
        )
    return body


def _natural_columns(body):
    """Column widths for a font size of 1pt (they scale linearly)."""
    sr = max([_text_len("SR. NO.", True, 1)] + [_text_len(r[0], False, 1) for r in body])
    sec = max([_text_len("SECTION", True, 1)] + [_text_len(r[1], r[3], 1) for r in body])
    tot = max([_text_len("TOTAL", True, 1)] + [_text_len(r[2], r[3], 1) for r in body])
    pad = 2 * PAD_X
    return [sr + pad, sec + pad, tot + pad]


def _natural_size(body):
    """(width, height) of the table for a font size of 1pt."""
    width = sum(_natural_columns(body))
    height = TITLE_H + ROW_H * (len(body) + 1)
    return width, height


# ----------------------------------------------------------------------------
# finding the empty space
# ----------------------------------------------------------------------------

def _find_frame(page):
    """Inner sheet frame: the smallest big rectangle drawn on the page."""
    pr = page.rect
    best = None
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if r.width >= 0.80 * pr.width and r.height >= 0.75 * pr.height:
            if r.width <= pr.width + 1 and r.height <= pr.height + 1:
                if best is None or r.width * r.height < best.width * best.height:
                    best = pymupdf.Rect(r)
    if best is None:
        best = pymupdf.Rect(
            pr.x0 + 0.03 * pr.width, pr.y0 + 0.03 * pr.height,
            pr.x1 - 0.03 * pr.width, pr.y1 - 0.03 * pr.height,
        )
    return best


def _occupancy(page, clip, scale):
    """Boolean mask (True = something is drawn) of `clip`, `scale` px per pt."""
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale),
        clip=clip,
        colorspace=pymupdf.csGRAY,
        alpha=False,
    )
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    return gray < WHITE_LEVEL


def _dilate(mask, radius):
    """Grow occupied pixels by `radius` px (square window, integral image)."""
    if radius <= 0:
        return mask
    k = 2 * radius + 1
    padded = np.pad(mask.astype(np.int32), radius)
    integral = np.pad(padded.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    h, w = mask.shape
    window = (
        integral[k:k + h, k:k + w]
        - integral[0:h, k:k + w]
        - integral[k:k + h, 0:w]
        + integral[0:h, 0:w]
    )
    return window > 0


def _best_free_rect(free, scale, nat_w, nat_h):
    """
    Walk every maximal empty rectangle (histogram method) and keep the one on
    which the table can be drawn with the biggest font.
    Returns (font, area_pt2, (x0, y0, x1, y1) in pt relative to the mask) or None.
    """
    rows, cols = free.shape
    heights = np.zeros(cols, dtype=np.int32)
    best = None

    for y in range(rows):
        heights = np.where(free[y], heights + 1, 0)
        stack = []  # (start_x, height)
        for x in range(cols + 1):
            current = int(heights[x]) if x < cols else 0
            start = x
            while stack and stack[-1][1] >= current:
                sx, sh = stack.pop()
                width_pt = (x - sx) / scale
                height_pt = sh / scale
                if sh > 0:
                    font = min(width_pt / nat_w, height_pt / nat_h)
                    key = (min(font, MAX_FONT), width_pt * height_pt)
                    if best is None or key > best[0]:
                        best = (
                            key,
                            (sx / scale, (y - sh + 1) / scale, x / scale, (y + 1) / scale),
                        )
                start = sx
            stack.append((start, current))

    if best is None:
        return None
    (font, area), rect = best
    return font, area, rect


def _search(page, frame, region, scale, nat_w, nat_h):
    """Best free rectangle inside `region` (page coordinates)."""
    region = region & frame
    if region.is_empty or region.width < 10 or region.height < 10:
        return None
    mask = _occupancy(page, region, scale)
    free = ~_dilate(mask, int(round(FREE_GAP * scale)))
    found = _best_free_rect(free, scale, nat_w, nat_h)
    if not found:
        return None
    font, _area, (x0, y0, x1, y1) = found
    return font, pymupdf.Rect(
        region.x0 + x0, region.y0 + y0, region.x0 + x1, region.y0 + y1
    )


def find_free_space(page, body):
    """
    Returns (font_size, rect, where) or None.
    where is 'right' (preferred), 'sheet' (fallback).
    """
    nat_w, nat_h = _natural_size(body)
    frame = _find_frame(page)

    right = pymupdf.Rect(
        frame.x1 - RIGHT_FRACTION * frame.width, frame.y0, frame.x1, frame.y1
    )
    hit = _search(page, frame, right, 2, nat_w, nat_h)
    if hit and hit[0] >= MIN_FONT:
        return hit[0], hit[1], "right"

    hit = _search(page, frame, frame, 1, nat_w, nat_h)
    if hit and hit[0] >= MIN_FONT:
        return hit[0], hit[1], "sheet"

    return None


# ----------------------------------------------------------------------------
# drawing the table
# ----------------------------------------------------------------------------

def _draw_table(page, body, rect, font, fill_width=True, fill_height=True):
    """Draw the table inside `rect` using a font size of at most `font`."""
    font = min(font, MAX_FONT)
    nat_cols = _natural_columns(body)
    nat_w = sum(nat_cols)
    n_body = len(body)

    inner = pymupdf.Rect(rect)
    inner.x0 += 0.3
    inner.y0 += 0.3
    inner.x1 -= 0.3
    inner.y1 -= 0.3

    # width: natural width, widened to use the space (keeps columns in ratio)
    width = nat_w * font
    if fill_width:
        width = min(inner.width, max(width, 0.0) * 2.4)
        width = max(width, nat_w * font)
    col_w = [c / nat_w * width for c in nat_cols]

    # height: rows get any spare height, but never more than 2 x font
    unit = TITLE_H + ROW_H * (n_body + 1)
    row_h = ROW_H * font
    title_h = TITLE_H * font
    if fill_height:
        spare = inner.height - unit * font
        if spare > 0:
            bump = min(spare / (n_body + 2), 0.45 * font)
            row_h += bump
            title_h += bump
    height = title_h + row_h * (n_body + 1)

    x0 = inner.x0 + (inner.width - width) / 2
    y0 = inner.y0 + (inner.height - height) / 2
    lw = max(0.12, 0.045 * font)

    shape = page.new_shape()

    def cell(x, y, w, h, fill=None):
        shape.draw_rect(pymupdf.Rect(x, y, x + w, y + h))
        shape.finish(color=GRID, fill=fill, width=lw)

    # heading "ABSTRACT"
    page.insert_text(
        (x0, y0 + title_h * 0.78), "ABSTRACT",
        fontsize=font * 1.05, fontname=FONT_BOLD, color=BLACK,
    )
    y = y0 + title_h

    # header
    xs = [x0]
    for w in col_w:
        xs.append(xs[-1] + w)
    texts = []
    for i, label in enumerate(("SR. NO.", "SECTION", "TOTAL")):
        cell(xs[i], y, col_w[i], row_h, fill=HEADER_BG)
        texts.append((i, label, True, WHITE, y))
    y += row_h

    # body
    last = n_body - 1
    for index, (sr, section, total, is_total) in enumerate(body):
        fill = TOTAL_BG if is_total else (WHITE if index % 2 == 0 else ROW_ALT_BG)
        for i in range(3):
            cell(xs[i], y, col_w[i], row_h, fill=fill)
        for i, value in enumerate((sr, section, total)):
            texts.append((i, value, is_total, BLACK, y))
        y += row_h

    # strong line above the grand total (as in the summary PDF)
    if body and body[last][3]:
        top = y - row_h
        shape.draw_line((xs[0], top), (xs[-1], top))
        shape.finish(color=HEADER_BG, width=lw * 2.4)

    shape.commit()

    # text on top of the cells
    pad = PAD_X * font
    for col, value, bold, color, row_top in texts:
        if not value:
            continue
        name = FONT_BOLD if bold else FONT
        length = pymupdf.get_text_length(value, fontname=name, fontsize=font)
        if col == 0:
            tx = xs[0] + (col_w[0] - length) / 2          # centred
        elif col == 2:
            tx = xs[3] - pad - length                       # right aligned
        else:
            tx = xs[1] + pad                                # left aligned
        ty = row_top + row_h / 2 + 0.34 * font
        page.insert_text((tx, ty), value, fontsize=font, fontname=name, color=color)

    return pymupdf.Rect(x0, y0, x0 + width, y0 + height)


# ----------------------------------------------------------------------------
# public API
# ----------------------------------------------------------------------------

def stamp_abstract(input_pdf, output_pdf, abstract_rows, page_index=0):
    """
    Copy `input_pdf` to `output_pdf` with the abstract table drawn in the empty
    space of page `page_index`.

    Returns a small dict describing what was done:
        {"page": int, "placement": "right" | "sheet" | "extra_page",
         "font_size": float, "rect": [x0, y0, x1, y1]}
    """
    body = _table_text(abstract_rows)
    if not body:
        raise ValueError("Abstract is empty - nothing to place on the drawing.")

    doc = pymupdf.open(input_pdf)
    try:
        page_index = min(max(page_index, 0), len(doc) - 1)
        page = doc[page_index]

        # work in unrotated page space so analysis and drawing agree
        rotation = page.rotation
        if rotation:
            page.set_rotation(0)

        placement = find_free_space(page, body)

        if placement:
            font, rect, where = placement
            used = _draw_table(page, body, rect, font)
            result = {"page": page_index, "placement": where}
        else:
            # no empty area big enough: never draw over the drawing, append a page
            page_rect = page.rect
            new_page = doc.new_page(width=page_rect.width, height=page_rect.height)
            nat_w, nat_h = _natural_size(body)
            margin = 36
            font = min(
                MAX_FONT * 1.5,
                (page_rect.width - 2 * margin) / nat_w,
                (page_rect.height - 2 * margin) / nat_h,
            )
            area = pymupdf.Rect(
                margin, margin,
                margin + nat_w * font + 1, margin + nat_h * font + 1,
            )
            used = _draw_table(new_page, body, area, font, fill_width=False, fill_height=False)
            result = {"page": len(doc) - 1, "placement": "extra_page"}

        if rotation:
            page.set_rotation(rotation)

        result.update(
            {
                "font_size": round(min(font, MAX_FONT), 2),
                "rect": [round(v, 1) for v in (used.x0, used.y0, used.x1, used.y1)],
            }
        )
        doc.save(output_pdf, deflate=True)
        return result
    finally:
        doc.close()
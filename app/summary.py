import re


# -----------------------------------------------------------------
# Regex patterns anchored to distinctive field FORMATS rather than
# position, because PyMuPDF's get_text() emits title-block labels
# and values as separate line clusters that do not line up 1:1.
# -----------------------------------------------------------------

DOCUMENT_ID_PATTERN = re.compile(r"\b([A-Z]{2}\d{5}-\d{6,12}-[A-Z]{2,4}-\d{4})\b")
PROJECT_ID_PATTERN = re.compile(r"\b([A-Z]{2}-\d{5})\b")
ELEMENT_ID_PATTERN = re.compile(r"\b(\d{2}-\d{2}-\d{2}-\d{2}-\d{2})\b")
SCALE_PATTERN = re.compile(r"^(\d{1,2}:\d{1,3})$", re.MULTILINE)
SHEET_SIZE_PATTERN = re.compile(r"^(A[0-4])$", re.MULTILINE)
YEAR_PATTERN = re.compile(r"^(20\d{2})$", re.MULTILINE)
TOTAL_WEIGHT_PATTERN = re.compile(r"Tag\nTotal\nIT\.WT\n([\d.]+)")
DEPARTMENT_PATTERN = re.compile(
    r"^(MECHANICAL|ELECTRICAL|CIVIL|STRUCTURAL|PROCESS|PIPING|INSTRUMENTATION)$",
    re.MULTILINE,
)

# Parts table: 7-line repeating groups -> part_no, description, spec, size, qty, weight, code
PART_ROW_PATTERN = re.compile(
    r"(?P<part_no>\d+)\n"
    r"(?P<description>PLATE|ISA\s+\S+)\n"
    r"(?P<spec>IS:\d+)\n"
    r"(?P<size>.+?)\n"
    r"(?P<quantity>\d+)\n"
    r"(?P<weight>[\d.]+)\n"
    r"(?P<code>[A-Z0-9]+)\n"
)

# Hardware table: 8-line repeating groups (leading "0"), EA or KG uom
HARDWARE_ROW_PATTERN = re.compile(
    r"0\n"
    r"(?P<code>[A-Z0-9]+)\n"
    r"(?P<description>.+?)\n"
    r"(?P<type>[A-Z])\n"
    r"(?P<remark>\S+)\n"
    r"(?P<quantity>\d+)\n"
    r"(?P<weight>[\d.]+)\n"
    r"(?P<uom>EA|KG)\n"
)

# Dispatchable Unit block: appears once, right before the parts rows, UOM fixed as KG
DU_PATTERN = re.compile(
    r"(?P<du_no>[A-Z0-9]+)\n"
    r"(?P<description>.+?)\n"
    r"(?P<type>[A-Z])\n"
    r"(?P<remark>\S+)\n"
    r"(?P<quantity>\d+)\n"
    r"(?P<weight>[\d.]+)\n"
    r"KG\n"
    r"(?P<code>[A-Z0-9]+)\n"
)

# -----------------------------------------------------------------
# Common-dimension summarization
#
# Groups parts that share the same WIDTH and THICKNESS and sums
# their LENGTHS into one combined entry, e.g. two plates
# "20 x 30 x 12 THK" and "250 x 30 x 12 THK" (same width=30,
# thickness=12) become one summary row "270x30x12".
#
# Two size formats are handled:
#   - Plates:  size is "L x W x T [THK]"            -> width, thickness read directly
#   - Angles:  size is "<length> LG."                -> width/thickness come from the
#              description, e.g. "ISA 50x50x6"       -> width=50, thickness=6
# -----------------------------------------------------------------

SIZE_LWT_PATTERN = re.compile(
    r"^\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*(?:THK\.?)?\s*$"
)
PROFILE_WWT_PATTERN = re.compile(r"([\d.]+)\s*[xX×]\s*([\d.]+)\s*[xX×]\s*([\d.]+)")
LENGTH_LG_PATTERN = re.compile(r"^\s*([\d.]+)\s*LG\.?\s*$", re.IGNORECASE)


def _parse_part_dimensions(part):
    """
    Return (length, width, thickness) for a part, or None if its
    size doesn't match a recognized "L x W x T" or "<length> LG."
    (with profile dims in the description) format.
    """
    size = part.get("size", "")
    description = part.get("description", "")

    m = SIZE_LWT_PATTERN.match(size)
    if m:
        length, width, thickness = (float(x) for x in m.groups())
        return length, width, thickness

    profile_m = PROFILE_WWT_PATTERN.search(description)
    length_m = LENGTH_LG_PATTERN.match(size)
    if profile_m and length_m:
        width, _leg2, thickness = (float(x) for x in profile_m.groups())
        length = float(length_m.group(1))
        return length, width, thickness

    return None


def _format_number(n):
    return str(int(n)) if float(n).is_integer() else str(n)


def summarize_common_dimensions(parts):
    """
    Group parts by (specification, width, thickness) and sum their
    lengths into a single combined dimension per group.

    Returns a list of rows:
      {
        "combined_size": "270x30x12",
        "specification": "IS:2062",
        "part_count": 2,
        "part_nos": "A, B",
      }
    sorted by thickness then width. Parts whose size doesn't match a
    recognized format are skipped (not included in any group).
    """
    groups = {}

    for part in parts:
        parsed = _parse_part_dimensions(part)
        if parsed is None:
            continue
        length, width, thickness = parsed
        spec = part.get("specification", "")
        key = (spec, width, thickness)
        g = groups.setdefault(
            key,
            {
                "spec": spec,
                "width": width,
                "thickness": thickness,
                "total_length": 0.0,
                "part_nos": [],
            },
        )
        g["total_length"] += length
        g["part_nos"].append(str(part.get("part_no", "")))

    rows = []
    for (_spec, width, thickness), g in sorted(
        groups.items(), key=lambda kv: (kv[0][2], kv[0][1])
    ):
        rows.append(
            {
                "combined_size": (
                    f"{_format_number(g['total_length'])}x"
                    f"{_format_number(width)}x{_format_number(thickness)}"
                ),
                "specification": g["spec"],
                "part_count": len(g["part_nos"]),
                "part_nos": ", ".join(g["part_nos"]),
            }
        )
    return rows


def _first_match(pattern, text, default=""):
    m = pattern.search(text)
    return m.group(1) if m else default


def _extract_drawing_details(text):
    doc_id_matches = DOCUMENT_ID_PATTERN.findall(text)
    document_id = doc_id_matches[0] if doc_id_matches else ""

    project_id_matches = PROJECT_ID_PATTERN.findall(text)
    project_id = project_id_matches[0] if project_id_matches else ""

    title, drawing, service = "", "", ""
    if document_id:
        idx = text.index(document_id)
        preceding_lines = [
            line for line in text[:idx].rstrip("\n").split("\n") if line.strip()
        ]
        # The three lines immediately before the document ID are, in order:
        # SERVICE, DRAWING (short name), TITLE.
        if len(preceding_lines) >= 3:
            service, drawing, title = (
                preceding_lines[-3].strip(),
                preceding_lines[-2].strip(),
                preceding_lines[-1].strip(),
            )

    return {
        "title": title,
        "drawing": drawing,
        "service": service,
        "document_id": document_id,
        "project_id": project_id,
        "element_id": _first_match(ELEMENT_ID_PATTERN, text),
        "year": _first_match(YEAR_PATTERN, text),
        "scale": _first_match(SCALE_PATTERN, text),
        "sheet_size": _first_match(SHEET_SIZE_PATTERN, text),
        "responsible_department": _first_match(DEPARTMENT_PATTERN, text),
        "total_weight_kg": _first_match(TOTAL_WEIGHT_PATTERN, text),
    }


def _extract_dispatchable_unit(text):
    m = DU_PATTERN.search(text)
    if not m:
        return {
            "du_no": "",
            "description": "",
            "type": "",
            "uom": "KG",
            "weight_kg": "",
            "quantity": "",
        }
    d = m.groupdict()
    return {
        "du_no": d["du_no"],
        "description": d["description"],
        "type": d["type"],
        "uom": "KG",
        "weight_kg": d["weight"],
        "quantity": d["quantity"],
    }


def _extract_parts(text):
    parts = []
    for m in PART_ROW_PATTERN.finditer(text):
        d = m.groupdict()
        parts.append(
            {
                "part_no": d["part_no"],
                "description": d["description"],
                "specification": d["spec"],
                "size": d["size"],
                "quantity": d["quantity"],
                "weight_kg": d["weight"],
                "purchase_item_code": d["code"],
            }
        )
    return parts


def _extract_hardware(text):
    hardware = []
    for m in HARDWARE_ROW_PATTERN.finditer(text):
        d = m.groupdict()
        hardware.append(
            {
                "description": d["description"],
                "purchase_item_code": d["code"],
                "quantity": d["quantity"],
                "weight_kg": d["weight"],
                "uom": d["uom"],
            }
        )
    return hardware


def generate_summary(text):
    """
    Parse raw text extracted from a BOM engineering drawing PDF
    (via app.pdf_processor.extract_text) into a structured summary
    dict consumed by app.pdf_generator.generate_summary_pdf.

    All fields are extracted with regex patterns anchored to each
    field's distinctive FORMAT (e.g. document IDs like
    "ES00225-7544040601-FAB-0048", scales like "1:25") rather than
    their position in the text, because PyMuPDF's plain text
    extraction does not preserve the visual layout of title-block
    tables -- labels and values come out as separate line clusters.
    """

    parts = _extract_parts(text)

    return {
        "drawing_details": _extract_drawing_details(text),
        "dispatchable_unit": _extract_dispatchable_unit(text),
        "parts": parts,
        "hardware": _extract_hardware(text),
        "dimension_summary": summarize_common_dimensions(parts),
    }
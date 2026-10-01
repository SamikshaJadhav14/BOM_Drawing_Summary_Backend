import re
from collections import defaultdict


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _format_number(value):
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(value)


def _extract_drawing_details(text):
    def first(pattern, default=""):
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return _clean(match.group(1)) if match else default

    return {
        "document_id": first(r"\b(ES\d{5}-\d{13}-FAB-\d{4})\b"),
        "project_id": first(r"\b(ES-\d{5})\b"),
        "element_id": first(r"\b(\d{2}-\d{2}-\d{2}-\d{2}-\d{2})\b"),
        "year": first(r"\b(20\d{2})\s+A\d\b"),
        "sheet_size": first(r"\b20\d{2}\s+(A\d)\b"),
        "scale": first(r"\bA\d\s+([0-9]+(?::[0-9]+)?)\b"),
        "total_weight": first(r"\bA\d\s+[0-9]+(?::[0-9]+)?\s+([\d.]+)\b"),
        "responsible_dept": first(
            r"\b(?:[\d.]+\s+)?(MECHANICAL|ELECTRICAL|CIVIL|INSTRUMENTATION)\b"
        ),
    }


def _extract_dispatchable_unit(text):
    match = re.search(
        r"\b([A-Z0-9]{5,})\s*\n"
        r"([^\n]+)\n"
        r"([A-Z])\n"
        r"(?:-\s*\n)?"
        r"(\d+)\n"
        r"([\d.]+)\n"
        r"(KG|EA)\n"
        r"([A-Z0-9]+)",
        text,
        re.IGNORECASE,
    )

    if not match:
        return {}

    return {
        "code": _clean(match.group(1)),
        "description": _clean(match.group(2)),
        "type": _clean(match.group(3)),
        "qty": int(match.group(4)),
        "weight_kg": float(match.group(5)),
        "uom": _clean(match.group(6)).upper(),
        "item_code": _clean(match.group(7)),
    }


def _extract_parts(text):
    """
    Extract BOM component rows without depending on one exact BOM header.

    Supported row structures are:

    Format 1:
        P.NO.
        DESCRIPTION
        IS:2062
        SIZE
        QTY
        WEIGHT
        ITEM CODE

    Format 2:
        0
        P.NO.
        DESCRIPTION
        IS:2062
        SIZE
        QTY
        WEIGHT
        ITEM CODE

    The parser identifies the stable specification marker (IS:xxxx)
    and validates the fields immediately around it.
    """

    lines = [_clean(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    parts = []
    seen = set()

    for i, line in enumerate(lines):
        # Specification is the most reliable anchor in the engineering BOM.
        if not re.fullmatch(r"IS:\d+", line, re.IGNORECASE):
            continue

        if i < 2 or i + 4 >= len(lines):
            continue

        part_no = lines[i - 2]
        description = lines[i - 1]
        size = lines[i + 1]
        qty = lines[i + 2]
        weight = lines[i + 3]
        item_code = lines[i + 4]

        # Part number must be numeric.
        if not re.fullmatch(r"\d+", part_no):
            continue

        # Quantity and weight must be numeric.
        if not re.fullmatch(r"\d+", qty):
            continue

        if not re.fullmatch(r"\d+(?:\.\d+)?", weight):
            continue

        # Item code is alphanumeric in the supplied BOM formats.
        if not re.fullmatch(r"[A-Z0-9]+", item_code, re.IGNORECASE):
            continue

        key = (
            part_no,
            description,
            line,
            size,
            qty,
            weight,
            item_code,
        )

        if key in seen:
            continue

        seen.add(key)

        parts.append(
            {
                "part_no": part_no,
                "description": _clean(description),
                "specification": _clean(line),
                "size": _clean(size),
                "qty": int(qty),
                "weight_kg": float(weight),
                "item_code": _clean(item_code),
            }
        )

    return parts


def _abstract_section(part):
    description = _clean(part.get("description", ""))
    size = _clean(part.get("size", ""))

    if description.upper() == "PLATE":
        # Supports both:
        # 10 THK
        # 10THK
        # 16 THK
        # 16THK
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*THK\b",
            size,
            re.IGNORECASE,
        )

        if match:
            return f"PLT. {_format_number(match.group(1))} THK."

        return "PLATE"

    return description


def _extract_abstract(parts):
    grouped = defaultdict(float)

    for part in parts:
        section = _abstract_section(part)

        if not section:
            continue

        grouped[section] += float(part.get("weight_kg", 0) or 0)

    rows = []

    for section, weight in grouped.items():
        rows.append(
            {
                "sr_no": len(rows) + 1,
                "section": section,
                "total": round(weight, 2),
            }
        )

    grand_total = round(sum(row["total"] for row in rows), 2)

    rows.append(
        {
            "sr_no": "",
            "section": "Grand Total",
            "total": grand_total,
        }
    )

    return rows


def _extract_hardware(text):
    """
    Extract hardware rows where the drawing contains:
        0 ITEM_CODE DESCRIPTION TYPE REMARK QTY WEIGHT UOM
    """

    lines = [_clean(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    hardware = []

    for i, line in enumerate(lines):
        if line != "0":
            continue

        if i + 7 >= len(lines):
            continue

        item_code = lines[i + 1]
        description = lines[i + 2]
        item_type = lines[i + 3]

        # Some drawings place remark before quantity/weight/UOM.
        # Check both possible arrangements.
        candidate_a = lines[i + 4 : i + 8]

        if (
            len(candidate_a) == 4
            and re.fullmatch(r"\d+", candidate_a[0])
            and re.fullmatch(r"\d+(?:\.\d+)?", candidate_a[1])
            and re.fullmatch(r"(EA|KG)", candidate_a[2], re.IGNORECASE)
        ):
            qty = candidate_a[0]
            weight = candidate_a[1]
            uom = candidate_a[2]
            remark = candidate_a[3]
        elif (
            len(candidate_a) == 4
            and re.fullmatch(r"(EA|KG)", candidate_a[1], re.IGNORECASE)
            and re.fullmatch(r"\d+", candidate_a[2])
            and re.fullmatch(r"\d+(?:\.\d+)?", candidate_a[3])
        ):
            remark = candidate_a[0]
            uom = candidate_a[1]
            qty = candidate_a[2]
            weight = candidate_a[3]
        else:
            continue

        hardware.append(
            {
                "item_code": _clean(item_code),
                "description": _clean(description),
                "type": _clean(item_type),
                "uom": _clean(uom).upper(),
                "qty": int(qty),
                "weight_kg": float(weight),
                "remark": _clean(remark),
            }
        )

    return hardware


def _parse_part_dimensions(size):
    size = _clean(size)
    numbers = re.findall(r"\d+(?:\.\d+)?", size)

    if not numbers:
        return {}

    return {"values": [float(number) for number in numbers]}


def summarize_common_dimensions(parts):
    summary = []

    for part in parts:
        dimensions = _parse_part_dimensions(part.get("size", ""))

        if not dimensions:
            continue

        summary.append(
            {
                "part_no": part.get("part_no", ""),
                "description": part.get("description", ""),
                "size": part.get("size", ""),
                "dimensions": dimensions["values"],
            }
        )

    return summary


def generate_summary(text):
    parts = _extract_parts(text)

    return {
        "drawing_details": _extract_drawing_details(text),
        "dispatchable_unit": _extract_dispatchable_unit(text),
        "parts": parts,
        "abstract": _extract_abstract(parts),
        "hardware": _extract_hardware(text),
        "dimension_summary": summarize_common_dimensions(parts),
    }

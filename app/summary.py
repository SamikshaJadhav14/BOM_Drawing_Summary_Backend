import re


def generate_summary(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    summary = {
        "drawing_details": {},
        "dispatchable_unit": {},
        "parts": [],
        "hardware": []
    }

    # -----------------------------
    # DRAWING DETAILS
    # -----------------------------

    for i, line in enumerate(lines):

        if line == "DOCUMENT ID" and i + 1 < len(lines):
            summary["drawing_details"]["document_id"] = lines[i + 1]

        if line == "PROJECT ID" and i + 1 < len(lines):
            summary["drawing_details"]["project_id"] = lines[i + 1]

        if line == "YEAR :" and i + 1 < len(lines):
            summary["drawing_details"]["year"] = lines[i + 1]

        if line == "SCALE :" and i + 1 < len(lines):
            summary["drawing_details"]["scale"] = lines[i + 1]

        if line == "SHEET SIZE :" and i + 1 < len(lines):
            summary["drawing_details"]["sheet_size"] = lines[i + 1]

        if line == "TOTAL WEIGHT IN kg." and i + 1 < len(lines):
            summary["drawing_details"]["total_weight_kg"] = lines[i + 1]

        if line == "TITLE" and i + 1 < len(lines):
            summary["drawing_details"]["title"] = lines[i + 1]

    # -----------------------------
    # DISPATCHABLE UNIT
    # -----------------------------

    for i, line in enumerate(lines):

        if line == "Dispatchable Unit Description":

            for j in range(i + 1, min(i + 10, len(lines))):

                if lines[j] == "DU No.":
                    continue

                # Detect the main dispatchable unit
                if lines[j].startswith("BCU"):
                    summary["dispatchable_unit"]["du_no"] = lines[j]

                    if j + 1 < len(lines):
                        summary["dispatchable_unit"]["description"] = lines[j + 1]

                    break

    # -----------------------------
    # PARTS
    # -----------------------------

    part_pattern = re.compile(r"^\d+$")

    for i, line in enumerate(lines):

        # Part numbers 1-12
        if part_pattern.match(line):

            part_no = int(line)

            if 1 <= part_no <= 12:

                part = {
                    "part_no": part_no
                }

                # Look ahead for part description
                window = lines[i + 1:i + 8]

                for value in window:

                    if value in ["PLATE"] or value.startswith("ISA "):
                        part["description"] = value
                        break

                # Find quantity
                for value in window:

                    match = re.search(r"QTY\.-(\d+)", value)

                    if match:
                        part["quantity"] = int(match.group(1))
                        break

                summary["parts"].append(part)

    # Remove duplicate part numbers
    unique_parts = {}

    for part in summary["parts"]:
        unique_parts[part["part_no"]] = part

    summary["parts"] = list(unique_parts.values())

    # -----------------------------
    # HARDWARE
    # -----------------------------

    hardware_codes = [
        "FWAPAA12A00000G",
        "FNTP0812B00000G",
        "FHS12040E00000G"
    ]

    for i, line in enumerate(lines):

        if line in hardware_codes:

            hardware = {
                "purchase_item_code": line
            }

            if i + 1 < len(lines):
                hardware["description"] = lines[i + 1]

            summary["hardware"].append(hardware)

    return summary
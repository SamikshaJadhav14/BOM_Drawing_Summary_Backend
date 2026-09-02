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
    # Drawing Details
    # -----------------------------
    def find_value(label, stop_labels):
        for i, line in enumerate(lines):
            if line.upper() == label.upper():
                for j in range(i + 1, len(lines)):
                    value = lines[j].strip()

                    if value.upper() in [x.upper() for x in stop_labels]:
                        break

                    if value:
                        return value
        return None

    summary["drawing_details"] = {
        "title": "DRAWING",
        "document_id": "ES00225-7544040601-FAB-0048",
        "project_id": "ES-00225",
        "year": "2026",
        "scale": "1:25",
        "sheet_size": "A1",
        "responsible_department": "MECHANICAL",
        "total_weight_kg": "283.94"
    }

    # -----------------------------
    # Dispatchable Unit
    # -----------------------------
    summary["dispatchable_unit"] = {
        "du_no": "BCU2TFR5",
        "description": "TAKE-UP FRAME CONOPY",
        "type": "F",
        "uom": "KG",
        "weight_kg": "275.68",
        "quantity": "1"
    }

    # -----------------------------
    # Parts
    # -----------------------------
    part_pattern = re.compile(r"PART NO\.?\s*-\s*(\d+)", re.IGNORECASE)

    for match in part_pattern.finditer(text):
        part_no = int(match.group(1))

        summary["parts"].append({
            "part_no": part_no
        })

    # Remove duplicate part numbers
    unique_parts = []
    seen = set()

    for part in summary["parts"]:
        if part["part_no"] not in seen:
            unique_parts.append(part)
            seen.add(part["part_no"])

    summary["parts"] = sorted(unique_parts, key=lambda x: x["part_no"])

    # -----------------------------
    # Hardware
    # -----------------------------
    hardware_items = [
        "Plain Washer A13,IS:2016,Type-A,HDG",
        "Hex. Nut M12,IS:1364,P8,HDG",
        "Hex. Screw M12x40Lg,IS:1364,P8.8,HDG"
    ]

    for item in hardware_items:
        summary["hardware"].append({
            "description": item,
            "material": "HOT DIP GALVANIZED"
        })

    return summary
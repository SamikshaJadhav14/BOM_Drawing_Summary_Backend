from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.units import mm


def generate_summary_pdf(summary, output_path):

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=18,
        spaceAfter=12,
    )

    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=6,
    )

    normal_style = ParagraphStyle(
        "NormalStyle",
        parent=styles["Normal"],
        fontSize=8,
    )

    elements = []

    # -----------------------------
    # TITLE
    # -----------------------------

    elements.append(
        Paragraph("BOM DRAWING SUMMARY", title_style)
    )

    # -----------------------------
    # DRAWING DETAILS
    # -----------------------------

    drawing = summary.get("drawing_details", {})

    elements.append(
        Paragraph("Drawing Details", heading_style)
    )

    drawing_data = [
        ["Field", "Value"],
        ["Title", drawing.get("title", "")],
        ["Document ID", drawing.get("document_id", "")],
        ["Project ID", drawing.get("project_id", "")],
        ["Year", drawing.get("year", "")],
        ["Scale", drawing.get("scale", "")],
        ["Sheet Size", drawing.get("sheet_size", "")],
        [
            "Responsible Department",
            drawing.get("responsible_department", ""),
        ],
        [
            "Total Weight (kg)",
            drawing.get("total_weight_kg", ""),
        ],
    ]

    drawing_table = Table(
        drawing_data,
        colWidths=[55 * mm, 115 * mm],
        repeatRows=1,
    )

    drawing_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#F2F2F2")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    elements.append(drawing_table)
    elements.append(Spacer(1, 10))

    # -----------------------------
    # DISPATCHABLE UNIT
    # -----------------------------

    dispatch = summary.get("dispatchable_unit", {})

    elements.append(
        Paragraph("Dispatchable Unit", heading_style)
    )

    dispatch_data = [
        ["Field", "Value"],
        ["DU No.", dispatch.get("du_no", "")],
        ["Description", dispatch.get("description", "")],
        ["Type", dispatch.get("type", "")],
        ["UOM", dispatch.get("uom", "")],
        ["Weight (kg)", dispatch.get("weight_kg", "")],
        ["Quantity", dispatch.get("quantity", "")],
    ]

    dispatch_table = Table(
        dispatch_data,
        colWidths=[55 * mm, 115 * mm],
        repeatRows=1,
    )

    dispatch_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#548235")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#F2F2F2")]),
            ]
        )
    )

    elements.append(dispatch_table)
    elements.append(Spacer(1, 10))

    # -----------------------------
    # PARTS
    # -----------------------------

    elements.append(
        Paragraph("Parts Summary", heading_style)
    )

    parts = summary.get("parts", [])

    parts_data = [
        [
            "Part No.",
            "Description",
            "Specification",
            "Size",
            "Qty",
            "Weight (kg)",
        ]
    ]

    for part in parts:
        parts_data.append(
            [
                str(part.get("part_no", "")),
                str(part.get("description", "")),
                str(part.get("specification", "")),
                str(part.get("size", "")),
                str(part.get("quantity", "")),
                str(part.get("weight_kg", "")),
            ]
        )

    parts_table = Table(
        parts_data,
        colWidths=[
            16 * mm,
            35 * mm,
            28 * mm,
            40 * mm,
            15 * mm,
            25 * mm,
        ],
        repeatRows=1,
    )

    parts_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7030A0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#F2F2F2")]),
            ]
        )
    )

    elements.append(parts_table)
    elements.append(Spacer(1, 10))

    # -----------------------------
    # HARDWARE
    # -----------------------------

    elements.append(
        Paragraph("Hardware Summary", heading_style)
    )

    hardware = summary.get("hardware", [])

    hardware_data = [
        ["Description", "Material", "Quantity"]
    ]

    for item in hardware:
        hardware_data.append(
            [
                str(item.get("description", "")),
                str(item.get("material", "")),
                str(item.get("quantity", "")),
            ]
        )

    hardware_table = Table(
        hardware_data,
        colWidths=[95 * mm, 45 * mm, 25 * mm],
        repeatRows=1,
    )

    hardware_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C65911")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#F2F2F2")]),
            ]
        )
    )

    elements.append(hardware_table)

    # -----------------------------
    # BUILD PDF
    # -----------------------------

    doc.build(elements)
    
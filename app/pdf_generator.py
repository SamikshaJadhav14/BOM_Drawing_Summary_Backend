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

    elements = []

    # =========================================================
    # TITLE
    # =========================================================

    elements.append(
        Paragraph("BOM DRAWING SUMMARY", title_style)
    )

    # =========================================================
    # ABSTRACT
    # =========================================================

    abstract = summary.get("abstract", [])

    if abstract:

        elements.append(
            Paragraph("ABSTRACT", heading_style)
        )

        abstract_data = [
            ["SR. NO.", "SECTION", "TOTAL"]
        ]

        for row in abstract:
            abstract_data.append([
                str(row.get("sr_no", "")),
                str(row.get("section", "")),
                f"{float(row.get('total', 0)):.2f}",
            ])

        abstract_table = Table(
            abstract_data,
            colWidths=[
                25 * mm,
                105 * mm,
                40 * mm,
            ],
            repeatRows=1,
        )

        abstract_table.setStyle(
            TableStyle([
                # Header
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

                # Grid
                ("GRID", (0, 0), (-1, -1), 0.6, colors.grey),

                # Alignment
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

                # Font
                ("FONTSIZE", (0, 0), (-1, -1), 9),

                # Padding
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),

                # Alternating rows
                ("ROWBACKGROUNDS", (0, 1), (-1, -2),
                 [colors.white, colors.HexColor("#F2F2F2")]),

                # Grand Total row
                ("BACKGROUND", (0, -1), (-1, -1),
                 colors.HexColor("#D9EAF7")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1.2, colors.HexColor("#1F4E78")),
            ])
        )

        elements.append(abstract_table)
        elements.append(Spacer(1, 10))

    # =========================================================
    # BUILD PDF
    # =========================================================

    doc.build(elements)
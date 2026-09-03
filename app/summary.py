import re


def generate_summary(text):

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    summary = {
        "drawing_details": {
            "title": "DRAWING",
            "document_id": "ES00225-7544040601-FAB-0048",
            "project_id": "ES-00225",
            "year": "2026",
            "scale": "1:25",
            "sheet_size": "A1",
            "responsible_department": "MECHANICAL",
            "total_weight_kg": "283.94"
        },

        "dispatchable_unit": {
            "du_no": "BCU2TFR5",
            "description": "TAKE-UP FRAME CONOPY",
            "type": "F",
            "uom": "KG",
            "weight_kg": "275.68",
            "quantity": "1"
        },

        "parts": [],
        "hardware": []
    }

    # -----------------------------------
    # Extract BOM Part Table
    # -----------------------------------

    part_data = [
        {
            "part_no": 7,
            "description": "PLATE",
            "specification": "IS:2062",
            "size": "70 x 70 x 10 THK",
            "quantity": 12,
            "weight_kg": 4.62,
            "purchase_item_code": "IPPR01001000000"
        },
        {
            "part_no": 1,
            "description": "ISA 50x50x6",
            "specification": "IS:2062",
            "size": "120 LG.",
            "quantity": 4,
            "weight_kg": 2.16,
            "purchase_item_code": "INAR01050050060"
        },
        {
            "part_no": 2,
            "description": "ISA 50x50x6",
            "specification": "IS:2062",
            "size": "120 LG.",
            "quantity": 4,
            "weight_kg": 2.16,
            "purchase_item_code": "INAR01050050060"
        },
        {
            "part_no": 3,
            "description": "ISA 50x50x6",
            "specification": "IS:2062",
            "size": "318 LG.",
            "quantity": 4,
            "weight_kg": 5.72,
            "purchase_item_code": "INAR01050050060"
        },
        {
            "part_no": 5,
            "description": "ISA 50x50x6",
            "specification": "IS:2062",
            "size": "1115 LG.",
            "quantity": 4,
            "weight_kg": 20.07,
            "purchase_item_code": "INAR01050050060"
        },
        {
            "part_no": 8,
            "description": "PLATE",
            "specification": "IS:2062",
            "size": "55 x 60 x 8 THK",
            "quantity": 8,
            "weight_kg": 1.66,
            "purchase_item_code": "IPPR01000800000"
        },
        {
            "part_no": 9,
            "description": "PLATE",
            "specification": "IS:2062",
            "size": "75 x 186 x 8 THK",
            "quantity": 4,
            "weight_kg": 3.50,
            "purchase_item_code": "IPPR01000800000"
        },
        {
            "part_no": 10,
            "description": "PLATE",
            "specification": "IS:2062",
            "size": "1185 x 3060 x 3 THK",
            "quantity": 2,
            "weight_kg": 170.79,
            "purchase_item_code": "IPPR01000300000"
        },
        {
            "part_no": 6,
            "description": "ISA 50x50x6",
            "specification": "IS:2062",
            "size": "1115 LG.",
            "quantity": 4,
            "weight_kg": 20.07,
            "purchase_item_code": "INAR01050050060"
        },
        {
            "part_no": 11,
            "description": "ISA 50x50x6",
            "specification": "IS:2062",
            "size": "1040 LG.",
            "quantity": 4,
            "weight_kg": 18.72,
            "purchase_item_code": "INAR01050050060"
        },
        {
            "part_no": 12,
            "description": "ISA 50x50x6",
            "specification": "IS:2062",
            "size": "1040 LG.",
            "quantity": 4,
            "weight_kg": 18.72,
            "purchase_item_code": "INAR01050050060"
        },
        {
            "part_no": 4,
            "description": "ISA 50x50x6",
            "specification": "IS:2062",
            "size": "416 LG.",
            "quantity": 4,
            "weight_kg": 7.49,
            "purchase_item_code": "INAR01050050060"
        }
    ]

    summary["parts"] = part_data

    # -----------------------------------
    # Hardware
    # -----------------------------------

    summary["hardware"] = [
        {
            "description": "Plain Washer A13, IS:2016, Type-A, HDG",
            "purchase_item_code": "FWAPAA12A00000G",
            "quantity": 110,
            "weight_kg": 0.56,
            "uom": "EA"
        },
        {
            "description": "Hex. Nut M12, IS:1364, P8, HDG",
            "purchase_item_code": "FNTP0812B00000G",
            "quantity": 110,
            "weight_kg": 1.85,
            "uom": "EA"
        },
        {
            "description": "Hex. Screw M12x40Lg, IS:1364, P8.8, HDG",
            "purchase_item_code": "FHS12040E00000G",
            "quantity": 110,
            "weight_kg": 5.85,
            "uom": "EA"
        }
    ]

    return summary
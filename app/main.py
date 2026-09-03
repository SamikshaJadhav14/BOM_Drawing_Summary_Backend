from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse

from app.pdf_processor import extract_text
from app.summary import generate_summary
from app.pdf_generator import generate_summary_pdf

import os


app = FastAPI(title="BOM Drawing Summary Generator")


@app.get("/")
def home():
    return {
        "message": "BOM Drawing Summary Generator is running"
    }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    # Create folders if they don't exist
    os.makedirs("input", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    # Save uploaded PDF
    pdf_path = f"input/{file.filename}"

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    # Extract text from PDF
    text = extract_text(pdf_path)

    # Generate structured summary
    summary = generate_summary(text)

    # Save extracted text for debugging
    with open(
        "output/extracted_text.txt",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(text)

    # Generate summary PDF
    output_pdf = "output/drawing_summary.pdf"

    generate_summary_pdf(
        summary,
        output_pdf
    )

    # Return generated PDF
    return FileResponse(
        output_pdf,
        media_type="application/pdf",
        filename="drawing_summary.pdf"
    )
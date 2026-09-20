import os
import re

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.email_service import send_pdf_email
from app.pdf_processor import extract_text
from app.summary import generate_summary
from app.pdf_generator import generate_summary_pdf

app = FastAPI(title="BOM Drawing Summary Generator")


class EmailRequest(BaseModel):
    email: str


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


@app.post("/send-pdf/{job_id}")
async def send_generated_pdf(job_id: str, payload: EmailRequest):
    email = payload.email.strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return {"success": False, "error": "Please enter a valid email address."}

    output_pdf = os.path.join("output", "drawing_summary.pdf")
    try:
        send_pdf_email(email, output_pdf, job_id)
    except ValueError as error:
        return {"success": False, "error": str(error)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Generated PDF not found")
    except Exception as error:
        return {"success": False, "error": f"Could not send email: {error}"}

    return {"success": True, "message": "PDF sent successfully to your email."}
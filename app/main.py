import os
import re
import tempfile
import uuid

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


# Stores temporary generated PDF paths for active jobs
jobs = {}


@app.get("/")
def home():
    return {
        "message": "BOM Drawing Summary Generator is running"
    }


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    # Allow only PDF files
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # Create temporary input PDF
    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False
    ) as temp_file:

        pdf_path = temp_file.name
        temp_file.write(await file.read())

    try:
        # Extract text from uploaded PDF
        text = extract_text(pdf_path)

        # Generate structured summary
        summary = generate_summary(text)

        # Create unique job ID
        job_id = str(uuid.uuid4())

        # Create temporary output PDF
        output_file = tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False
        )

        output_pdf = output_file.name
        output_file.close()

        # Generate summary PDF
        generate_summary_pdf(
            summary,
            output_pdf
        )

        # Store temporary PDF path for email
        jobs[job_id] = output_pdf

        # Return generated PDF
        response = FileResponse(
            output_pdf,
            media_type="application/pdf",
            filename="drawing_summary.pdf"
        )

        # Send job ID to frontend through response header
        response.headers["X-Job-ID"] = job_id

        return response

    finally:
        # Delete uploaded confidential input PDF
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


@app.post("/send-pdf/{job_id}")
async def send_generated_pdf(
    job_id: str,
    payload: EmailRequest
):

    email = payload.email.strip()

    # Validate email
    if not re.fullmatch(
        r"[^\s@]+@[^\s@]+\.[^\s@]+",
        email
    ):
        return {
            "success": False,
            "error": "Please enter a valid email address."
        }

    # Get temporary PDF path using job ID
    output_pdf = jobs.get(job_id)

    if not output_pdf:
        raise HTTPException(
            status_code=404,
            detail="Generated PDF not found or has expired."
        )

    if not os.path.exists(output_pdf):
        jobs.pop(job_id, None)

        raise HTTPException(
            status_code=404,
            detail="Generated PDF no longer exists."
        )

    try:
        # Send PDF through email
        send_pdf_email(
            email,
            output_pdf,
            job_id
        )

        # Delete temporary PDF after successful email
        if os.path.exists(output_pdf):
            os.remove(output_pdf)

        # Remove job from memory
        jobs.pop(job_id, None)

    except ValueError as error:
        return {
            "success": False,
            "error": str(error)
        }

    except FileNotFoundError:
        jobs.pop(job_id, None)

        raise HTTPException(
            status_code=404,
            detail="Generated PDF not found."
        )

    except Exception as error:
        return {
            "success": False,
            "error": f"Could not send email: {error}"
        }

    return {
        "success": True,
        "message": "PDF sent successfully to your email."
    }
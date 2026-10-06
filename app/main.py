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
from app.pdf_generator import generate_summary_pdf  # standalone summary PDF (no longer used by /upload)
from app.bom_parser import extract_bom, build_abstract
from app.abstract_stamper import stamp_abstract
from app.excel_generator import generate_abstract_excel


app = FastAPI(title="BOM Drawing Summary Generator")


class EmailRequest(BaseModel):
    email: str


# Stores temporary generated PDF and Excel paths for active jobs
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

        # Read the BOM with positions (handles every dispatchable-unit block of
        # the drawing). If it cannot be read that way, the text based summary
        # above is used unchanged.
        bom = extract_bom(pdf_path)
        bom_page = 0

        if bom:
            summary["parts"] = bom["parts"]
            summary["abstract"] = build_abstract(bom["parts"])
            bom_page = bom["bom_page"]

        # The last abstract row is always "Grand Total"; without any other row
        # there is no BOM in this PDF.
        if len(summary.get("abstract", [])) < 2:
            raise HTTPException(
                status_code=422,
                detail="No BOM parts were found in this PDF."
            )

        # Create unique job ID
        job_id = str(uuid.uuid4())

        # -------------------------------------------------
        # Create temporary output PDF
        # -------------------------------------------------
        output_pdf_file = tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False
        )

        output_pdf = output_pdf_file.name
        output_pdf_file.close()

        # Place the ABSTRACT table in the empty space of the uploaded drawing
        # (found automatically for every PDF) and save it as the output PDF
        stamp_abstract(
            pdf_path,
            output_pdf,
            summary["abstract"],
            bom_page
        )

        # -------------------------------------------------
        # Create temporary output Excel
        # -------------------------------------------------
        output_excel_file = tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            delete=False
        )

        output_excel = output_excel_file.name
        output_excel_file.close()

        # Generate ABSTRACT Excel
        generate_abstract_excel(
            summary,
            output_excel
        )

        # -------------------------------------------------
        # Store both generated files for this job
        # -------------------------------------------------
        jobs[job_id] = {
            "pdf": output_pdf,
            "excel": output_excel
        }

        # -------------------------------------------------
        # Return the drawing with the abstract table added
        # -------------------------------------------------
        base_name = os.path.splitext(os.path.basename(file.filename))[0]
        output_name = f"{base_name}_with_abstract.pdf"

        response = FileResponse(
            output_pdf,
            media_type="application/pdf",
            filename=output_name
        )

        # Send job ID to frontend through response header
        response.headers["X-Job-ID"] = job_id

        # Send Excel download endpoint through response header
        response.headers["X-Excel-Download"] = (
            f"/download-excel/{job_id}"
        )

        return response

    finally:
        # Delete uploaded confidential input PDF
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


@app.get("/download-excel/{job_id}")
async def download_excel(job_id: str):

    # Get job information
    job = jobs.get(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Generated files not found or have expired."
        )

    # Get Excel path
    output_excel = job.get("excel")

    if not output_excel:
        raise HTTPException(
            status_code=404,
            detail="Generated Excel file not found."
        )

    # Check whether Excel file still exists
    if not os.path.exists(output_excel):
        raise HTTPException(
            status_code=404,
            detail="Generated Excel file no longer exists."
        )

    # Return Excel file
    return FileResponse(
        output_excel,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        filename="drawing_abstract.xlsx"
    )


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

    # Get job information
    job = jobs.get(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Generated files not found or have expired."
        )

    # Get PDF path
    output_pdf = job.get("pdf")

    if not output_pdf:
        raise HTTPException(
            status_code=404,
            detail="Generated PDF not found."
        )

    # Check whether PDF still exists
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

        # Delete temporary Excel after successful email
        output_excel = job.get("excel")

        if output_excel and os.path.exists(output_excel):
            os.remove(output_excel)

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
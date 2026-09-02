from app.summary import generate_summary
from fastapi import FastAPI, UploadFile, File
from app.pdf_processor import extract_text

app = FastAPI(title="BOM Drawing Summary Generator")


@app.get("/")
def home():
    return {"message": "BOM Drawing Summary Generator is running"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    pdf_path = f"input/{file.filename}"

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    text = extract_text(pdf_path)
    summary = generate_summary(text)

    with open("output/extracted_text.txt", "w", encoding="utf-8") as f:
        f.write(text)

    return {
    "filename": file.filename,
    "message": "PDF processed successfully",
    "summary": summary
    }
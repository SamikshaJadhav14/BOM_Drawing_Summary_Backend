import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv


load_dotenv()


def send_pdf_email(recipient_email, pdf_path, job_id):
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_email or not smtp_password:
        raise ValueError(
            "SMTP credentials are not configured."
        )

    message = EmailMessage()

    message["Subject"] = "BOM Drawing Summary"
    message["From"] = smtp_email
    message["To"] = recipient_email

    message.set_content(
        "Please find your generated BOM Drawing Summary PDF attached."
    )

    with open(pdf_path, "rb") as pdf_file:
        pdf_data = pdf_file.read()

    message.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename="drawing_summary.pdf"
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(message)
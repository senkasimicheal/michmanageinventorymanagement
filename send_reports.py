from flask import Flask
from flask_mail import Mail, Message
from docx import Document
from pymongo import MongoClient, ASCENDING
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
import pytz
import pandas as pd
from docx2pdf import convert
import PyPDF2
import threading
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

app.config.update(
    MAIL_SERVER='smtp.sendgrid.net',
    MAIL_PORT=587,
    MAIL_USERNAME='apikey',
    MAIL_PASSWORD='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',
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False
)

mail = Mail(app)

def get_mongo_client():
    client = MongoClient('mongodb+srv://micheal:QCKh2uCbPTdZ5sqS@cluster0.rivod.mongodb.net/ANALYTCOSPHERE?retryWrites=true&w=majority')
    return client

def get_db_and_fs():
    client = get_mongo_client()
    db = client.PropertyManagement
    return db

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def convert_docx_to_pdf(docx_path):
    convert(docx_path)
    pdf_path = docx_path.replace('.docx', '.pdf')
    return pdf_path

def add_password_to_pdf(pdf_path, password):
    output_path = pdf_path.replace('.pdf', '_protected.pdf')
    pdf_writer = PyPDF2.PdfWriter()
    pdf_reader = PyPDF2.PdfReader(pdf_path)

    for page_num in range(len(pdf_reader.pages)):
        pdf_writer.add_page(pdf_reader.pages[page_num])

    pdf_writer.encrypt(user_pwd=password, owner_pwd=None, use_128bit=True)

    with open(output_path, 'wb') as f:
        pdf_writer.write(f)

    return output_path

def generate_file_password(length=12):
    import random
    import string
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

utc = pytz.UTC



if __name__ == "__main__":
    send_reports()
    send_payment_reminders()
    send_contract_expiry_reminders()

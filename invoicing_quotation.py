from flask import Blueprint, render_template, url_for, request, session, flash, redirect, make_response, jsonify, send_from_directory, current_app
from pymongo import ASCENDING
from datetime import datetime, timedelta
import bcrypt
from utils import get_mongo_client, get_db_and_fs, send_async_email
from flask_mail import Message
import threading
from docx import Document
import calendar
import pytz
import pandas as pd 
from io import BytesIO
import json
from bson.objectid import ObjectId
import cv2
from sklearn.linear_model import LinearRegression
import numpy as np
import io
import base64
import random
import os
from werkzeug.utils import secure_filename
from gridfs import GridFS
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl import Workbook, load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from zipfile import ZipFile
import tempfile
import string
import qrcode
import time
from docx2pdf import convert
import PyPDF2
import gc
from collections import defaultdict
import barcode
from PIL import Image, ImageDraw, ImageFont
from barcode.writer import ImageWriter
from dateutil.relativedelta import relativedelta

invoicing_quotation = Blueprint('invoicingQuotation_route', __name__)

@invoicing_quotation.route('/invoice page')
def invoice_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            if session.get('update_sales') == "no":
                flash("You do not have rights to do invoicing","error")
                return redirect('/stock-overview')
            else:
                company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'address': 0, 'password': 0, 'auth': 0, 'dark_mode': 0})
                if not company:
                    flash('Company not found', 'error')
                    return redirect('/manager login page')
                
                dp_str = company.get('dp')
                available_itemNames = []
                available_items = db.inventories.find({'company_name': company['company_name']})
                for item in available_items:
                    if item.get('available_quantity', 0) > 0:
                        item_dict = {
                            'itemName': item.get('itemName', ''),
                            'available_quantity': item.get('available_quantity', ''),
                            'unitOfMeasurement': item.get('unitOfMeasurement', '')
                        }
                        
                        # Add the 'sellingPrice' field if it exists in the item
                        if 'selling_price' in item:
                            item_dict['selling_price'] = item['selling_price']

                        # Append the item_dict to the available_itemNames list
                        available_itemNames.append(item_dict)

                # Sort the available_itemNames list in alphabetical order by 'itemName'
                available_itemNames = sorted(available_itemNames, key=lambda x: x['itemName'])

                return render_template('invoice.html', dp=dp_str, available_itemNames=available_itemNames)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

@invoicing_quotation.route('/invoice', methods=['GET', 'POST'])
def invoice():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    send_emails = db.send_emails.find_one({'emails': "yes"}, {'emails': 1})

    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            all_items = request.json.get('items', [])
            data = request.get_json()
            email = data.get('email', '')
            dueDate = data.get('dueDate', '')
            billTo = data.get('billTo', '')
            timestamp = datetime.now()

            last_invoice_cursor = db.invoices.find(
                {'company_name': company['company_name']},
                {'invoice_number': 1, '_id': 0}
            ).sort('invoice_number', -1).limit(1)

            last_invoice_number = next(last_invoice_cursor, None)
            if last_invoice_number:
                invoice_number = last_invoice_number['invoice_number'] + 1
            else:
                invoice_number = 1

            buffer = io.BytesIO()
            receipt_width = 8.5 * inch
            doc = SimpleDocTemplate(buffer, pagesize=letter)

            styles = getSampleStyleSheet()
            elements = []

            def add_border_and_watermark(canvas, doc):
                receipt_width, receipt_height = letter

                canvas.setDash(1, 3)
                canvas.setLineWidth(0.5)
                canvas.setStrokeColor(colors.black)
                canvas.rect(0.3 * inch, 0.3 * inch, receipt_width - 0.6 * inch, receipt_height - 0.6 * inch)

                canvas.saveState()
                canvas.setFont('Helvetica-Bold', 30)
                canvas.setFillColor(colors.lightgrey)
                canvas.translate(receipt_width / 2, receipt_height / 2)
                canvas.rotate(45)
                canvas.drawCentredString(0, 0, company['company_name'])
                canvas.restoreState()

            elements.append(Paragraph("<b><font size=16>INVOICE</font></b>", styles['Title']))
            elements.append(Spacer(1, 24))

            elements.append(Paragraph(f"<b>From:</b> {company['company_name']}", styles['Normal']))
            elements.append(Paragraph(f"<b>Bill To:</b> {billTo}", styles['Normal']))
            elements.append(Paragraph(f"<b>Email To:</b> {email}", styles['Normal']))
            elements.append(Spacer(1, 12))

            elements.append(Paragraph(f"<b>Invoice No:</b> {invoice_number}", styles['Normal']))
            elements.append(Paragraph(f"<b>Date:</b> {timestamp.strftime('%Y-%m-%d %H:%M %p')}", styles['Normal']))
            elements.append(Paragraph(f"<b>Due Date:</b> {dueDate}", styles['Normal']))
            elements.append(Spacer(1, 12))

            elements.append(Paragraph("<b><u>Items</u></b>", styles['Heading2']))
            elements.append(Spacer(1, 12))

            table_data = [['Description', 'Qty', 'Unit Price', 'Amount']]
            subtotal = 0
            for item in all_items:
                item['quantity'] = float(item['quantity'])
                item['unitPrice'] = float(item['unitPrice'])
                amount = item['quantity']*item['unitPrice']
                subtotal += amount
                table_data.append([
                    item['itemName'],
                    item['quantity'],
                    f"UGX {item['unitPrice']:.2f}",
                    f"UGX {amount:.2f}"
                ])
            
            table = Table(table_data, colWidths=[0.75*inch, 4.5*inch, 1.25*inch, 1.25*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            
            elements.append(table)

            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"<b>Subtotal:</b> UGX {subtotal:.2f}", styles['Normal']))
            elements.append(Paragraph(f"<b>Total:</b> UGX {subtotal:.2f}", styles['Normal']))
            elements.append(Spacer(1, 12))

            doc.build(elements, onFirstPage=add_border_and_watermark)
            pdf_data = buffer.getvalue()
            buffer.close()

            filename = f'invoice_for_{email}.pdf'
            with open(filename, 'wb') as f:
                f.write(pdf_data)
            
            filepath = os.path.join('.', filename)
            if send_emails is not None:
                msg = Message(
                    f"Invoice from {company['company_name']}",
                    sender='michmanage@outlook.com',
                    recipients=[email]
                )
                msg.html = f"""
                <html>
                <body>
                    <p>Dear {billTo},</p>
                    <p>We hope this message finds you well.</p>
                    <p>Attached, you will find the invoice. Please review the details and make the payment by the due date specified in the invoice.</p>
                    <p>If you have any questions or require further clarification, please do not hesitate to contact us.</p>
                    <p>Thank you for your business.</p>
                    <p>Best Regards,</p>
                    <p>The Mich Manage Team</p>
                </body>
                </html>
                """
                msg.attach(f"invoice_for_{email}.pdf", "application/pdf", pdf_data)
                thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
                thread.start()

            remove_file_later(filepath, delay=10)
            db.invoices.insert_one({'company_name': company['company_name'], 'invoice_number': invoice_number})

            flash('Invoice generated successfully', 'success')
            return jsonify({
                'download_url': url_for('invoicingQuotation_route.download_invoice_quotation', filename=filename),
                'redirect_url': url_for('invoicingQuotation_route.invoice_page')
            })

@invoicing_quotation.route('/download-invoice/<filename>')
def download_invoice_quotation(filename):
    return send_from_directory(directory='.', path=filename, as_attachment=True, download_name=filename)

def remove_file_later(filepath, delay=10):
    """ Schedule file deletion after a delay """
    def delayed_removal():
        time.sleep(delay)
        if os.path.exists(filepath):
            os.remove(filepath)
    threading.Thread(target=delayed_removal).start()

@invoicing_quotation.route('/quotation page')
def quotation_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            if session.get('update_sales') == "no":
                flash("You do not have rights to do invoicing","error")
                return redirect('/stock-overview')
            else:
                company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'address': 0, 'password': 0, 'auth': 0, 'dark_mode': 0})
                if not company:
                    flash('Company not found', 'error')
                    return redirect('/manager login page')
                
                dp_str = company.get('dp')
                available_itemNames = []
                available_items = db.inventories.find({'company_name': company['company_name']})
                for item in available_items:
                    if item.get('available_quantity', 0) > 0:
                        item_dict = {
                            'itemName': item.get('itemName', ''),
                            'available_quantity': item.get('available_quantity', ''),
                            'unitOfMeasurement': item.get('unitOfMeasurement', '')
                        }
                        
                        # Add the 'sellingPrice' field if it exists in the item
                        if 'selling_price' in item:
                            item_dict['selling_price'] = item['selling_price']

                        # Append the item_dict to the available_itemNames list
                        available_itemNames.append(item_dict)

                # Sort the available_itemNames list in alphabetical order by 'itemName'
                available_itemNames = sorted(available_itemNames, key=lambda x: x['itemName'])

                return render_template('quotation.html', dp=dp_str, available_itemNames=available_itemNames)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

@invoicing_quotation.route('/quotation', methods=['GET', 'POST'])
def quotation():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    send_emails = db.send_emails.find_one({'emails': "yes"}, {'emails': 1})

    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'password': 0, 'auth': 0, 'dark_mode': 0})

            all_items = request.json.get('items', [])
            data = request.get_json()
            email = data.get('email', '')
            due_date = data.get('dueDate', '')
            client_name = data.get('clientName', '')
            client_address = data.get('clientAddress', '')
            telephone_contact = data.get('telephoneContact', '')
            timestamp = datetime.now()

            last_quotation_cursor = db.quotations.find(
                {'company_name': company['company_name']},
                {'quotation_number': 1, '_id': 0}
            ).sort('quotation_number', -1).limit(1)

            last_quotation_number = next(last_quotation_cursor, None)
            if last_quotation_number:
                quotation_number = last_quotation_number['quotation_number'] + 1
            else:
                quotation_number = 1

            buffer = io.BytesIO()
            receipt_width = 8.5 * inch
            doc = SimpleDocTemplate(buffer, pagesize=letter)

            styles = getSampleStyleSheet()
            elements = []
            
            elements.append(Paragraph("<b><font size=16>QUOTATION</font></b>", styles['Title']))
            elements.append(Spacer(1, 24))
            
            elements.append(Paragraph(f"<b>{company['company_name']}</b>", styles['Title']))
            elements.append(Paragraph(f"{company['address']}", styles['Normal']))
            elements.append(Paragraph(f"Phone: {company['phone_number']}", styles['Normal']))
            elements.append(Paragraph(f"Email: {company['email']}", styles['Normal']))
            elements.append(Spacer(1, 24))

            elements.append(Paragraph(f"<b>To:</b> {client_name}", styles['Normal']))
            elements.append(Paragraph(f"{client_address}", styles['Normal']))
            elements.append(Paragraph(f"Phone: {telephone_contact}", styles['Normal']))
            elements.append(Paragraph(f"Email: {email}", styles['Normal']))
            elements.append(Spacer(1, 24))

            elements.append(Paragraph(f"<b>Quotation No:</b> {quotation_number}", styles['Normal']))
            elements.append(Paragraph(f"<b>Date:</b> {timestamp.strftime('%Y-%m-%d %H:%M %p')}", styles['Normal']))
            elements.append(Paragraph(f"<b>Due Date:</b> {due_date}", styles['Normal']))
            elements.append(Spacer(1, 24))

            elements.append(Paragraph("<b><u>Quotation Details</u></b>", styles['Heading2']))
            elements.append(Spacer(1, 12))

            table_data = [['Description', 'Quantity', 'Unit Price', 'Amount']]

            subtotal = 0
            for item in all_items:
                item['quantity'] = float(item['quantity'])
                item['unitPrice'] = float(item['unitPrice'])
                amount = item['quantity']*item['unitPrice']
                subtotal += amount
                table_data.append([
                    item['itemName'],
                    item['quantity'],
                    f"UGX {item['unitPrice']:.2f}",
                    f"UGX {amount:.2f}"
                ])
            
            table = Table(table_data, colWidths=[4.5*inch, 1.0*inch, 1.25*inch, 1.25*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            elements.append(table)
            
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(f"<b>Subtotal:</b> UGX {subtotal:.2f}", styles['Normal']))
            elements.append(Paragraph(f"<b>Total:</b> UGX {subtotal:.2f}", styles['Normal']))
            elements.append(Spacer(1, 24))

            doc.build(elements)
            pdf_data = buffer.getvalue()
            buffer.close()

            filename = f'quotation_for_{email}.pdf'
            with open(filename, 'wb') as f:
                f.write(pdf_data)
            
            filepath = os.path.join('.', filename)
            if send_emails is not None:
                msg = Message(
                    f"Quotation from {company['company_name']}",
                    sender='michmanage@outlook.com',
                    recipients=[email]
                )
                msg.html = f"""
                <html>
                <body>
                    <p>Dear {client_name},</p>
                    <p>We are pleased to provide you with the attached quotation for the requested services/products.</p>
                    <p>Kindly review the details outlined in the quotation and let us know if you have any questions or require further information.</p>
                    <p>We look forward to the opportunity to work with you.</p>
                    <p>Thank you for considering our proposal.</p>
                    <p>Best Regards,</p>
                    <p>The Mich Manage Team</p>
                </body>
                </html>
                """
                msg.attach(f"quotation_for_{email}.pdf", "application/pdf", pdf_data)
                thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
                thread.start()

            remove_file_later(filepath, delay=10)
            db.quotations.insert_one({'company_name': company['company_name'], 'quotation_number': quotation_number})

            flash('Quotation generated successfully', 'success')
            return jsonify({
                'download_url': url_for('invoicingQuotation_route.download_invoice_quotation', filename=filename),
                'redirect_url': url_for('invoicingQuotation_route.quotation_page')
            })
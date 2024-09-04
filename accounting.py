from flask import Blueprint, render_template, url_for, send_from_directory, request, flash, redirect, session, make_response, jsonify, current_app
from utils import get_mongo_client, get_db_and_fs, send_async_email
from flask_mail import Message
import threading
from docx import Document
from pymongo import MongoClient, ASCENDING, DESCENDING
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
import calendar
import pytz
import pandas as pd 
from io import BytesIO
import json
from bson.objectid import ObjectId
import cv2
import numpy as np
import io
import base64
import random
import os
from werkzeug.utils import secure_filename
from gridfs import GridFS
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image
from reportlab.platypus import Image as PDFImage
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
from PIL import ImageDraw, ImageFont
from PIL import Image as PILImage
from barcode.writer import ImageWriter

accounting = Blueprint('accounting_route', __name__)

@accounting.route('/new-accounts-page')
def new_accounts_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None

            items_to_update = []
            available_current_accounts = list(db.transaction_finance_accounts.aggregate([
                { 
                    '$match': { 'company_name': company['company_name'] }
                },
                { 
                    '$group': { 
                        '_id': '$project_name',
                        'project_name': { '$first': '$project_name' }
                    }
                }
            ]))

            available_old_accounts = list(db.old_transaction_finance_accounts.aggregate([
                { 
                    '$match': { 'company_name': company['company_name'] }
                },
                { 
                    '$group': { 
                        '_id': '$client_id',
                        'project_name': { '$first': '$project_name' }
                    }
                }
            ]))

            combined_accounts = available_current_accounts + available_old_accounts
            some_projects = []
            if len(combined_accounts) != 0:
                seen_project_names = set()
                unique_accounts = []

                for account in combined_accounts:
                    if account['project_name'] not in seen_project_names:
                        seen_project_names.add(account['project_name'])
                        unique_accounts.append(account)

                for item in unique_accounts:
                    item_details = {
                        'project_name': item['project_name'],
                    }
                    items_to_update.append(item_details)
                
                some_projects = sorted(items_to_update, key=lambda x: x['project_name'])

            return render_template('add new account.html',some_projects=some_projects,dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

@accounting.route('/add-new-account', methods=['POST'])
def add_new_account():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                    'password': 0, 'auth': 0, 'dark_mode': 0})
            last_receipt_cursor = db.transaction_finance_accounts.find(
                {'company_name': company['company_name']},
                {'receipt_number': 1, '_id': 0}
            ).sort('receipt_number', -1).limit(1)

            old_receipt_cursor = db.old_transaction_finance_accounts.find(
                {'company_name': company['company_name']},
                {'receipt_number': 1, '_id': 0}
            ).sort('receipt_number', -1).limit(1)

            last_receipt_number = next(last_receipt_cursor, None)
            old_receipt_number = next(old_receipt_cursor, None)

            if last_receipt_number:
                if old_receipt_number:
                    if last_receipt_number['receipt_number']>old_receipt_number['receipt_number']:
                        receipt_number = last_receipt_number['receipt_number'] + 1
                    else:
                        receipt_number = old_receipt_number['receipt_number'] + 1
                else:
                    receipt_number = last_receipt_number['receipt_number'] + 1
            elif old_receipt_number:
                receipt_number = old_receipt_number['receipt_number'] + 1
            else:
                receipt_number = 1

            all_items = request.json.get('items', [])
            timestamp = datetime.now()
            added = 0
            for item in all_items:
                item['client_name'] = item.get('client_name', '').strip().title()
                item['project_name'] = item.get('project_name', '').strip().title()
                
                try:
                    item['measure'] = float(item.get('measure', 0))
                    item['value_amount'] = float(item.get('value_amount', 0))
                    item['amount_paid'] = float(item.get('amount_paid', 0))
                    item['amount'] = item['amount_paid']
                    item['date_of_payment'] = datetime.strptime(item.get('date_of_payment', ''), '%Y-%m-%d')
                    item['amount_demanded'] = item['value_amount'] - item['amount_paid']
                    item['company_name'] = company.get('company_name', '')
                    item['timestamp'] = timestamp
                    item['receipt_number'] = receipt_number

                    if item['amount_demanded'] == 0:                
                        result = db.old_transaction_finance_accounts.insert_one(item)
                        generated_id = result.inserted_id
                        receipt_id = str(generated_id)

                        buffer = BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=letter)

                        url = f'https://michmanagement.onrender.com//get_financial_receipt?id={receipt_id}'
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=3,
                            border=4,
                        )
                        qr.add_data(url)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        img.save(f'payment_receipt_qr_{receipt_id}.png')

                        data = [
                            ['Payment Receipt - ' + company['company_name'], ''],
                            ['Receipt No:', receipt_number],
                            ['Receipt for:', item['client_name']],
                            ['Tel:', item['telephone']],
                            ['Email:', item['email']],
                            ['Project Name:', item['project_name']],
                            ['Measure:', f"{item['measure']} {item['unit_of_measurement']}"],
                            ['Value:', f"UGX {item['value_amount']}"],
                            ['Amount Paid:', f"UGX {item['amount_paid']}"],
                            ['Payment Mode:', item['payment_mode']],
                            ['Date Paid:', (item['date_of_payment']).strftime('%Y-%m-%d')],
                            ['Balance:', f"UGX {item['amount_demanded']}"],
                            ['Payment Status:', f"Cleared"],
                            ['Prepared by:', f"{login_data} on {timestamp.strftime('%Y-%m-%d')}"]
                        ]

                        table = Table(data)

                        table.setStyle(TableStyle([
                            ('SPAN', (0, 0), (1, 0)),
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),

                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 14),

                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('GRID', (0,0), (-1,-1), 1, colors.black),
                            ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Oblique')
                        ]))

                        qr_code_img = f'payment_receipt_qr_{receipt_id}.png'
                        qr_code = PDFImage(qr_code_img)
                        qr_code.hAlign = 'CENTER'

                        elements = [table, qr_code]
                        doc.build(elements)

                        pdf_data = buffer.getvalue()
                        buffer.close()
                        payment_receipt_base64 = base64.b64encode(pdf_data).decode()

                        os.remove(f'payment_receipt_qr_{receipt_id}.png')
                        
                        db.old_transaction_finance_accounts.update_one(
                            {'_id': generated_id},
                            {'$set': {'client_id': generated_id, 'payment_receipt': payment_receipt_base64}}
                        )
                    else:
                        result = db.transaction_finance_accounts.insert_one(item)

                        generated_id = result.inserted_id
                        receipt_id = str(generated_id)

                        # Create a payment receipt PDF file
                        buffer = BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=letter)

                        # QR Code Generation
                        url = f'https://michmanagement.onrender.com//get_financial_receipt?id={receipt_id}'
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=3,
                            border=4,
                        )
                        qr.add_data(url)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        img.save(f'payment_receipt_qr_{receipt_id}.png')

                        # Create the receipt details
                        data = [
                            ['Payment Receipt - ' + company['company_name'], ''],
                            ['Receipt No:', receipt_number],
                            ['Receipt for:', item['client_name']],
                            ['Tel:', item['telephone']],
                            ['Email:', item['email']],
                            ['Project Name:', item['project_name']],
                            ['Measure:', f"{item['measure']} {item['unit_of_measurement']}"],
                            ['Value:', f"UGX {item['value_amount']}"],
                            ['Amount Paid:', f"UGX {item['amount_paid']}"],
                            ['Payment Mode:', item['payment_mode']],
                            ['Date Paid:', (item['date_of_payment']).strftime('%Y-%m-%d')],
                            ['Balance:', f"UGX {item['amount_demanded']}"],
                            ['Payment Status:', f"Pending"],
                            ['Prepared by:', f"{login_data} on {timestamp.strftime('%Y-%m-%d')}"]
                        ]

                        # Create a table with the receipt details
                        table = Table(data)

                        # Add a table style
                        table.setStyle(TableStyle([
                            ('SPAN', (0, 0), (1, 0)),  # Merge the first row
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),

                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 14),

                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('GRID', (0,0), (-1,-1), 1, colors.black),
                            ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Oblique')  # Make the last cell on the last row italic
                        ]))

                        # Load your QR code image
                        qr_code_img = f'payment_receipt_qr_{receipt_id}.png'
                        qr_code = PDFImage(qr_code_img)
                        qr_code.hAlign = 'CENTER'

                        # Add the QR code image to the elements list before building the PDF
                        elements = [table, qr_code]
                        doc.build(elements)

                        # Get the PDF data and encode it as base64
                        pdf_data = buffer.getvalue()
                        buffer.close()
                        payment_receipt_base64 = base64.b64encode(pdf_data).decode()

                        # Delete the QR code image file
                        os.remove(f'payment_receipt_qr_{receipt_id}.png')
                        
                        db.transaction_finance_accounts.update_one(
                            {'_id': generated_id},
                            {'$set': {'payment_receipt': payment_receipt_base64}}
                        )
                    # Create the email message
                    if item['email']:
                        if send_emails is not None:
                            msg = Message(f"Payment Receipt From {company['company_name']}", 
                                        sender='michmanage@outlook.com', 
                                        recipients=[item['email']])
                            msg.html = f"""
                            <html>
                            <body>
                            <p>Dear {item['client_name']},</p>
                            <p>Please find attached your payment receipt on the {item['project_name']} project at {company['company_name']}.</p>
                            <p>Best Regards,</p>
                            <p>Mich Manage</p>
                            </body>
                            </html>
                            """

                            # Attach the PDF receipt to the email
                            msg.attach("Payment Receipt.pdf", "application/pdf", pdf_data)

                            # Send the email
                            thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
                            thread.start()
                            
                    db.audit_logs.insert_one({
                        'user': login_data,
                        'Activity': 'Added new account',
                        'Item': item['client_name'],
                        'timestamp': timestamp
                    })
                    added = 1
        
                except (ValueError, TypeError) as e:
                    # Log or handle the exception as needed
                    flash(f"Error processing account {item.get('itemName', 'unknown')}: {e}", 'error')
                    
                receipt_number += 1
            if added == 1:
                flash('Accounts were added','success')
            return jsonify({'redirect': url_for('accounting_route.new_accounts_page')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

@accounting.route('/update existing account')
def update_existing_account():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            items_to_update = []
            available_accounts = db.transaction_finance_accounts.find({'company_name': company['company_name'],'amount_demanded': {'$ne': 0}})
            if available_accounts:
                for item in available_accounts:
                    item_details = {
                        'client_id': str(item['_id']),
                        'client_name': item['client_name'],
                        'project_name': item['project_name'],
                        'amount_demanded': item.get('amount_demanded', '')
                    }
                    items_to_update.append(item_details)
                
                items_to_update = sorted(items_to_update, key=lambda x: x['client_name'])

            return render_template('update accounts.html', dp=dp_str, items_to_update=items_to_update)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

@accounting.route('/update-accounts', methods=['POST'])
def update_accounts():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            all_items = request.json.get('items', [])  # Access the JSON data sent from the client
            timestamp = datetime.now()

            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                    'password': 0, 'auth': 0, 'dark_mode': 0})
            
            last_receipt_cursor = db.transaction_finance_accounts.find(
                {'company_name': company['company_name']},
                {'receipt_number': 1, '_id': 0}
            ).sort('receipt_number', -1).limit(1)

            old_receipt_cursor = db.old_transaction_finance_accounts.find(
                {'company_name': company['company_name']},
                {'receipt_number': 1, '_id': 0}
            ).sort('receipt_number', -1).limit(1)

            last_receipt_number = next(last_receipt_cursor, None)
            old_receipt_number = next(old_receipt_cursor, None)

            if last_receipt_number:
                if old_receipt_number:
                    if last_receipt_number['receipt_number']>old_receipt_number['receipt_number']:
                        receipt_number = last_receipt_number['receipt_number'] + 1
                    else:
                        receipt_number = old_receipt_number['receipt_number'] + 1
                else:
                    receipt_number = last_receipt_number['receipt_number'] + 1
            elif old_receipt_number:
                receipt_number = old_receipt_number['receipt_number'] + 1
            else:
                receipt_number = 1
                
            updated = 0
            for item in all_items:
                updated = 1
                account = db.transaction_finance_accounts.find_one({'_id': ObjectId(item['client_id'])})
                account['client_id'] = account.pop('_id')
                item['amount_paid'] = float(item.get('amount_paid', 0))
                item['date_of_payment'] = datetime.strptime(item.get('date_of_payment', ''), '%Y-%m-%d')
                amount = account['amount'] + item['amount_paid']
                amount_demanded = account['value_amount'] - amount
                if amount_demanded == 0:
                    payment_status = "Cleared"
                else:
                    payment_status = "Pending"
                db.old_transaction_finance_accounts.insert_one(account)

                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)

                url = f'https://michmanagement.onrender.com//get_financial_receipt?id={item["client_id"]}'
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=3,
                    border=4,
                )
                qr.add_data(url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img.save(f'payment_receipt_qr_{item["client_id"]}.png')

                data = [
                    ['Payment Receipt - ' + account['company_name'], ''],
                    ['Receipt No:', receipt_number],
                    ['Receipt for:', account['client_name']],
                    ['Tel:', account['telephone']],
                    ['Email:', account['email']],
                    ['Project Name:', account['project_name']],
                    ['Measure:', f"{account['measure']} {account['unit_of_measurement']}"],
                    ['Value:', f"UGX {account['value_amount']}"],
                    ['Amount Paid:', f"UGX {item['amount_paid']}"],
                    ['Payment Mode:', item['payment_mode']],
                    ['Date Paid:', (item['date_of_payment']).strftime('%Y-%m-%d')],
                    ['Balance:', f"UGX {amount_demanded}"],
                    ['Payment Status:', f"{payment_status}"],
                    ['Prepared by:', f"{login_data} on {timestamp.strftime('%Y-%m-%d')}"]
                ]

                table = Table(data)

                table.setStyle(TableStyle([
                    ('SPAN', (0, 0), (1, 0)),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),

                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),

                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Oblique')
                ]))

                qr_code_img = f'payment_receipt_qr_{item["client_id"]}.png'
                qr_code = PDFImage(qr_code_img)
                qr_code.hAlign = 'CENTER'

                elements = [table, qr_code]
                doc.build(elements)

                pdf_data = buffer.getvalue()
                buffer.close()
                payment_receipt_base64 = base64.b64encode(pdf_data).decode()

                os.remove(f'payment_receipt_qr_{item["client_id"]}.png')

                email = account.get('email')
                if email and email.strip():
                    if send_emails is not None:
                        msg = Message(f"Payment Receipt From {account['company_name']}", 
                                    sender='michmanage@outlook.com', 
                                    recipients=[account['email']])
                        msg.html = f"""
                        <html>
                        <body>
                        <p>Dear {account['client_name']},</p>
                        <p>Please find attached your payment receipt on the {account['project_name']} project at {account['company_name']}.</p>
                        <p>Best Regards,</p>
                        <p>Mich Manage</p>
                        </body>
                        </html>
                        """

                        # Attach the PDF receipt to the email
                        msg.attach("Payment Receipt.pdf", "application/pdf", pdf_data)

                        # Send the email
                        thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
                        thread.start()

                db.transaction_finance_accounts.update_one({'_id': ObjectId(item['client_id'])},{'$set': {'payment_mode': item['payment_mode'], 'amount_paid': item['amount_paid'], 'amount': amount, 'amount_demanded': amount_demanded, 'timestamp':timestamp, 'payment_receipt':payment_receipt_base64}})

                updated_document = db.transaction_finance_accounts.find_one({'_id': ObjectId(item['client_id'])})
                if updated_document['amount_demanded'] == 0:
                    updated_document['client_id'] = updated_document.pop('_id')
                    db.old_transaction_finance_accounts.insert_one(updated_document)
                    db.transaction_finance_accounts.delete_one({'_id': ObjectId(item['client_id'])})
                db.audit_logs.insert_one({'user': login_data,'Activity': 'Updated account','Item': item['client_id'],'timestamp': timestamp})
                receipt_number += 1

            if updated == 1:
                flash('Client updated successfully', 'success')
            return jsonify({'redirect': url_for('accounting_route.update_existing_account')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

@accounting.route('/current-accounts')
def current_accounts():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            
            company_name = company['company_name']
            current_accounts = list(db.transaction_finance_accounts.find({'company_name': company_name}))
            current_accounts.sort(key=lambda x: x.get('timestamp', x['date_of_payment']), reverse=True)
            current_accounts.sort(key=lambda x: x['client_name'])

            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            return render_template('current accounts.html', current_accounts = current_accounts, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

@accounting.route('/accounts-history')
def accounts_history():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            
            subscription = db.managers.find_one({'name': company['company_name']}, {'account_type': 1, 'manager_email': 1, '_id': 0})
            account_type = subscription['account_type']
            # Remove any empty strings from the list
            account_type = [atype for atype in account_type if atype]

            if 'Accounting' in account_type:
                company_name = company['company_name']
                twelve_months_ago = datetime.now() - timedelta(days=365)
                old_accounts = list(db.old_transaction_finance_accounts.find({'company_name': company_name,'date_of_payment': {'$gte': twelve_months_ago}}))
                old_accounts.sort(key=lambda x: x.get('timestamp', x['date_of_payment']), reverse=True)
                old_accounts.sort(key=lambda x: x['client_name'])

                if 'dp' in company:
                    dp_str = company['dp']
                else:
                    dp_str = None
                return render_template('old accounts.html', old_accounts = old_accounts, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

####edit finances
@accounting.route('/edit-finance-accounts/<item_id>', methods=['GET', 'POST'])
def edit_finance_accounts(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if company.get('edit_finance') in ('yes', None):
                if 'dp' in company:
                    dp_str = company['dp']
                else:
                    dp_str = None
                return render_template('edit finance accounts.html',item_id=item_id,dp=dp_str)
            else:
                flash('You do not have rights to make edits', 'error')
                return redirect('/current-accounts')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')
        
@accounting.route('/apply-finance-edits', methods=['POST'])
def apply_finance_edits():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
            item_id = request.form.get("item_id")
            client_name = request.form.get("client_name")
            telephone = request.form.get("telephone")
            email = request.form.get("email")
            project_name = request.form.get("project_name")
            measure = request.form.get("measure")
            unit_of_measurement = request.form.get("unit_of_measurement")
            value_amount = request.form.get("value_amount")
            payment_mode = request.form.get("payment_mode")
            amount_paid = request.form.get("amount_paid")
            date_of_payment = request.form.get("date_of_payment")

            timestamp = datetime.now()
            
            selected_item = db.transaction_finance_accounts.find_one({'_id': ObjectId(item_id)})

            if selected_item:
                if client_name:
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'client_name': client_name}})
                    db.old_transaction_finance_accounts.update_one({'client_id': ObjectId(item_id)},{'$set': {'client_name': client_name}})
                if telephone:
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'telephone': telephone}})
                    db.old_transaction_finance_accounts.update_one({'client_id': ObjectId(item_id)},{'$set': {'telephone': telephone}})
                if email:
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'email': email}})
                    db.old_transaction_finance_accounts.update_one({'client_id': ObjectId(item_id)},{'$set': {'email': email}})
                if project_name:
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'project_name': project_name}})
                    db.old_transaction_finance_accounts.update_one({'client_id': ObjectId(item_id)},{'$set': {'project_name': project_name}})
                if measure:
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'measure': measure}})
                    db.old_transaction_finance_accounts.update_one({'client_id': ObjectId(item_id)},{'$set': {'measure': measure}})
                if unit_of_measurement:
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'unit_of_measurement': unit_of_measurement}})
                    db.old_transaction_finance_accounts.update_one({'client_id': ObjectId(item_id)},{'$set': {'unit_of_measurement': unit_of_measurement}})
                if value_amount:
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'value_amount': value_amount}})
                    db.old_transaction_finance_accounts.update_one({'client_id': ObjectId(item_id)},{'$set': {'value_amount': value_amount}})
                if payment_mode:
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'payment_mode': payment_mode}})
                    db.old_transaction_finance_accounts.update_one({'client_id': ObjectId(item_id)},{'$set': {'payment_mode': payment_mode}})
                if amount_paid:
                    amount_paid = float(amount_paid)
                    if amount_paid <= (selected_item['amount_paid'] + selected_item['amount_demanded']):
                        new_amount = selected_item['amount'] - selected_item['amount_paid'] + amount_paid
                        amount_demanded = selected_item['value_amount'] - new_amount

                        ##generate payment receipt
                        # Create a payment receipt PDF file
                        buffer = BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=letter)

                        # QR Code Generation
                        url = f'https://michmanagement.onrender.com//get_financial_receipt?id={item_id}'
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=3,
                            border=4,
                        )
                        qr.add_data(url)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        img.save(f'payment_receipt_qr_{item_id}.png')

                        # Create the receipt details
                        data = [
                            ['Payment Receipt - ' + selected_item['company_name'], ''],
                            ['Receipt for:', selected_item['client_name']],
                            ['Tel:', selected_item['telephone']],
                            ['Email:', selected_item['email']],
                            ['Project Name:', selected_item['project_name']],
                            ['Measure:', f"{selected_item['measure']} {selected_item['unit_of_measurement']}"],
                            ['Value:', f"UGX {selected_item['value_amount']}"],
                            ['Amount Paid:', f"UGX {amount_paid}"],
                            ['Payment Mode:', selected_item['payment_mode']],
                            ['Date Paid:', (selected_item['date_of_payment']).strftime('%Y-%m-%d')],
                            ['Balance:', f"UGX {amount_demanded}"],
                            ['Prepared by:', f"{login_data} on {timestamp.strftime('%Y-%m-%d')}"]
                        ]

                        # Create a table with the receipt details
                        table = Table(data)

                        # Add a table style
                        table.setStyle(TableStyle([
                            ('SPAN', (0, 0), (1, 0)),  # Merge the first row
                            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),

                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 14),

                            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                            ('GRID', (0,0), (-1,-1), 1, colors.black),
                            ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Oblique')  # Make the last cell on the last row italic
                        ]))

                        # Load your QR code image
                        qr_code_img = f'payment_receipt_qr_{item_id}.png'
                        qr_code = PDFImage(qr_code_img)
                        qr_code.hAlign = 'CENTER'

                        # Add the QR code image to the elements list before building the PDF
                        elements = [table, qr_code]
                        doc.build(elements)

                        # Get the PDF data and encode it as base64
                        pdf_data = buffer.getvalue()
                        buffer.close()
                        payment_receipt_base64 = base64.b64encode(pdf_data).decode()

                        # Delete the QR code image file
                        os.remove(f'payment_receipt_qr_{item_id}.png')

                        ###send payment receipt
                        email = selected_item.get('email')
                        if email and email.strip():
                            if send_emails is not None:
                                msg = Message(f"Payment Receipt From {selected_item['company_name']}", 
                                            sender='michmanage@outlook.com', 
                                            recipients=[selected_item['email']])
                                msg.html = f"""
                                <html>
                                <body>
                                <p>Dear {selected_item['client_name']},</p>
                                <p>Please find attached your payment receipt on the {selected_item['project_name']} project at {selected_item['company_name']}.</p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
                                thread.start()
                                
                        db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'amount_paid': amount_paid, 'amount': new_amount, 'amount_demanded': amount_demanded, 'payment_receipt':payment_receipt_base64}})
                    else:
                        flash('Please enter another amount', 'error')
                if date_of_payment:
                    date_of_payment = datetime.strptime(date_of_payment, '%Y-%m-%d')
                    db.transaction_finance_accounts.update_one({'_id': ObjectId(item_id)},{'$set': {'date_of_payment': date_of_payment}})
                flash('Account has been updated', 'success')
                db.audit_logs.insert_one({'user': login_data,'Activity': 'Edit finance accounts','Item': item_id,'timestamp': datetime.now()})
            else:
                flash('Please select an up-to-date expense', 'error')
            return redirect('/current-accounts')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')
    
####delete expense
@accounting.route('/delete-finance-account/<item_id>', methods=['POST'])
def delete_finance_account(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if company.get('edit_finance') in ('yes', None):
                selected_item = db.transaction_finance_accounts.find_one({'_id': ObjectId(item_id)})
                if selected_item:
                    db.transaction_finance_accounts.delete_one({'_id': ObjectId(item_id)})
                    db.old_transaction_finance_accounts.delete_many({'client_id': ObjectId(item_id)})
                    db.audit_logs.insert_one({'user': login_data,'Activity': 'Finance account deletion','Item': item_id,'timestamp': datetime.now()})
                    flash('Account was deleted', 'success')
                else:
                    flash('Selection does not exist in current accounts', 'error')
                return redirect('/current-accounts')
            else:
                flash('You do not have rights to delete', 'error')
                return redirect('/current-accounts')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')

###DOANLOAD FINANCE DATA   
@accounting.route('/download-financial-data', methods=["POST"])
def download_financial_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')

            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            current_accounts = list(db.transaction_finance_accounts.find(
                {'company_name': company['company_name'], 'date_of_payment': {'$gte': startdate, '$lte': enddate}},
                {'_id': 0, 'company_name': 0}
            ))

            old_accounts = list(db.old_transaction_finance_accounts.find(
                {'company_name': company['company_name'], 'date_of_payment': {'$gte': startdate, '$lte': enddate}},
                {'_id': 0, 'company_name': 0}
            ))

            accounts = current_accounts + old_accounts

            if len(accounts) != 0:
                # Sort data by expenseDate in descending order
                sorted_accounts = sorted(accounts, key=lambda x: x["date_of_payment"], reverse=True)

                # Create Excel file
                excel_buffer = BytesIO()
                wb = Workbook()
                ws = wb.active
                ws.title = "Expenses"

                # Write header row
                headers = ['Client Name','Telephone','Email','Project','Account Type','Measure','Unit','Value','Mode Of Payment','Amount Last Paid','Total Payment','Date Of Payment','Balance']
                ws.append(headers)

                # Write data rows
                for account in sorted_accounts:
                    row = [
                        account.get('client_name', ''),
                        account.get('telephone', ''),
                        account.get('email', ''),
                        account.get('project_name', ''),
                        account.get('account_type', ''),
                        account.get('measure', 0),
                        account.get('unit_of_measurement', ''),
                        account.get('value_amount', 0),
                        account.get('payment_mode', ''),
                        account.get('amount_paid', 0),
                        account.get('amount', 0),
                        account.get('date_of_payment', '').strftime('%Y-%m-%d') if isinstance(account.get('date_of_payment'), datetime) else '',
                        account.get('amount_demanded', 0)
                    ]
                    ws.append(row)

                wb.save(excel_buffer)
                excel_buffer.seek(0)

                # Create the response
                response = make_response(excel_buffer.getvalue())
                response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Finances_{startdate_on_str}_{enddate_on_str}.xlsx"
                response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

                # Clean up
                del wb
                del excel_buffer
                gc.collect()

                return response
            else:
                flash('No data was found', 'error')
                return redirect('/current-accounts')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')
        
@accounting.route('/accounts-overview', methods=["GET", "POST"])
def accounts_overview():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/manager login page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")

            if startdate_on_str and enddate_on_str:
                start_of_previous_month = datetime.strptime(startdate_on_str, '%Y-%m-%d')
                first_day_of_current_month = datetime.strptime(enddate_on_str, '%Y-%m-%d')
            else:
                today = datetime.today()

                start_of_previous_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                if today.month == 12:
                    first_day_of_current_month = today.replace(year=today.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                else:
                    first_day_of_current_month = today.replace(month=today.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            
            current_accounts_info_pipeline = [
                {
                    '$match': {
                        'company_name': company['company_name'],
                        'date_of_payment': {'$gte': start_of_previous_month, '$lte': first_day_of_current_month}
                    }
                },
                {
                    '$group': {
                        '_id': '$project_name',
                        'total_amount': {'$sum': '$amount'},
                        'total_amount_demanded': {'$sum': '$amount_demanded'}
                    }
                },
                {
                    '$sort': {'total_amount': -1}
                }
            ]

            current_accounts_info = list(db.transaction_finance_accounts.aggregate(current_accounts_info_pipeline))

            project_name = []
            amount = []
            amount_demanded = []

            for current_record in current_accounts_info:
                project_name.append(current_record['_id'])
                amount.append(current_record['total_amount'])
                amount_demanded.append(current_record['total_amount_demanded'])

            # Create the DataFrame
            current_accounts_info_df = pd.DataFrame({
                'Project Name': project_name,
                'Total Amount Paid': amount,
                'Amount Demanded': amount_demanded
            })

            # Aggregation for old accounts
            old_accounts_counts = db.old_transaction_finance_accounts.aggregate([
                {
                    '$match': {
                        'company_name': company['company_name'],
                        'date_of_payment': {'$gte': start_of_previous_month, '$lte': first_day_of_current_month}
                    }
                },
                {
                    '$group': {
                        '_id': '$project_name',
                        'unique_clients': {'$addToSet': '$client_id'},
                        'appearance_count': {'$sum': 1}  # Count appearances
                    }
                },
                {
                    '$project': {
                        '_id': 1,
                        'unique_client_count': {'$size': '$unique_clients'},
                        'appearance_count': 1  # Include appearance count
                    }
                }
            ])

            # Aggregation for current accounts
            current_accounts_counts = db.transaction_finance_accounts.aggregate([
                {
                    '$match': {
                        'company_name': company['company_name'],
                        'date_of_payment': {'$gte': start_of_previous_month, '$lte': first_day_of_current_month}
                    }
                },
                {
                    '$group': {
                        '_id': '$project_name',
                        'unique_clients': {'$addToSet': '$_id'},
                        'appearance_count': {'$sum': 1}  # Count appearances
                    }
                },
                {
                    '$project': {
                        '_id': 1,
                        'unique_client_count': {'$size': '$unique_clients'},
                        'appearance_count': 1  # Include appearance count
                    }
                }
            ])

            # Convert aggregation results to dictionaries for easy lookup
            old_accounts_dict = {item['_id']: {'unique_client_count': item['unique_client_count'], 'appearance_count': item['appearance_count']} for item in old_accounts_counts}
            current_accounts_dict = {item['_id']: {'unique_client_count': item['unique_client_count'], 'appearance_count': item['appearance_count']} for item in current_accounts_counts}

            combined_counts = []

            # Combine keys from both dictionaries
            all_project_names = set(old_accounts_dict.keys()).union(current_accounts_dict.keys())

            for project_name in all_project_names:
                old_data = old_accounts_dict.get(project_name, {'unique_client_count': 0, 'appearance_count': 0})
                current_data = current_accounts_dict.get(project_name, {'unique_client_count': 0, 'appearance_count': 0})
                
                # Combine the counts
                combined_count = old_data['unique_client_count'] + current_data['unique_client_count']
                combined_appearance_count = old_data['appearance_count'] + current_data['appearance_count']
                
                # Append the results
                combined_counts.append({
                    'Project Name': project_name,
                    'Unique Client Count': combined_count,
                    'Appearance Count': combined_appearance_count
                })

            count_clients_per_project_df = pd.DataFrame(combined_counts)

            ##PAYMENT TRENDS
            twelve_months_ago = datetime.now() - timedelta(days=365)
            old_accounts_aggregation = db.old_transaction_finance_accounts.aggregate([
                {
                    '$match': {
                        'company_name': company['company_name'],
                        'date_of_payment': {'$gte': twelve_months_ago}
                    }
                },
                {
                    '$group': {
                        '_id': {
                            'year': {'$year': '$date_of_payment'},
                            'month': {'$month': '$date_of_payment'}
                        },
                        'total_amount': {'$sum': '$amount'}
                    }
                },
                {
                    '$sort': {
                        '_id.year': 1,
                        '_id.month': 1
                    }
                }
            ])

            current_accounts_aggregation = db.transaction_finance_accounts.aggregate([
                {
                    '$match': {
                        'company_name': company['company_name'],
                        'date_of_payment': {'$gte': twelve_months_ago}
                    }
                },
                {
                    '$group': {
                        '_id': {
                            'year': {'$year': '$date_of_payment'},
                            'month': {'$month': '$date_of_payment'}
                        },
                        'total_amount': {'$sum': '$amount'}
                    }
                },
                {
                    '$sort': {
                        '_id.year': 1,
                        '_id.month': 1
                    }
                }
            ])

            # Convert the aggregations to dictionaries for easier processing
            old_accounts_dict = {f"{item['_id']['year']}-{item['_id']['month']:02d}": item['total_amount'] for item in old_accounts_aggregation}
            current_accounts_dict = {f"{item['_id']['year']}-{item['_id']['month']:02d}": item['total_amount'] for item in current_accounts_aggregation}

            # Combine sums for the same months
            combined_sums = {}

            for key in set(old_accounts_dict.keys()).union(current_accounts_dict.keys()):
                old_sum = old_accounts_dict.get(key, 0)
                current_sum = current_accounts_dict.get(key, 0)
                combined_sums[key] = old_sum + current_sum

            df_trended = pd.DataFrame(
                list(combined_sums.items()), 
                columns=['Month', 'Total Amount']
            )

            # Convert 'Month' column to datetime format
            df_trended['Month'] = pd.to_datetime(df_trended['Month'], format='%Y-%m')
            # Create a new column for the month and year in the desired format
            df_trended['Month_Name'] = df_trended['Month'].dt.strftime('%B %Y')
            # Sort by the 'Month' column to ensure the data is ordered from oldest to newest
            df_trended = df_trended.sort_values(by='Month')
            # Drop the original 'Month' column if needed and keep 'Month_Name' and 'Total Amount'
            df_trended = df_trended[['Month_Name', 'Total Amount']].reset_index(drop=True)

            #####PLOTS
            projectName = []
            amount = []
            top_current_items = current_accounts_info_df.sort_values(by='Total Amount Paid', ascending=False).head(10)

            if not top_current_items.empty:
                for index, row in top_current_items.iterrows():
                    projectName.append(row['Project Name'])
                    amount.append(row['Total Amount Paid'])
            top10CurrentAccounts = list(zip(projectName, amount))

            projectNameDemanded = []
            amountDemanded = []
            top_demanded_items = current_accounts_info_df.sort_values(by='Amount Demanded', ascending=False).head(10)

            if not top_demanded_items.empty:
                for index, row in top_demanded_items.iterrows():
                    projectNameDemanded.append(row['Project Name'])
                    amountDemanded.append(row['Amount Demanded'])
            top10DemandedAccounts = list(zip(projectNameDemanded, amountDemanded))

            projectNameCount = []
            clients = []

            if not count_clients_per_project_df.empty:
                count_clients_per_project_df = count_clients_per_project_df.sort_values(by='Appearance Count', ascending=False)
                count_clients_per_project_df = count_clients_per_project_df.reset_index(drop=True) 
                for index, row in count_clients_per_project_df.iterrows():
                    projectNameCount.append(row['Project Name'])
                    clients.append(row['Appearance Count'])
            top10ClientProject = list(zip(projectNameCount, clients))

            trended_chart = {
                'labels': df_trended['Month_Name'].tolist(),
                'values': df_trended['Total Amount'].tolist()
            }

            del current_accounts_info_df,count_clients_per_project_df,df_trended
            gc.collect()
            dp = company.get('dp')
            dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
            return render_template('accounting dashboard.html',top10CurrentAccounts=top10CurrentAccounts,
                                top10DemandedAccounts=top10DemandedAccounts,
                                top10ClientProject=top10ClientProject,trended_chart=trended_chart,
                                start_of_previous_month=start_of_previous_month,
                                first_day_of_current_month=first_day_of_current_month, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/manager login page')
    
@accounting.route('/view-finance-receipt/<id>', methods=["GET"])
def view_finance_receipt(id):
    db, fs = get_db_and_fs()
    # Retrieve the tenant document using tenant_id
    account = db.transaction_finance_accounts.find_one({'_id': ObjectId(id)})
    if account:
        if 'payment_receipt' in account:
            # Convert the base64 string back to bytes
            payment_receipt = base64.b64decode(account['payment_receipt'])

            # Create a BytesIO object from the PDF data
            pdf_io = io.BytesIO(payment_receipt)

            # Create the file name
            file_name = f"{id}.pdf"

            # Create a custom response
            response = make_response(pdf_io.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename={file_name}'

            return response
        else:
            flash("No receipt found for this transaction", 'error')
            return redirect('/current-accounts')
    else:
        old_account = db.old_transaction_finance_accounts.find_one({'_id': ObjectId(id)})
        if old_account:
            if 'payment_receipt' in old_account:
                payment_receipt = base64.b64decode(old_account['payment_receipt'])

                # Create a BytesIO object from the PDF data
                pdf_io = io.BytesIO(payment_receipt)

                # Create the file name
                file_name = f"{id}.pdf"

                # Create a custom response
                response = make_response(pdf_io.getvalue())
                response.headers['Content-Type'] = 'application/pdf'
                response.headers['Content-Disposition'] = f'attachment; filename={file_name}'

                return response
            else:
                flash("No receipt found for this transaction", 'error')
                return redirect('/accounts-history')
        else:
            flash("No receipt found for this transaction", 'error')
            return redirect('/accounts-history')

@accounting.route('/get_financial_receipt', methods=['GET'])
def get_financial_receipt():
    db, fs = get_db_and_fs()
    id = request.args.get('id')

    receipt_data = db.transaction_finance_accounts.find_one({'_id': ObjectId(id)}, {'payment_receipt': 1, '_id': 0})

    if receipt_data is None:
        old_receipt_data = db.old_transaction_finance_accounts.find_one({'client_id': ObjectId(id)}, {'payment_receipt': 1, '_id': 0})
        if old_receipt_data:
            # Convert the base64 string back to bytes
            payment_receipt = base64.b64decode(old_receipt_data['payment_receipt'])

            # Create a BytesIO object from the PDF data
            pdf_io = io.BytesIO(payment_receipt)

            # Create the file name
            file_name = f"{id}.pdf"

            # Create a custom response
            response = make_response(pdf_io.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename={file_name}'

            return response

    else:
        # Convert the base64 string back to bytes
        payment_receipt = base64.b64decode(receipt_data['payment_receipt'])

        # Create a BytesIO object from the PDF data
        pdf_io = io.BytesIO(payment_receipt)

        # Create the file name
        file_name = f"{id}.pdf"

        # Create a custom response
        response = make_response(pdf_io.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={file_name}'

        return response
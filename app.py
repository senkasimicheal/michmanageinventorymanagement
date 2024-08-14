from flask import Flask, render_template, url_for, send_from_directory, request, flash, redirect, session, make_response, jsonify
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
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
from openpyxl import Workbook, load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from zipfile import ZipFile
import tempfile
import string
import qrcode
import threading
import time
from docx2pdf import convert
import PyPDF2
import gc
from collections import defaultdict

app = Flask(__name__, static_folder='static')
app.secret_key = secrets.token_hex(16)
scheduler = BackgroundScheduler()

@app.route('/static/<path:filename>')
def static_files(filename):
    response = send_from_directory(app.static_folder, filename)
    response.headers['Cache-Control'] = 'public, max-age=2592000'  # Cache for 30 days
    return response

def get_mongo_client():
    # client = MongoClient('mongodb://localhost:27017/')
    client = MongoClient('mongodb+srv://micheal:QCKh2uCbPTdZ5sqS@cluster0.rivod.mongodb.net/ANALYTCOSPHERE?retryWrites=true&w=majority')
    return client

# Function to get the database and GridFS instance
def get_db_and_fs():
    client = get_mongo_client()
    db = client.PropertyManagement
    fs = GridFS(db, collection='contracts')
    return db, fs

app.config.update(
    MAIL_SERVER='smtp.sendgrid.net',
    MAIL_PORT=587,
    MAIL_USERNAME='apikey',
    MAIL_PASSWORD='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',
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False
)

mail = Mail(app)

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

utc = pytz.UTC

def generate_file_password(length=12):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

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

def parse_iso_format(iso_str):
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1]  # Remove 'Z'
        dt = datetime.fromisoformat(iso_str)
        return dt.replace(tzinfo=pytz.UTC)
    else:
        return datetime.fromisoformat(iso_str)

@app.before_request
def before_request():
    if 'logged_in' not in session and request.endpoint not in ('send_message', 'tenant_register_account', 'register_account','load_verification_page', 'verifying_your_account', 'terms_of_service', 'privacy_policy', 'admin', 'adminlogin', 'add_property_manager', 'complaint_form', 'tenant_data', 'tenant_download', 'get_receipt','get_financial_receipt',
                                                               'google_verification', 'contact', 'sitemap', 'about', 'tenant_login_page', 'tenant_login', 'tenant_register', 'register', 'login', 'userlogin', 'index', 'static', 'verify_username', 'send_verification_code', 'password_reset_verifying_user', 'add_property_manager_page',
                                                               'add_complaint', 'my_complaints', 'tenant_reply_complaint', 'resolve_complaints' , 'update_complaint', 'new_subscription', 'new_subscription_initiated', 'export', 'apply_for_advert', 'submit_advert_application', 'authentication','tenant_account_setup_page', 'resend_auth_code',
                                                               'tenant_account_setup_initiated', 'tenant_authentication', 'download_apk', 'manager_login_page', 'manager_register_page', 'tenant_register_page', 'tenant_login_page', 'add_properties', 'add_tenants', 'export_tenant_data', 'add_new_stock_page','documentation','manager_notifications',
                                                               'tenant_notifications', 'tenant_popup_notifications','registered_clients','apply_item_edits','expenses_page','add_new_expense','view_expenses','auto_registration_verification','add_new_account','stock_overview','accounts_overview','send_payment_financial_reminders','download_financial_data',
                                                               'delete_finance_account','apply_finance_edits','edit_finance_accounts','accounts_history','current_accounts','update_accounts','update_existing_account','add_new_account','new_accounts_page','generate_bar_codes'):
        return redirect('/')

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Expires"] = '0'
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
def index():
    return render_template('index.html')

@app.route('/download-apk')
def download_apk():
    return send_from_directory(directory='.', path='michmanage.apk', as_attachment=True)

##########SEND MONTHLY REPORTS###########
def send_reports():
    if datetime.now().day != 1:
        return  # Only run on the first day of the month

    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    current_year = datetime.now().year
    current_month = datetime.now().month
    # Query the manager collection for all emails
    manager_emails = [doc['manager_email'] for doc in db.managers.find({}, {'manager_email': 1})]
    for email in manager_emails:
        # Query the registered collection for the username associated with the manager's email
        registered_doc = db.registered_managers.find_one({'email': email})
        company_name = registered_doc['company_name']

        previous_month_paid = datetime.now().month - 1 if datetime.now().month > 1 else 12

        old_tenant_docs = list(db.old_tenant_data.find({
            'company_name': company_name,
            'date_last_paid': {
                '$gte': datetime(current_year, previous_month_paid, 1).replace(tzinfo=utc),
                '$lt': datetime(current_year, previous_month_paid + 1, 1).replace(tzinfo=utc) if previous_month_paid < 12 else datetime(current_year + 1, 1, 1).replace(tzinfo=utc)
            }
        }))

        new_tenant_docs = list(db.tenants.find({
            'company_name': company_name,
            'date_last_paid': {
                '$gte': datetime(current_year, previous_month_paid, 1).replace(tzinfo=utc),
                '$lt': datetime(current_year, previous_month_paid + 1, 1).replace(tzinfo=utc) if previous_month_paid < 12 else datetime(current_year + 1, 1, 1).replace(tzinfo=utc)
            }
        }))
        # Append the two lists
        all_tenant_docs = old_tenant_docs + new_tenant_docs
        property_managed = list(db.property_managed.find({'company_name': company_name}))

        # Initialize a counter
        total_sections = 0
        # Iterate over the documents
        for doc in property_managed:
            # If the document has a 'sections' field and it's a list
            if 'sections' in doc and isinstance(doc['sections'], list):
                # Add the number of sections in this document to the total
                total_sections += len(doc['sections'])
        
        # Initialize dictionaries to store the counts
        monthly_payments = {}
        monthly_full_payments = {}

        # Iterate over the documents
        for doc in all_tenant_docs:
            # Get the month and payment details
            month = doc['months_paid']
            amount = doc['available_amount']
            section_value = doc['section_value']

            # Update the count of payments for this month
            if month in monthly_payments:
                monthly_payments[month] += 1
            else:
                monthly_payments[month] = 1

            # If the amount equals the section value, update the count of full payments for this month
            if amount == section_value:
                if month in monthly_full_payments:
                    monthly_full_payments[month] += 1
                else:
                    monthly_full_payments[month] = 1

        # Calculate the sum of the amount and the total number of properties
        sum_amount = sum(doc['available_amount'] for doc in all_tenant_docs)
        # Calculate the sum of the amount demanded
        sum_demanded = sum(doc['section_value'] - doc['available_amount'] for doc in all_tenant_docs)
        occupied_units = db.tenants.count_documents({'company_name': company_name})
        vacancy_rate = round(((total_sections-occupied_units)/total_sections)*100,1)

        # Calculate the previous month and its year
        if current_month == 1:
            previous_month = 12
            previous_month_year = current_year - 1
        else:
            previous_month = current_month - 1
            previous_month_year = current_year
        
        # Get the current date
        now = datetime.now()
        now_without_seconds = now.replace(second=0, microsecond=0)

        # Calculate the first day of the previous month
        first_day_previous_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)

        # Convert it to a string in the format 'Month Day, Year'
        first_day_previous_month_str = first_day_previous_month.strftime('%B %d, %Y')

        ######RESOLVED COMPLAINTS######
        start_time = datetime(current_year, previous_month_paid, 1).replace(tzinfo=utc)
        end_time = datetime(current_year, previous_month_paid + 1, 1).replace(tzinfo=utc) if previous_month_paid < 12 else datetime(current_year + 1, 1, 1).replace(tzinfo=utc)

        resolved_complaints = list(db.resolved_complaints.find({
            'resolved_time': {
                '$gte': start_time,
                '$lt': end_time
            }
        }))
        all_resolved_in_company = []
        if len(resolved_complaints)==0:
            average_days=0
            total_complaints_resolved=0
            max_days =0
            min_days =0
            most_frequent_tenant = ""
            top_5_complaints = []
        else:
            for resolved in resolved_complaints:
                # Check if the complaint was resolved in the current month and year
                if resolved['resolved_time'].month == current_month-1 and resolved['resolved_time'].year == current_year:
                    resolved_by = db.registered_managers.find_one({"username": resolved["username"]})
                    company_manager = db.managers.find_one({"manager_email": resolved_by["email"]})
                    if resolved_by["email"] == company_manager["manager_email"]:
                        all_resolved_in_company.append(resolved)
            
            # Convert the list of dictionaries to a DataFrame for easier manipulation
            df = pd.DataFrame(all_resolved_in_company)
            # Calculate the number of days taken to resolve each complaint
            df['days_taken'] = (df['resolved_time'] - df['complained_on']).dt.days
            # Calculate the average number of days taken to resolve a complaint
            average_days = round(df['days_taken'].mean(),0)
            # Calculate the total number of complaints resolved
            total_complaints_resolved = len(df)
            # Calculate the maximum and minimum number of days taken to resolve a complaint
            max_days = df['days_taken'].max()
            min_days = df['days_taken'].min()
            # Find the most frequent tenant name
            most_frequent_tenant = df['tenant_name'].value_counts().idxmax()
            # Find the top 5 complaint headings for the most frequent tenant
            top_5_complaints = df[df['tenant_name'] == most_frequent_tenant]['complaint_heading'].value_counts().nlargest(5).index.tolist()

        # Create a new Word document
        doc = Document()
        doc.add_heading(f'Property Performance Report for {company_name}', 0)

        # Add the data to the document
        doc.add_paragraph(f'Date: {now_without_seconds}')
        doc.add_heading('Executive Summary', level=2)
        doc.add_paragraph(f'This report provides an overview of the property management activities for the period from {first_day_previous_month_str} to {calendar.month_name[previous_month]} {calendar.monthrange(previous_month_year, previous_month)[1]}, {previous_month_year}. It includes key performance indicators, financial summaries, and occupancy rates.')
        
        doc.add_heading('Financial Overview', level=2)
        doc.add_paragraph(f'Total Rent Collected: {sum_amount}')
        doc.add_paragraph(f'Total Amount Demanded: {sum_demanded}')
        for month, payments in monthly_payments.items():
            doc.add_paragraph(f'Total Payments for {month}: {payments}')

        for month, full_payments in monthly_full_payments.items():
            doc.add_paragraph(f'Total Full Payments in {month}: {full_payments}')
        
        doc.add_heading('Occupancy Rates', level=2)
        doc.add_paragraph(f'Total Units: {total_sections}')
        doc.add_paragraph(f'Occupied Units: {occupied_units}')
        doc.add_paragraph(f'Vacancy Rate: {vacancy_rate}%')

        doc.add_heading('Tenant Satisfaction', level=2)
        doc.add_paragraph(f'Total Complaints Resolved: {total_complaints_resolved}')
        doc.add_paragraph(f'Tenant helped most: {most_frequent_tenant}')
        doc.add_paragraph('Top 5 complaints')
        doc.add_paragraph(f'{top_5_complaints}')
        doc.add_paragraph(f'Average Number Of Days Taken To Resolve Complaints: {average_days}')
        doc.add_paragraph(f'Maximum Number Of Days Taken To Resolve Complaints: {max_days}')
        doc.add_paragraph(f'Minimum Number Of Days Taken To Resolve Complaints: {min_days}')


        # Save the document
        report_filename = f'{email}_report.docx'
        doc.save(report_filename)

        pdf_filename = convert_docx_to_pdf(report_filename)
        password = generate_file_password()
        protected_pdf_filename = add_password_to_pdf(pdf_filename, password)

        existing_password = db.file_passwords.find_one({'username':registered_doc['username'], 'detail': 'Montly Report'})
        if existing_password:
            db.file_passwords.delete_one({'username':registered_doc['username'], 'detail': 'Montly Report'})
        db.file_passwords.insert_one({'username':registered_doc['username'], 'password': password, 'detail': 'Montly Report'})

        # Create a new Flask-Mail Message
        if send_emails is not None:
            msg = Message(
                'Mich Manage - Monthly Property Performance Report',
                sender='michpmts@gmail.com',
                recipients=[email]
            )

            # Attach the report
            with app.open_resource(protected_pdf_filename) as fp:
                msg.attach(protected_pdf_filename, "application/pdf", fp.read())

            # Set the HTML body of the email
            msg.html = f"""
            <html>
            <body>
            <p>Dear {company_name},</p>
            <p>Please find attached your monthly report.</p>
            <p>To unlock file, find your password in Passwords when you login</p>
            <p>Best Regards,</p>
            <p>Mich Manage</p>
            </body>
            </html>
            """

            # Send the email
            with app.app_context():
                thread = threading.Thread(target=send_async_email, args=[app, msg])
                thread.start()
            # Delete the report
            os.remove(report_filename)
            os.remove(pdf_filename)
            os.remove(protected_pdf_filename)
            del df
            gc.collect()

##########SEND PAYMENT REMINDERS###########
def send_payment_reminders():
    current_day_of_week = datetime.now().weekday()
    if current_day_of_week != 1:
        return
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    current_year = datetime.now().year
    month_mapping = {
        'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
        'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
        'Quarter 1': 3, 'Quarter 2': 6, 'Quarter 3': 9, 'Quarter 4': 12,
        '2024': 12, '2025': 12, '2026': 12
    }
    tenants = list(db.tenants.find())
    for tenant in tenants:
        last_payment_month = month_mapping.get(tenant['months_paid'], 0)
        last_payment_date = datetime(year=current_year, month=last_payment_month, day=1)
        next_payment_date = last_payment_date + timedelta(days=30)
        remaining_days = (next_payment_date - datetime.now()).days
        if remaining_days < 0:
            manager = db.registered_managers.find_one({'username': tenant['username']})
            manager_email = manager['email']
            #Sending reminder message
            if send_emails is not None:
                msg = Message('Rent Payment Overdue - Mich Manage', 
                sender='michpmts@gmail.com', 
                recipients=[manager_email])
                msg.html = f"""
                <html>
                <body>
                <p>Dear {manager['name']},</p>
                <p>I hope this message finds you well. I wanted to bring to your attention that the rent payment for <b style="font-size: 20px;">{tenant['tenantName']}</b> on <b style="font-size: 20px;">{tenant['propertyName']}</b> is overdue.</p>
                <p>Number of Days Overdue: <b style="font-size: 20px;">{-1*remaining_days}</b></p>
                <p>If you have any questions or concerns, feel free to reach out to us.</p>
                <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com//manager%20login%20page">Login</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                # Send the email
                with app.app_context():
                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                    thread.start()
        elif remaining_days >= 0 and remaining_days < 10:
            tenant_email = tenant['tenantEmail']
            #Sending reminder message
            if send_emails is not None:
                msg = Message('Payment Reminder - Mich Manage', 
                sender='michpmts@gmail.com', 
                recipients=[tenant_email])
                msg.html = f"""
                <html>
                <body>
                <p>Dear {tenant['tenantName']},</p>
                <p>This is a friendly reminder that your rent payment for <b style="font-size: 20px;">{tenant['months_paid']}</b> is due in <b style="font-size: 20px;">{remaining_days}</b> days.</p>
                <p>Please ensure that your payment is submitted on time to avoid any late fees or disruptions to your tenancy.</p>
                <p>If you have any questions or concerns, feel free to reach out to us.</p>
                <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                # Send the email
                with app.app_context():
                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                    thread.start()

##########SEND CONTRACT EXPIRY REMINDERS###########
def send_contract_expiry_reminders():
    current_day_of_week = datetime.now().weekday()
    if current_day_of_week != 2:
        return
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    managers = list(db.managers.find())
    for manager in managers:
        contracts = list(db.contracts.find({'company_name': manager['name']}))
        tenants = []
        if len(contracts) != 0:
            for contract in contracts:
                end_date = contract['end_date']
                now = datetime.now()
                # Calculate the remaining period from now
                remaining_seconds = int((end_date - now).total_seconds())
                remaining_minutes, remaining_seconds = divmod(remaining_seconds, 60)
                remaining_hours, remaining_minutes = divmod(remaining_minutes, 60)
                remaining_days, remaining_hours = divmod(remaining_hours, 24)
                remaining_days += 1
                if remaining_days <= 15:
                    tenants.append(contract['receiver'])

        if tenants:
            manager_email = manager['email']
            # Prepare the list of tenants as a string
            tenants_str = ', '.join(tenants)

            # Sending reminder message
            if send_emails is not None:
                msg = Message('Contract Expiry Reminder - Mich Manage', 
                sender='michpmts@gmail.com', 
                recipients=[manager_email])
                msg.html = f"""
                <html>
                <body>
                <p>Dear {manager['name']},</p>
                <p>I hope this message finds you well. This is a reminder that the contracts for the following tenants are due to expire in 15 days or less:</p>
                <p><b style="font-size: 20px;">{tenants_str}</b></p>
                <p>Please take the necessary actions to renew these contracts if needed.</p>
                <p>If you have any questions or concerns, feel free to reach out to us.</p>
                <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com//manager%20login%20page">Login</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                # Send the email
                with app.app_context():
                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                    thread.start()

###########SEND US A MESSAGE###############
@app.route('/send-message', methods=["POST"])
def send_message():
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
        
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    message = request.form.get('message')
    admin_sender = 'michpmts@gmail.com'
    #Sending inquiries
    if send_emails is not None:
        msg = Message('Inquiries - Mich Manage', 
        sender='michpmts@gmail.com', 
        recipients=[admin_sender, email])
        msg.html = f"""
        <html>
        <body>
        <p>{name} has just contacted Mich ManageS</p>
        <p>Phone number: {phone}</p>
        <p>Email: {email}</p>
        <p><b style="font-size: 20px;">Message</b></p>
        <p>{message}</p>
        <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com/">Visit Our Platform</a></b></p>
        </body>
        </html>
        """
        thread = threading.Thread(target=send_async_email, args=[app, msg])
        thread.start()
    flash('Your inquiry was sent', 'success')
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/', code=303)

@app.route('/manager login page')
def manager_login_page():
    return render_template('manager login.html')

@app.route('/documentation')
def documentation():
    return render_template('documentation.html')

@app.route('/tenant login page')
def tenant_login_page():
    return render_template('tenant login.html')

@app.route('/manager_register')
def manager_register_page():
    db, fs = get_db_and_fs()
    companies = db.managers.find({}, {"name": 1})
    company_names = [company['name'] for company in companies]
    
    cursor = db.property_managed.find({}, {'propertyName': 1, '_id': 0})
    property_data = [item['propertyName'] for item in cursor if 'propertyName' in item]
    
    resp = make_response(render_template("manager register.html", property_data=property_data, company_names=company_names))
    return resp

@app.route('/tenant_register')
def tenant_register_page():
    db, fs = get_db_and_fs()
    companies = db.managers.find({}, {"name": 1})
    company_names = [company['name'] for company in companies]
    
    cursor = db.property_managed.find({}, {'propertyName': 1, '_id': 0})
    property_data = [item['propertyName'] for item in cursor if 'propertyName' in item]
    
    resp = make_response(render_template("tenant register.html", property_data=property_data, company_names=company_names))
    return resp

@app.route('/add properties')
def add_properties():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            return render_template('add property page.html', dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/add tenants')
def add_tenants():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            is_manager = db.managers.find_one({'manager_email': company['email']})        

            if is_manager is None:
                user_query  = {'username': login_data, 'company_name': company['company_name']}
            else:
                user_query  = {'company_name': company['company_name']}

            property_data_list = list(db.property_managed.find(user_query,{'propertyName':1,'sections':1,'_id':0}))
            tenant_data_cursor = db.tenants.find(user_query,{'propertyName':1,'selected_section':1,'_id':0})
                    
            property_data_dict = {doc['propertyName']: doc['sections'] for doc in property_data_list}
            for tenant_exists in tenant_data_cursor:
                tenant_property_name = tenant_exists.get('propertyName', '').strip()
                selected_section = tenant_exists.get('selected_section', '').strip()
                # Check if the property exists in updated_property_data and the section is in the property's sections
                if tenant_property_name in property_data_dict and selected_section in property_data_dict[tenant_property_name]:
                    # Remove the section
                    property_data_dict[tenant_property_name].remove(selected_section)
                    # If there are no more sections for this property, remove the property
                    if not property_data_dict[tenant_property_name]:
                        del property_data_dict[tenant_property_name]
            return render_template('add tenants page.html', dp=dp_str, property_data=property_data_dict)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/export tenant data')
def export_tenant_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            return render_template('export tenant data.html', dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/add new stock page')
def add_new_stock_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            return render_template('add new stock.html', dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/update existing stock')
def update_existing_stock():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if not company:
                flash('Company not found', 'error')
                return redirect('/')
            
            dp_str = company.get('dp')
            items_to_update = []
            available_items = db.inventories.find({'company_name': company['company_name']})
            for item in available_items:
                item_details = {
                    'itemName': item['itemName'],
                    'available_quantity': item.get('available_quantity', ''),
                    'unitOfMeasurement': item.get('unitOfMeasurement', '')
                }
                items_to_update.append(item_details)
            
            items_to_update = sorted(items_to_update, key=lambda x: x['itemName'])

            return render_template('update existing stock.html', dp=dp_str, items_to_update=items_to_update)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/update sales page')
def update_sales_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'address': 0, 'password': 0, 'auth': 0, 'dark_mode': 0})
            if not company:
                flash('Company not found', 'error')
                return redirect('/')
            
            dp_str = company.get('dp')
            available_itemNames = []
            available_items = db.inventories.find({'company_name': company['company_name']})
            for item in available_items:
                if item.get('available_quantity', 0) > 0:
                    available_itemNames.append({
                        'itemName': item.get('itemName', ''),
                        'available_quantity': item.get('available_quantity', ''),
                        'unitOfMeasurement': item.get('unitOfMeasurement', '') 
                    })

            # Sort the available_itemNames list in alphabetical order by 'itemName'
            available_itemNames = sorted(available_itemNames, key=lambda x: x['itemName'])

            return render_template('update sales page.html', dp=dp_str, available_itemNames=available_itemNames)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/generate product bar codes page')
def generate_bar_codes():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'address': 0, 'password': 0, 'auth': 0, 'dark_mode': 0})
            if not company:
                flash('Company not found', 'error')
                return redirect('/')
            
            dp_str = company.get('dp')
            available_itemNames = []
            available_items = db.inventories.find({'company_name': company['company_name']})
            for item in available_items:
                if item.get('available_quantity', 0) > 0:
                    available_itemNames.append({
                        'itemName': item.get('itemName', '')
                    })

            # Sort the available_itemNames list in alphabetical order by 'itemName'
            available_itemNames = sorted(available_itemNames, key=lambda x: x['itemName'])

            return render_template('generate barcodes.html', dp=dp_str, available_itemNames=available_itemNames)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/update production activity')
def update_production_activity():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            
            available_itemNames = []
            available_items = db.inventories.find({'company_name': company['company_name']})
            for item in available_items:
                if item.get('available_quantity', 0) > 0:
                    available_itemNames.append({
                        'itemName': item.get('itemName', ''),  # Provide a default value
                        'available_quantity': item.get('available_quantity', ''),
                        'unitOfMeasurement': item.get('unitOfMeasurement', '')  # Provide a default value
                    })
                
            available_itemNames = sorted(available_itemNames, key=lambda x: x['itemName'])
            return render_template('update production.html', dp=dp_str, available_itemNames=available_itemNames)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/update inhouse use page')
def update_inhouse_use_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None

            available_itemNames = []
            available_items = db.inventories.find({'company_name': company['company_name']})
            for item in available_items:
                if item.get('available_quantity', 0) > 0:
                    available_itemNames.append({
                        'itemName': item.get('itemName', ''),  # Provide a default value
                        'available_quantity': item.get('available_quantity', ''),
                        'unitOfMeasurement': item.get('unitOfMeasurement', '')  # Provide a default value
                    })

            available_itemNames = sorted(available_itemNames, key=lambda x: x['itemName'])
            return render_template('update inhouse use.html', dp=dp_str, available_itemNames=available_itemNames)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/logout-admin')
def logout_admin():
    session.clear()
    return redirect('/admin', code=303)
    
@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms of service.html')

@app.route('/googlee9cdc37dc478e7a2.html')
def google_verification():
    return render_template('googlee9cdc37dc478e7a2.html')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, request.path[1:])

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

#########GENERATING RADOM NUMBERS#############
def generate_code(length=6):
    return ''.join(random.choice('0123456789') for _ in range(length))

###########REGISTRING AN ACCOUNT###############
@app.route('/register-account', methods=["POST"])
def register_account():
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
        
    # Get form data
    form_data = request.form
    # List of required fields
    required_fields = ['name', 'email', 'phone_number', 'company_name', 'username', 'address', 'password', 'confirm_password']

    # Check if any of the required fields are empty
    for field in required_fields:
        if not form_data.get(field):
            flash(f'{field.replace("_", " ").title()} is required', 'error')
            return redirect('/manager_register')
        
    name = form_data.get('name')
    email = form_data.get('email')
    phone_number = form_data.get('phone_number')
    company_name = form_data.get('company_name')
    username = form_data.get('username')
    address = form_data.get('address')
    password = form_data.get('password')
    confirm_password = form_data.get('confirm_password')

    # Check if passwords match
    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return redirect('/manager_register')

    # Check if user is a manager
    company = db.managers.find_one({'name': company_name})
    if company and email not in company.get('managers', []):  # Check if the user is a manager
        flash('Not a manager in the registered companies', 'error')
        return redirect('/manager_register')

    # Check if username or email already exists
    if db.registered_managers.find_one({'username': username}):
        flash('Username already taken', 'error')
        return redirect('/manager_register')
    if db.registered_managers.find_one({'email': email, 'company_name': company_name}):
        flash('User already registered', 'error')
        return redirect('/manager_register')

    # Generate verification code
    code = generate_code()
    is_manager = db.managers.find_one({'manager_email': email})
    if is_manager:
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        account = company['account_type']
        # Remove any empty strings from the list
        account = [atype for atype in account if atype]

        if 'Enterprise Resource Planning' in account and len(account) == 1:
            # If only 'Enterprise Resource Planning' is present
            account_type = 'Enterprise Resource Planning'
        elif 'Property Management' in account and len(account) == 1:
            # If only 'Property Management' is present
            account_type = 'Property Management'
        elif 'Accounting' in account and len(account) == 1:
            account_type = 'Accounting'

        manager = {
            'createdAt': datetime.now(),
            'code': code,
            'name': name,
            'email': email,
            'phone_number': phone_number,
            'company_name': company_name,
            'username': username,
            'address': address,
            'registered_on': datetime.now(),
            'password': hashed_password,
            'account_type': account_type
        }
    else:
        other_manager = db.other_managers.find_one({'company_name': company_name, 'manager_email':email})
        if other_manager:
            account = other_manager['account_type']

            if account == 'Property Management':
                account_type = 'Property Management'
            elif account == 'Stock Management':
                account_type = 'Stock Management'
            elif account == 'Accounting':
                account_type = 'Accounting'
        else:
            account = company['account_type']
        
            # Remove any empty strings from the list
            account = [atype for atype in account if atype]

            if 'Enterprise Resource Planning' in account and len(account) == 1:
                # If only 'Enterprise Resource Planning' is present
                account_type = 'Enterprise Resource Planning'
            elif 'Property Management' in account and len(account) == 1:
                # If only 'Property Management' is present
                account_type = 'Property Management'
            elif 'Accounting' in account and len(account) == 1:
                account_type = 'Accounting'

        manager = {
            'createdAt': datetime.now(),
            'code': code,
            'name': name,
            'email': email,
            'phone_number': phone_number,
            'company_name': company_name,
            'username': username,
            'address': address,
            'registered_on': datetime.now(),
            'password': hashed_password,
            'account_type': account_type,
            'add_properties': 'no',
            'add_tenants': 'no',
            'update_tenant': 'no',
            'edit_tenant': 'no',
            'manage_contracts': 'no',
            'add_stock': 'no',
            'update_stock': 'no',
            'update_sales': 'no',
            'inhouse': 'no',
            'view_stock_info': 'no',
            'view_revenue': 'no',
            'view_sales': 'no',
            'view_finance_dashboard': 'no',
            'add_new_finance_account': 'no',
            'update_finance_account': 'no',
            'view_finance': 'no',
            'edit_finance': 'no',
            'delete_finance': 'no'
        }

    # Delete existing verification code if exists
    db.registration_verification_codes.delete_one({'username': username})

    # Send verification email
    no_send_emails_code = 0
    if send_emails is not None:
        msg = Message('Email Verification from Mich Manage', 
                    sender='michpmts@gmail.com', 
                    recipients=[email])
        msg.html = f"""
        <html>
        <body>
        <p>Dear {name},</p>
        <p>Thank you for registering with us. Please verify your email address by entering the following code in the verification field on our website:</p>
        <p><b style="font-size: 20px;">Verification Code: {code}</b></p>
        <p>Please copy the code above and click on verify:</p>
        <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com/auto-registration-verification?email={email}&code={code}">Verify</a></b></p>
        <p>Best Regards,</p>
        <p>Mich Manage</p>
        </body>
        </html>
        """

        thread = threading.Thread(target=send_async_email, args=[app, msg])
        thread.start()
    else:
        session['no_send_emails_code'] = 'no_send_emails_code'
        no_send_emails_code = code
    # Create an index on the 'createdAt' field
    db.registration_verification_codes.create_index([("createdAt", ASCENDING)], expireAfterSeconds=43200)
    # Insert verification code into database
    db.registration_verification_codes.insert_one(manager)

    flash('Please verify your account', 'success')
    return render_template('verify_manager.html', no_send_emails_code=no_send_emails_code)

####AUTO VERIFICATION######
@app.route('/auto-registration-verification')
def auto_registration_verification():
    email = request.args.get('email')
    code = request.args.get('code')

    if email and code:
        db, fs = get_db_and_fs()
        code_exists = db.registration_verification_codes.find_one({'email': email, 'code': code})

        if code_exists:
            try:
                db.registered_managers.insert_one(code_exists)
                db.registration_verification_codes.delete_one({'email': email, 'code': code})
                flash('User registered successfully', 'success')
                return redirect('/')
            except Exception as e:
                flash('An error occurred while registering the user: ' + str(e), 'error')
        else:
            flash('Code expired or Invalid', 'error')
    
    return render_template('verify_manager.html')
  
##########VERIFYING MANAGER ACCOUNT##############
@app.route('/load-verification-page')
def load_verification_page():
    return render_template('verify_manager.html')

@app.route('/verifying-your-account', methods=["POST"])
def verifying_your_account():
    db, fs = get_db_and_fs()
    # Get form data
    email = request.form.get('email')
    code = request.form.get('code')

    # Check if code exists
    code_exists = db.registration_verification_codes.find_one({'email': email, 'code': code})
    if code_exists is None:
        flash('Check the code and try again', 'error')
        return render_template('verify_manager.html')

    # Insert manager into registered managers
    try:
        db.registered_managers.insert_one(code_exists)
        flash('User registered', 'success')
        return redirect('/')
    except Exception as e:
        flash('An error occurred while registering the user: ' + str(e), 'error')
        return render_template('verify_manager.html')


def mask_email(email):
    at_index = email.index("@")
    return email[0] + "*"*(at_index-2) + email[at_index-1:]

##########FORGOT PASSWORD##############
@app.route('/verify-username')
def verify_username():
    return render_template('forgot_password_verify_username.html')

def send_verification_email(manager_email, manager_name, code):
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    if send_emails is not None:
        msg = Message('Password Reset Verification Code - Mich Manage', 
                    sender='michpmts@gmail.com', 
                    recipients=[manager_email])
        msg.html = f"""
        <html>
        <body>
        <p>Dear {manager_name},</p>
        <p>We've received a request to reset the password associated with your account</p>
        <p>To proceed with the password reset process, please use the following verification code:</p>
        <p><b style="font-size: 20px;">Verification Code: {code}</b></p>
        <p>Please note that this code is only valid for 5 minutes from the time of this email. For security reasons, please do not share this code with anyone, including Mich Manage support staff.</p>
        <p>If you did not request this password reset, please disregard this email. Your account security is important to us.</p>
        <p>Thank you for choosing Mich Manage</p>
        <p>Best Regards,</p>
        <p>Mich Manage</p>
        </body>
        </html>
        """
        thread = threading.Thread(target=send_async_email, args=[app, msg])
        thread.start()

@app.route('/send-verification-code', methods=["POST"])
def send_verification_code():
    db, fs = get_db_and_fs()
    username = request.form.get('username')
    manager_exists = db.registered_managers.find_one({'username': username})
    if manager_exists is None:
        flash('Check username and try again', 'error')
        return redirect('/verify-username')

    code = generate_code()
    manager_email = manager_exists['email']
    masked_email = mask_email(manager_email)
    reset_requested = db.forgot_password_codes.find_one({'username': username})

    if reset_requested is None:
        manager = {'createdAt': datetime.now(), 'code': code, 'username': username, 'email': manager_email}
        send_verification_email(manager_email, manager_exists['name'], code)
        db.forgot_password_codes.create_index([("createdAt", ASCENDING)], expireAfterSeconds=300)
        db.forgot_password_codes.insert_one(manager)
        flash(f"A verification code was sent to {masked_email}", 'success')
        return render_template('forgot_password_code.html', masked_email=masked_email)
    else:
        db.forgot_password_codes.delete_one({'username': username})
        manager = {'createdAt': datetime.now(), 'code': code, 'username': username, 'email': manager_email}
        send_verification_email(manager_email, manager_exists['name'], code)
        db.forgot_password_codes.create_index([("createdAt", ASCENDING)], expireAfterSeconds=300)
        db.forgot_password_codes.insert_one(manager)
        flash(f"Another verification code was sent to {masked_email}", 'success')
        return render_template('forgot_password_code.html', masked_email=masked_email)

    
@app.route('/password-reset-verifying_user', methods=["POST"])
def password_reset_verifying_user():
    db, fs = get_db_and_fs()

    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    # Get form data
    email = request.form.get('email')
    code = request.form.get('code')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    # Check if passwords match
    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return render_template('forgot_password_code.html')

    # Check if code exists
    request_exists = db.forgot_password_codes.find_one({'email': email, 'code': code})
    if request_exists is None:
        flash('Check code or email and try again', 'error')
        return render_template('forgot_password_code.html')

    # Update password
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    try:
        db.registered_managers.update_one({'username': request_exists['username']},{'$set': {'password': hashed_password}})
        db.forgot_password_codes.delete_one({'email': email, 'code': code})
    except Exception as e:
        flash('An error occurred while resetting the password: ' + str(e), 'error')
        return render_template('forgot_password_code.html')

    # Send password reset successful email
    if send_emails is not None:
        msg = Message('Your Password Has Been Successfully Reset', 
                    sender='michpmts@gmail.com', 
                    recipients=[email])
        msg.html = f"""
        <html>
        <body>
        <p>Dear manager,</p>
        <p>We're writing to inform you that the password for your account at Mich Manage has been successfully reset.</p>
        <p>If you initiated this password reset, you can now log in to your account using your new password. Please keep this password secure and do not share it with anyone.</p>
        <p>If you did not request this password reset, or if you have any concerns about the security of your account, please contact our support team immediately.</p>
        <p>Thank you for choosing Mich Manage. If you have any further questions or need assistance, please don't hesitate to reach out.</p>
        <p>Best Regards,</p>
        <p>Mich Manage</p>
        </body>
        </html>
        """
        thread = threading.Thread(target=send_async_email, args=[app, msg])
        thread.start()

    flash('Your password was successfully reset', 'success')
    return redirect('/login')
         
#######MANAGER LOGIN##############
@app.route("/userlogin", methods=["POST"])
def userlogin():
    db, fs = get_db_and_fs()
    session.clear()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    username = request.form.get('username')
    password = request.form.get('password')

    session.permanent = False
    
    manager = db.registered_managers.find_one({'username':username},{'_id':0,'createdAt':0,'code':0,'address':0})

    if manager is None:
        flash('Not a manager', 'error')
        return redirect('/manager login page')
    else:
        if 'dark_mode' in manager:
            if manager['dark_mode'] == 'yes':
                session['dark_mode'] = 'yes'
            else:
                session['dark_mode'] = 'no'
        else:
            session['dark_mode'] = 'no'
    
        subscription = db.managers.find_one({'name': manager['company_name']},{'last_subscribed_on':1,'subscribed_days':1,'account_type':1})

        stored_password = manager['password']
        if not bcrypt.checkpw(password.encode('utf-8'), stored_password):
            flash('Wrong Password', 'error')
            return redirect('/manager login page')

        remaining_days = (subscription['last_subscribed_on'] + timedelta(days=subscription['subscribed_days']) - datetime.now()).days
        if remaining_days <= 0:
            flash('Your subscription has expired, please contact management', 'error')
            return redirect('/')

        if "auth" in manager and manager["auth"] == "yes":
            code = generate_code()
            user_auth = {"username": manager['username'], "code": code}
            db.login_auth.delete_one({"username": manager['username']})

            no_send_emails_code = 0

            #Sending verification code
            if send_emails is not None:
                msg = Message('Verify Your Identity - Mich Manage', 
                              sender='michpmts@gmail.com', 
                              recipients=[manager["email"]])
                msg.html = f"""
                <html>
                <body>
                <p>Dear Mich Manage user, please verify your identity</p>
                <p><b style="font-size: 20px;">Verification Code: {code}</b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                thread = threading.Thread(target=send_async_email, args=[app, msg])
                thread.start()
            else:
                session['no_send_emails_code'] = 'no_send_emails_code'
                no_send_emails_code = code

            db.login_auth.create_index([("createdAt", ASCENDING)], expireAfterSeconds=300)
            db.login_auth.insert_one(user_auth)
            return render_template("authentication.html", no_send_emails_code=no_send_emails_code, username=username)
        else:
            user_message1 = f"{manager['name']}"
            login_username = f"{manager['username']}"
            phone_number = f"{manager['phone_number']}"

            logged_in_data = {
                'username': username,
                'timestamp': datetime.now()
            }
            db.logged_in_data.insert_one(logged_in_data)

            session.permanent = False
            session['logged_in'] = True
            session['user_message1'] = user_message1
            session['user_message2'] = remaining_days
            session['login_username'] = login_username
            session['phone_number'] = phone_number

            fields = ['add_properties', 'add_tenants', 'update_tenant', 'edit_tenant', 'manage_contracts', 'add_stock', 'update_stock',
                      'update_sales','inhouse','view_stock_info','view_revenue','view_sales','view_finance_dashboard','add_new_finance_account',
                      'update_finance_account','view_finance','edit_finance','delete_finance']
            
            for field in fields:
                value = manager.get(field)
                if value is not None:
                    session[field] = value
            
            is_manager = db.managers.find_one({'manager_email': manager['email']})
            if is_manager:
                session['is_manager'] = 'is_manager'
                account_type = subscription['account_type']
                # Remove any empty strings from the list
                account_type = [atype for atype in account_type if atype]

                if 'Enterprise Resource Planning' in account_type and len(account_type) == 1:
                    # If only 'Enterprise Resource Planning' is present
                    session['account_type'] = 'Enterprise Resource Planning'
                    return redirect("/stock-overview")
                elif 'Property Management' in account_type and len(account_type) == 1:
                    # If only 'Property Management' is present
                    session['account_type'] = 'Property Management'
                    return redirect("/load-dashboard-page")
                elif 'Accounting' in account_type and len(account_type) == 1:
                    # If only 'Accounting' is present
                    session['account_type'] = 'Accounting'
                    return redirect("/accounts-overview")

                # elif 'Enterprise Resource Planning' in account_type and 'Property Management' in account_type:
                #     # If both are present
                #     session['account_type'] = 'all_accounts'
                #     return redirect('/all-accounts-overview')
            else:
                other_manager = db.other_managers.find_one({'company_name': manager['company_name'], 'manager_email': manager['email']})
                if other_manager:
                    account_type = other_manager['account_type']

                    if account_type == 'Stock Management':
                        session['account_type'] = 'Enterprise Resource Planning'
                        return redirect("/stock-overview")
                    elif account_type == 'Property Management':
                        # If only 'Property Management' is present
                        session['account_type'] = 'Property Management'
                        return redirect("/load-dashboard-page")
                    elif account_type == 'Accounting':
                        # If only 'Accounting' is present
                        session['account_type'] = 'Accounting'
                        return redirect("/accounts-overview")
                else:
                    account_type = subscription['account_type']
                    # Remove any empty strings from the list
                    account_type = [atype for atype in account_type if atype]

                    if 'Enterprise Resource Planning' in account_type and len(account_type) == 1:
                        # If only 'Enterprise Resource Planning' is present
                        session['account_type'] = 'Enterprise Resource Planning'
                        return redirect("/stock-overview")
                    elif 'Property Management' in account_type and len(account_type) == 1:
                        # If only 'Property Management' is present
                        session['account_type'] = 'Property Management'
                        return redirect("/load-dashboard-page")
                    elif 'Accounting' in account_type and len(account_type) == 1:
                        # If only 'Accounting' is present
                        session['account_type'] = 'Accounting'
                        return redirect("/accounts-overview")
            
#RESEND CODE
@app.route("/resend auth code/<username>")
def resend_auth_code(username):
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    code = generate_code()
    user_auth = {"username": username, "code": code}
    db.login_auth.delete_one({"username": username})

    no_send_emails_code = 0
    manager = db.registered_managers.find_one({'username':username},{'_id':0,'createdAt':0,'code':0,'address':0})
    #Sending verification code
    if send_emails is not None:
        msg = Message('Verify Your Identity - Mich Manage', 
        sender='michpmts@gmail.com', 
        recipients=[manager["email"]])
        msg.html = f"""
        <html>
        <body>
        <p>Mich Manage Personal Identification</p>
        <p><b style="font-size: 20px;">Verification Code: {code}</b></p>
        <p>Best Regards,</p>
        <p>Mich Manage</p>
        </body>
        </html>
        """
        thread = threading.Thread(target=send_async_email, args=[app, msg])
        thread.start()
    else:
        session['no_send_emails_code'] = 'no_send_emails_code'
        no_send_emails_code = code

    db.login_auth.create_index([("createdAt", ASCENDING)], expireAfterSeconds=300)
    db.login_auth.insert_one(user_auth)
    return render_template("authentication.html", no_send_emails_code=no_send_emails_code, username=username)

#USER AUTHENTICATION
@app.route("/authentication", methods=["POST"])
def authentication():
    db, fs = get_db_and_fs()
    # Get form data
    code = request.form.get("code")

    # Check if code exists
    user_auth = db.login_auth.find_one({"code": code})
    if user_auth is None:
        flash("Check code and try again", 'error')
        return render_template("authentication.html")

    # Get manager and subscription data
    manager = db.registered_managers.find_one({'username': user_auth["username"]})
    db.login_auth.delete_one({'username': user_auth["username"]})
    if manager is None:
        flash('Not a manager', 'error')
        return redirect('/')
    else:
        subscription = db.managers.find_one({'name': manager['company_name']},{'last_subscribed_on':1,'subscribed_days':1,'account_type':1})

        # Calculate remaining days
        remaining_days = (subscription['last_subscribed_on'] + timedelta(days=subscription['subscribed_days']) - datetime.now()).days

        # Insert logged in data
        logged_in_data = {
            'username': manager['username'],
            'timestamp': datetime.now()
        }
        try:
            db.logged_in_data.insert_one(logged_in_data)
        except Exception as e:
            flash('An error occurred while logging in: ' + str(e), 'error')
            return render_template("authentication.html")

        # Set session data
        session.permanent = False
        session['logged_in'] = True
        session['user_message1'] = manager['name']
        session['user_message2'] = remaining_days
        session['login_username'] = manager['username']
        session['phone_number'] = manager['phone_number']

        is_manager = db.managers.find_one({'manager_email': manager['email']})
        if is_manager:
            session['is_manager'] = 'is_manager'
            account_type = subscription['account_type']
            # Remove any empty strings from the list
            account_type = [atype for atype in account_type if atype]

            if 'Enterprise Resource Planning' in account_type and len(account_type) == 1:
                # If only 'Enterprise Resource Planning' is present
                session['account_type'] = 'Enterprise Resource Planning'
                return redirect("/stock-overview")
            elif 'Property Management' in account_type and len(account_type) == 1:
                # If only 'Property Management' is present
                session['account_type'] = 'Property Management'
                return redirect("/load-dashboard-page")
            elif 'Accounting' in account_type and len(account_type) == 1:
                # If only 'Accounting' is present
                session['account_type'] = 'Accounting'
                return redirect("/accounts-overview")
        else:
            other_manager = db.other_managers.find_one({'company_name': manager['company_name'], 'manager_email': manager['email']})
            if other_manager:
                account_type = other_manager['account_type']

                if account_type == 'Stock Management':
                    session['account_type'] = 'Enterprise Resource Planning'
                    return redirect("/stock-overview")
                elif account_type == 'Property Management':
                    # If only 'Property Management' is present
                    session['account_type'] = 'Property Management'
                    return redirect("/load-dashboard-page")
                elif account_type == 'Accounting':
                    # If only 'Accounting' is present
                    session['account_type'] = 'Accounting'
                    return redirect("/accounts-overview")
            else:
                account_type = subscription['account_type']
                # Remove any empty strings from the list
                account_type = [atype for atype in account_type if atype]

                if 'Enterprise Resource Planning' in account_type and len(account_type) == 1:
                    # If only 'Enterprise Resource Planning' is present
                    session['account_type'] = 'Enterprise Resource Planning'
                    return redirect("/stock-overview")
                elif 'Property Management' in account_type and len(account_type) == 1:
                    # If only 'Property Management' is present
                    session['account_type'] = 'Property Management'
                    return redirect("/load-dashboard-page")
                elif 'Accounting' in account_type and len(account_type) == 1:
                    # If only 'Accounting' is present
                    session['account_type'] = 'Accounting'
                    return redirect("/accounts-overview")
        
##ACCOUNT SETTING
@app.route('/account-setup-page')
def account_setup_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0})

        if 'dark_mode' in company:
            if company['dark_mode'] == 'yes':
                session['dark_mode'] = 'yes'
            else:
                session['dark_mode'] = 'no'
        else:
            session['dark_mode'] = 'no'
    
        dp = company.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        auth = company.get('auth', "no")
        dark_mode = company.get('dark_mode', "no")
        return render_template("account setting.html", dp=dp_str, auth=auth, dark_mode=dark_mode)

##ACCOUNT SETTING
@app.route('/account-setup-initiated', methods=["POST"])
def account_setup_initiated():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0})
        auth = request.form.get("switchState")
        dark_mode = request.form.get("switchState1")
        name = request.form.get("name")
        phone_number = request.form.get("phone_number")
        address = request.form.get("address")
        dp = request.files['dp'] if 'dp' in request.files else None
        secret_id = request.form.get("secret_id")

        update_fields = {}

        if auth:
            update_fields['auth'] = auth
        if secret_id:
            db.managers.update_one({'name': company['company_name']}, {'$set': {'secret_id': secret_id}})
        if dark_mode:
            update_fields['dark_mode'] = dark_mode
        if name:
            update_fields['name'] = name
        if phone_number:
            update_fields['phone_number'] = phone_number
        if address:
            update_fields['address'] = address
        if dp:
            file_content = dp.read()
            np_img = np.frombuffer(file_content, np.uint8)
            # Use OpenCV to read the image
            img = cv2.imdecode(np_img, cv2.IMREAD_UNCHANGED)
            # Encode the image as JPEG with high quality (e.g., 90)
            _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            # Convert the encoded image to a base64 string
            base64_string = base64.b64encode(buffer).decode('utf-8')
            update_fields['dp'] = base64_string

        # Update the document with the non-empty fields
        db.registered_managers.update_one({'username': login_data}, {'$set': update_fields})
        flash("Your account was successfully set", 'success')
        return redirect('/account-setup-page')
    
##ACCOUNT SETTING FOR TENANT
@app.route('/tenant-account-setup-page')
def tenant_account_setup_page():
    db, fs = get_db_and_fs()
    login_data = session.get('tenantID')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        tenant = db.tenant_user_accounts.find_one({'_id': ObjectId(login_data)})
        dp = tenant.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        auth = tenant.get('auth', "no")
        return render_template("tenant account setting.html", dp=dp_str, auth=auth)

##ACCOUNT SETTING FOR TENANT
@app.route('/tenant-account-setup-initiated', methods=["POST"])
def tenant_account_setup_initiated():
    db, fs = get_db_and_fs()
    login_data = session.get('tenantID')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        auth = request.form.get("switchState")
        dp = request.files['dp'] if 'dp' in request.files else None

        update_fields = {}

        if auth:
            update_fields['auth'] = auth
        if dp:
            file_content = dp.read()
            np_img = np.frombuffer(file_content, np.uint8)
            # Use OpenCV to read the image
            img = cv2.imdecode(np_img, cv2.IMREAD_UNCHANGED)
            # Encode the image as JPEG with high quality (e.g., 90)
            _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            # Convert the encoded image to a base64 string
            base64_string = base64.b64encode(buffer).decode('utf-8')
            update_fields['dp'] = base64_string

        # Update the document with the non-empty fields
        db.tenant_user_accounts.update_one({'_id': ObjectId(login_data)}, {'$set': update_fields})
        flash("Your account was successfully set", 'success')
        return redirect('/tenant-account-setup-page')

#######TENANT REGISTER ACCOUNT###############          
@app.route('/tenant-register-account', methods=["POST"])
def tenant_register_account():
    db, fs = get_db_and_fs()
    email = request.form.get('email')
    username = request.form.get('username')
    propertyName = request.form.get('propertyName')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return redirect('/tenant register')
    else:
        tenant_exists = db.tenant_user_accounts.find_one({'tenantEmail': email, 'propertyName': propertyName})
        user = db.tenant_user_accounts.find_one({'username': username})
        if tenant_exists is None:
            if user is None:
                tenant = db.tenants.find_one({'propertyName': propertyName, 'tenantEmail': email})
                if tenant is None:
                    flash('Entered tenant is not attached to any property', 'error')
                    return redirect('/tenant register')
                else:
                    hashed_password = bcrypt.hashpw(confirm_password.encode('utf-8'), bcrypt.gensalt())
                    tenant_data = {'account_manager': tenant['username'], 'tenantEmail': email, 'username': username, 'propertyName': propertyName,
                                'registered_on': datetime.now(), 'password': hashed_password}
                    db.tenant_user_accounts.insert_one(tenant_data)
                    flash('Tenant registered', 'success')
                    return redirect('/')
            else:
                flash('Username already taken', 'error')
                return redirect('/tenant register')
        else:
            flash('Tenant already registered', 'error')
            return redirect('/')
        
#######TENANT LOGIN##############
@app.route("/tenant-login", methods=["POST"])
def tenant_login():
    db, fs = get_db_and_fs()
    session.clear()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    username = request.form.get('username')
    password = request.form.get('password')

    tenant = db.tenant_user_accounts.find_one({'username': username})
    if tenant is None:
        flash('Not a registered tenant', 'error')
        return redirect('/tenant login page')
    else:
        stored_password = tenant['password']
        if bcrypt.checkpw(password.encode('utf-8'), stored_password):
            if "auth" in tenant and tenant["auth"] == "yes":
                code = generate_code()

                user_auth = {"username": tenant['username'], "code": code, "tenantID": str(tenant['_id']), "tenantEmail": tenant['tenantEmail'], "propertyName": tenant['propertyName']}
                db.tenant_login_auth.delete_one({"username": tenant['username']})

                no_send_emails_code = 0

                #Sending verification code
                send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

                if send_emails is not None:
                    msg = Message('Verify Your Identity - Mich Manage', 
                    sender='michpmts@gmail.com', 
                    recipients=[tenant["tenantEmail"]])
                    msg.html = f"""
                    <html>
                    <body>
                    <p>Mich Manage Personal Identification</p>
                    <p><b style="font-size: 20px;">Verification Code: {code}</b></p>
                    <p>Best Regards,</p>
                    <p>Mich Manage</p>
                    </body>
                    </html>
                    """
                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                    thread.start()
                else:
                    session['no_send_emails_code'] = 'no_send_emails_code'
                    no_send_emails_code = code

                db.tenant_login_auth.create_index([("createdAt", ASCENDING)], expireAfterSeconds=300)
                db.tenant_login_auth.insert_one(user_auth)
                return render_template("tenant authentication.html", no_send_emails_code=no_send_emails_code)
            else:
                session.permanent = False
                session['tenantID'] = str(tenant['_id'])
                session['login_username'] = str(tenant['_id'])
                session['tenantEmail'] = tenant['tenantEmail']
                session['propertyName'] = tenant['propertyName']

                logged_in_data = {
                    'username': tenant['username'],
                    'timestamp': datetime.now()
                }
                db.tenant_logged_in_data.insert_one(logged_in_data)
                return redirect('/tenant-data')
        else:
            flash('Wrong Password', 'error')
            return redirect('/tenant login page')

#USER AUTHENTICATION
@app.route("/tenant-authentication", methods=["POST"])
def tenant_authentication():
    db, fs = get_db_and_fs()
    # Get form data
    code = request.form.get("code")

    # Check if code exists
    user_auth = db.tenant_login_auth.find_one({"code": code})
    if user_auth is None:
        flash("Check code and try again", 'error')
        return render_template("tenant authentication.html")
    else:
        session.permanent = False
        session['tenantID'] = str(user_auth['tenantID'])
        session['tenantEmail'] = user_auth['tenantEmail']
        session['propertyName'] = user_auth['propertyName']

        logged_in_data = {
            'username': user_auth['username'],
            'timestamp': datetime.now()
        }
        db.tenant_logged_in_data.insert_one(logged_in_data)
        db.tenant_login_auth.delete_one({'username': user_auth["username"]})
        return redirect('/tenant-data')

@app.route('/tenant-data')
def tenant_data():
    db, fs = get_db_and_fs()
    tenantEmail = session.get('tenantEmail')
    propertyName = session.get('propertyName')
    login_data = session.get('tenantID')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant-login-page')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            current_tenant_data = list(db.tenants.find({'tenantEmail': tenantEmail, 'propertyName': propertyName}))

            tenant_acc_setting = db.tenant_user_accounts.find_one({'_id': ObjectId(login_data)})
            dp = tenant_acc_setting.get('dp')
            dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
            auth = tenant_acc_setting.get('auth', "no")

            if len(current_tenant_data) == 0:
                flash('We found no amount demanded', 'error')
                return redirect('/complaint-form')
            else:

                tenant_data = []
                month_mapping = {
                    'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                    'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
                    'Quarter 1': 3, 'Quarter 2': 6, 'Quarter 3': 9, 'Quarter 4': 12,
                    '2024': 12, '2025': 12, '2026': 12
                }
                current_month = datetime.now().strftime('%B')
                current_month_number = datetime.now().month
                # Loop through each tenant in the old tenant data
                for tenant in current_tenant_data:
                    # Extract the required information
                    name = tenant.get('tenantName')
                    phone = tenant.get('tenantPhone')
                    propertyName = tenant.get('propertyName')
                    months_paid = tenant.get('months_paid')
                    date_paid = tenant.get('date_last_paid')

                    amount_demanded = max(0, tenant['section_value'] - tenant['available_amount'])
                    last_payment_month = month_mapping.get(tenant['months_paid'], 0)
                    last_payment_date = datetime(year=tenant["date_last_paid"].year, month=last_payment_month, day=1)
                    next_payment_date = last_payment_date + timedelta(days=30)
                    remaining_days = (next_payment_date - datetime.now()).days
                    remaining_days = abs(remaining_days)

                    if amount_demanded == 0:
                        if last_payment_month < current_month_number:
                            amount_next_month = int((round((remaining_days) / 30 + 0.5, 0)) * tenant['section_value'])
                            amount_demanded = (tenant['section_value'] - tenant['available_amount']) + amount_next_month

                            tenant_data.append({
                                'name': name,
                                'phone': phone,
                                'propertyName': propertyName,
                                'amount_demanded': amount_demanded,
                                'months_paid': f"From {calendar.month_name[last_payment_month+1]} to {current_month}",
                                'date_paid': date_paid.strftime("%Y-%m-%d")
                            })

                    elif amount_demanded > 0:
                        if last_payment_month == current_month_number:
                            tenant_data.append({
                                'name': name,
                                'phone': phone,
                                'propertyName': propertyName,
                                'amount_demanded': amount_demanded,
                                'months_paid': months_paid,
                                'date_paid': date_paid.strftime("%Y-%m-%d")
                            })
                        
                        elif last_payment_month < current_month_number:
                            amount_next_month = int((round((remaining_days) / 30 + 0.5, 0)) * tenant['section_value'])
                            amount_demanded = (tenant['section_value'] - tenant['available_amount']) + amount_next_month

                            tenant_data.append({
                                'name': name,
                                'phone': phone,
                                'propertyName': propertyName,
                                'amount_demanded': amount_demanded,
                                'months_paid': f"From {months_paid} to {current_month}",
                                'date_paid': date_paid.strftime("%Y-%m-%d")
                            })
            
                return render_template('tenant monitor account.html',tenant_data=tenant_data, dp=dp_str, auth=auth)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

#############LOADING COMPLAINTS PAGE##########
@app.route('/complaint-form')
def complaint_form():
    db, fs = get_db_and_fs()
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant-login-page')
    else:
        tenant_acc_setting = db.tenant_user_accounts.find_one({'_id': ObjectId(tenant_login_data)})
        dp = tenant_acc_setting.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        auth = tenant_acc_setting.get('auth', "no")

        return render_template('complaints template.html', dp=dp_str, auth=auth)
    
##########STORE COMPLAINTS##############
@app.route('/add-complaint', methods=["POST"])
def add_complaint():
    db, fs = get_db_and_fs()
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant-login-page')
    else:
        send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
        if send_emails is not None:
            app.config['MAIL_SERVER']='smtp.sendgrid.net'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USERNAME'] = 'apikey'
            app.config['MAIL_PASSWORD'] = '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'
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USE_SSL'] = False
            mail.init_app(app)

        complaint_heading = request.form.get('complaint_heading')
        details = request.form.get('details')
        client_time_str = request.form.get('client_time')
        client_time = parse_iso_format(client_time_str)
        time_zone_offset = int(request.form.get('time_zone_offset'))
        adjusted_time = client_time + timedelta(hours=time_zone_offset)

        tenant_user = db.tenant_user_accounts.find_one({'_id': ObjectId(tenant_login_data)})
        tenant = db.tenants.find_one({'tenantEmail': tenant_user['tenantEmail'], 'propertyName': tenant_user['propertyName']})
        manager = db.registered_managers.find_one({'username': tenant['username'], 'company_name': tenant['company_name']})
        manager_email = manager['email']
        compiled_complaint = {'tenantID': ObjectId(tenant_login_data), 'tenant_name': tenant['tenantName'], 'complaint_heading': complaint_heading,
                              'details': details, 'complained_on': adjusted_time, 'status': ''}
        
        if 'complaint_image' in request.files:
            file = request.files['complaint_image']
            if file:
                file_content = file.read()
                np_img = np.frombuffer(file_content, np.uint8)
                # Use OpenCV to read the image
                img = cv2.imdecode(np_img, cv2.IMREAD_UNCHANGED)
                # Encode the image as JPEG with high quality (e.g., 90)
                _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                # Convert the encoded image to a base64 string
                base64_string = base64.b64encode(buffer).decode('utf-8')

                compiled_complaint = {'tenantID': ObjectId(tenant_login_data), 'tenant_name': tenant['tenantName'], 'complaint_heading': complaint_heading,
                              'details': details, 'image': base64_string, 'complained_on': adjusted_time, 'status': ''}
                
        db.tenant_complaints.insert_one(compiled_complaint)
        db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
        db.userNotifications.insert_one({
            'category': 'reply',
            'user': manager['username'],
            'notification': f"New complaint from {tenant['tenantName']}",
            'timestamp': datetime.utcnow()
        })
        #Sending verification code
        if send_emails is not None:
            msg = Message('New Complaint On Mich Manage', 
            sender='michpmts@gmail.com', 
            recipients=[manager_email])
            msg.html = f"""
            <html>
            <body>
            <p>Dear Manager,</p>
            <p>You have a new complaint from {tenant['tenantName']}, please login below to check complaint:</p>
            <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com//manager%20login%20page">Login</a></b></p>
            <p>Best Regards,</p>
            <p>Mich Manage</p>
            </body>
            </html>
            """
            thread = threading.Thread(target=send_async_email, args=[app, msg])
            thread.start()

        flash('Complaint submitted, we will get back to you', 'success')
        return redirect('/complaint-form')
    
############SHOW MY COMPLAINTS######################
@app.route('/my-complaints')
def my_complaints():
    db, fs = get_db_and_fs()
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant-login-page')
    else:
        tenant_acc_setting = db.tenant_user_accounts.find_one({'_id': ObjectId(tenant_login_data)})
        my_complaints = db.tenant_complaints.find({'tenantID': ObjectId(tenant_login_data)})
        if len(list(db.tenant_complaints.find({'tenantID': ObjectId(tenant_login_data)}))) == 0:
            flash('You have not placed any complaint(s) yet!', 'error')
            return redirect('/complaint-form')
        else:
            complaints = []
            for complaint in my_complaints:
                replies = list(db.tenant_complaints_replies.find({'complaintID': complaint['_id']}))
                if len(replies) == 0:
                    replies = [{'Reply': 'No reply', 'who': 'N/A', 'reply_date': 'N/A'}]
                else:
                    for reply in replies:
                        if reply['who'] != tenant_acc_setting['username']:
                            db.tenant_complaints_replies.update_one({'_id': reply['_id']}, {'$set': {'status': 'seen'}})
                    # Sort replies by date, most recent first
                    replies = sorted(replies, key=lambda r: r['reply_date'], reverse=True)
                complaint_copy = complaint.copy()  # create a copy of complaint to avoid overwriting
                complaint_copy['_id'] = str(complaint['_id'])
                complaint_copy['tenantID'] = str(complaint['tenantID'])
                # Prepare replies with conditional status field
                if len(replies) == 1 and replies[0]['Reply'] == 'No reply':
                    complaint_copy['replies'] = [{'Reply': replies[0]['Reply'], 'who': replies[0]['who'], 'reply_date': replies[0]['reply_date'], 'status': ''}]
                else:
                    complaint_copy['replies'] = [{'Reply': reply['Reply'], 'who': reply['who'], 'other': tenant_acc_setting['username'], 'status': reply.get('status', ''), 'reply_date': reply['reply_date'].strftime('%Y-%m-%d %H:%M') if reply['reply_date'] != 'N/A' else 'N/A'} for reply in replies]
                complaints.append(complaint_copy)
            # Sort complaints by date, most recent first
            complaints = sorted(complaints, key=lambda c: c['complained_on'], reverse=True)
            # Remove duplicates
            complaints = list({v['_id']: v for v in complaints}.values())

            dp = tenant_acc_setting.get('dp')
            dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
            auth = tenant_acc_setting.get('auth', "no")

            return render_template('my complaints.html',complaints=complaints, dp=dp_str, auth=auth)

############REPLY TO COMPLAINTS BY TENANT###########
@app.route('/tenant-reply-to-complaint', methods=['POST'])
def tenant_reply_complaint():
    db, fs = get_db_and_fs()
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
        if send_emails is not None:
            app.config['MAIL_SERVER']='smtp.sendgrid.net'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USERNAME'] = 'apikey'
            app.config['MAIL_PASSWORD'] = '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'
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USE_SSL'] = False
            mail.init_app(app)

        tenant_name = db.tenant_user_accounts.find_one({'_id': ObjectId(tenant_login_data)})
        login_data = tenant_name['username']
        complaint_id = request.form.get('complaint_id')
        Reply = request.form.get('Reply_' + str(complaint_id))
        client_time_str = request.form.get('client_time')
        client_time = parse_iso_format(client_time_str)
        time_zone_offset = int(request.form.get('time_zone_offset'))
        adjusted_time = client_time + timedelta(hours=time_zone_offset)
        db.tenant_complaints_replies.insert_one({'complaintID': ObjectId(complaint_id),
                                                    'Reply': Reply,
                                                    'who': login_data,
                                                    'reply_date': adjusted_time,
                                                    'status': ''})
        tenant_managed = db.tenants.find_one({'tenantEmail': tenant_name['tenantEmail'], 'propertyName': tenant_name['propertyName']})
        manager = db.registered_managers.find_one({'username': tenant_managed['username'], 'company_name': tenant_managed['company_name']})
        manager_username = manager['username']
        db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
        db.userNotifications.insert_one({
            'category': 'reply',
            'user': manager_username,
            'notification': f"New reply from {tenant_managed['tenantName']}",
            'timestamp': datetime.utcnow()
        })
        manager_email = manager['email']

        if send_emails is not None:
            msg = Message('New Reply From Tenant', 
            sender='michpmts@gmail.com', 
            recipients=[manager_email])
            msg.html = f"""
            <html>
            <body>
            <p>Dear Manager,</p>
            <p>You have a new reply from {tenant_managed['tenantName']}, please login below to check reply:</p>
            <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com//manager%20login%20page">Login</a></b></p>
            <p>Best Regards,</p>
            <p>Mich Manage</p>
            </body>
            </html>
            """
            thread = threading.Thread(target=send_async_email, args=[app, msg])
            thread.start()
        
        return redirect('/my-complaints')
  
############LOAD COMPLAINTS TO MANAGER######################
@app.route('/resolve-complaints')
def resolve_complaints():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            is_manager = db.managers.find_one({'manager_email': company['email']})
            ####CHECK IS LOGEDIN MANAGER HAS FULL RIGHTS
            if is_manager is None:
                property_assigned = db.registered_managers.find({'username': login_data})
                property_assigned_dict = {property for doc in property_assigned if 'properties' in doc for property in doc['properties']}
                if not property_assigned_dict:
                    flash('You are not managing any property!', 'error')
                    return redirect('/load-dashboard-page')
                else:
                    tenant_accounts = []
                    for property in property_assigned_dict:
                        tenant_account = list(db.tenant_user_accounts.find({'propertyName': property}))
                        tenant_accounts.extend(tenant_account)
            else:
                user_querry = {'company_name': company['company_name']}
                properties = db.property_managed.find(user_querry)
                if db.property_managed.count_documents(user_querry)==0:
                    flash('You are not managing any property!', 'error')
                    return redirect('/load-dashboard-page')
                else:
                    tenant_accounts = []
                    for property in properties:
                        tenant_account = list(db.tenant_user_accounts.find({'propertyName': property['propertyName']}))
                        tenant_accounts.extend(tenant_account)

            complaints = []
            resolved_complaints=[]
            for tenant in tenant_accounts:
                tenant_id = tenant['_id']
                found_complaints = db.tenant_complaints.find({'tenantID': tenant_id})
                found_resolved_complaints = db.resolved_complaints.find({'tenantID': tenant_id})
                for found_resolved in found_resolved_complaints:
                    resolved_complaints.append(found_resolved)
                for complaint in found_complaints:
                    replies = list(db.tenant_complaints_replies.find({'complaintID': complaint['_id']}))
                    db.tenant_complaints.update_one({'_id': complaint['_id']}, {'$set': {'status': 'seen'}})
                    if len(replies) == 0:
                        replies = [{'Reply': 'No reply', 'who': 'N/A', 'reply_date': 'N/A'}]
                    else:
                        for reply in replies:
                            if reply['who'] != 'Manager':
                                db.tenant_complaints_replies.update_one({'_id': reply['_id']}, {'$set': {'status': 'seen'}})
                        # Sort replies by date, most recent first
                        replies = sorted(replies, key=lambda r: r['reply_date'], reverse=True)
                    complaint_copy = complaint.copy()  # create a copy of complaint to avoid overwriting
                    complaint_copy['_id'] = str(complaint['_id'])
                    complaint_copy['tenantID'] = str(complaint['tenantID'])
                    # Prepare replies with conditional status field
                    if len(replies) == 1 and replies[0]['Reply'] == 'No reply':
                        complaint_copy['replies'] = [{'Reply': replies[0]['Reply'], 'who': replies[0]['who'], 'reply_date': replies[0]['reply_date'], 'status': ''}]
                    else:
                        complaint_copy['replies'] = [{'Reply': reply['Reply'], 'who': reply['who'], 'other': 'Manager', 'status': reply.get('status', ''), 'reply_date': reply['reply_date'].strftime('%Y-%m-%d %H:%M') if reply['reply_date'] != 'N/A' else 'N/A'} for reply in replies]
                    complaints.append(complaint_copy)
            # Sort complaints by date, most recent first
            complaints = sorted(complaints, key=lambda c: c['complained_on'], reverse=True)
            # Remove duplicates
            complaints = list({v['_id']: v for v in complaints}.values())
            return render_template('resolve complaints.html',complaints=complaints,resolved_complaints=resolved_complaints, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
            
############RESOLVE COMPLAINTS BY MANAGER###########
@app.route('/update-complaint', methods=['POST'])
def update_complaint():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            # manager = db.registered_managers.find_one({'username': login_data})
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
            if send_emails is not None:
                app.config['MAIL_SERVER']='smtp.sendgrid.net'
                app.config['MAIL_PORT'] = 587
                app.config['MAIL_USERNAME'] = 'apikey'
                app.config['MAIL_PASSWORD'] = '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'
                app.config['MAIL_USE_TLS'] = True
                app.config['MAIL_USE_SSL'] = False
                mail.init_app(app)

            complaint_id = request.form.get('complaint_id')
            Reply = request.form.get('Reply_' + str(complaint_id))
            client_time_str = request.form.get('client_time')
            client_time = parse_iso_format(client_time_str)
            time_zone_offset = int(request.form.get('time_zone_offset'))
            adjusted_time = client_time + timedelta(hours=time_zone_offset)
            db.tenant_complaints_replies.insert_one({'complaintID': ObjectId(complaint_id),
                                                        'Reply': Reply,
                                                        'who': 'Manager',
                                                        'reply_date': adjusted_time,
                                                        'status': ''})
            
            tenant_complaint_id = db.tenant_complaints.find_one({'_id': ObjectId(complaint_id)})
            tenant_object_id = db.tenant_user_accounts.find_one({'_id': tenant_complaint_id['tenantID']})
            db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
            db.userNotifications.insert_one({
                'category': 'reply',
                'user': tenant_complaint_id['tenantID'],
                'notification': f"New reply from manager {login_data}",
                'timestamp': datetime.utcnow()
            })
            tenant_email = tenant_object_id['tenantEmail']

            if send_emails is not None:
                msg = Message('New Reply From Property Manager', 
                sender='michpmts@gmail.com', 
                recipients=[tenant_email])
                msg.html = f"""
                <html>
                <body>
                <p>Dear tenant,</p>
                <p>You have a new reply from manager of {tenant_object_id['propertyName']}, please login below to check reply:</p>
                <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                thread = threading.Thread(target=send_async_email, args=[app, msg])
                thread.start()

            return redirect('/resolve-complaints')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
        
##########RESOLVING COMPLAINTS AFTER SOLVING THEM#########
@app.route('/resolved-complaints/<complaint_id>', methods=["GET", "POST"])
def resolved_complaints(complaint_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
            if send_emails is not None:
                app.config['MAIL_SERVER']='smtp.sendgrid.net'
                app.config['MAIL_PORT'] = 587
                app.config['MAIL_USERNAME'] = 'apikey'
                app.config['MAIL_PASSWORD'] = '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'
                app.config['MAIL_USE_TLS'] = True
                app.config['MAIL_USE_SSL'] = False
                mail.init_app(app)
                
            resolved_complaint = db.tenant_complaints.find_one({'_id': ObjectId(complaint_id)})
            resolved_complaint['resolved_time'] = datetime.now()
            resolved_complaint['username'] = login_data
            db.resolved_complaints.insert_one(resolved_complaint)
            db.tenant_complaints.delete_one({'_id': ObjectId(complaint_id)})

            tenant = db.tenant_user_accounts.find_one({"_id": resolved_complaint["tenantID"]})
            tenant_email = tenant["tenantEmail"]
            manager = db.registered_managers.find_one({"username": login_data})
            manager_email = manager["email"]
            resolved_time = resolved_complaint["resolved_time"].replace(second=0, microsecond=0)
            complained_on = resolved_complaint["complained_on"].replace(second=0, microsecond=0)
            days_taken = ((resolved_time - complained_on).days) + 1

            db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
            db.userNotifications.insert_one({
                'category': 'reply',
                'user': resolved_complaint["tenantID"],
                'notification': f"Complaint resolved by manager {login_data}",
                'timestamp': datetime.utcnow()
            })

            if send_emails is not None:
                msg = Message('Complaint was resolved', 
                sender='michpmts@gmail.com', 
                recipients=[tenant_email, manager_email])
                msg.html = f"""
                <html>
                <body>
                <p>Dear user,</p>
                <p>The following complaint was resolved by {manager['name']}</p>
                <p>Heading: {resolved_complaint["complaint_heading"]}</p>
                <p>Details: {resolved_complaint["details"]}</p>
                <p>Date filed: {complained_on}</p>
                <p>Date resolved: {resolved_time}</p>
                <p>Time taken to resolve: {days_taken} days</p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                thread = threading.Thread(target=send_async_email, args=[app, msg])
                thread.start()

            flash('Complaint was resolved', 'success')
            return redirect('/resolve-complaints')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
       
#############ADD PROPERTY####################
@app.route('/add-property', methods=["POST"])
def add_property():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            propertyName = request.form.get('propertyName', '').strip()
            type = request.form.get('type')
            sections = request.form.get('sections').split(',')
            property_value = request.form.get('property_value')
            property_value = int(property_value)
            late_payment_day = request.form.get('late_payment_day')
            late_payment_day = int(late_payment_day)
            currency = request.form.get('currency')
            address = request.form.get('address')
            city = request.form.get('city')
            state = request.form.get('state')
            parish = request.form.get('parish')
            owner_name = request.form.get('owner_name')
            owner_email = request.form.get('owner_email')
            owner_phone = request.form.get('owner_phone')
            owner_residence = request.form.get('owner_residence')

            property_exists = db.property_managed.find_one({'propertyName': propertyName})
            manager = db.registered_managers.find_one({'username':login_data})
            is_manager = db.managers.find_one({'manager_email': manager['email']})
            properties = db.property_managed.count_documents({'company_name': manager['company_name']})
            if is_manager['amount_per_month'] == 100000 and properties>=20:
                flash('Maximum number of properties is reached', 'error')
                return redirect('/load-dashboard-page')
            elif is_manager['amount_per_month'] == 150000 and properties>=30:
                flash('Maximum number of properties is reached', 'error')
                return redirect('/load-dashboard-page')
            elif is_manager['amount_per_month'] == 200000 and properties>=50:
                flash('Maximum number of properties is reached', 'error')
                return redirect('/load-dashboard-page')
            else:
                if property_exists is None:
                    property_details = {'username': login_data,
                                        'propertyName': propertyName,
                                        'company_name': manager['company_name'],
                                        'type': type,
                                        'sections': sections,
                                        'property_value': property_value,
                                        'late_payment_day': late_payment_day,
                                        'currency': currency,
                                        'address': address, 'city': city,
                                        'state': state, 'parish': parish,
                                        'owner_name': owner_name,
                                        'owner_email': owner_email,
                                        'owner_phone': owner_phone,
                                        'owner_residence': owner_residence}
                    db.property_managed.insert_one(property_details)
                    db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add property data', 'propertyName':propertyName, 'timestamp': datetime.now()})
                    flash('Property was added successfully', 'success')
                    return redirect('/load-dashboard-page')
                else:
                    flash('This Property is in the database', 'error')
                    return redirect('/load-dashboard-page')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

########LOAD TENANT INFO################
@app.route('/update-tenant-info')
def update_tenant_info():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    current_year = datetime.now().year
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            dp_str = None

            is_manager = db.managers.find_one({'manager_email': company['email']}) is not None

            if not is_manager:
                property_assigned = db.registered_managers.find({'username': login_data})
                property_assigned_dict = {property for doc in property_assigned if 'properties' in doc for property in doc['properties']}
                tenants = []
                for property in property_assigned_dict:
                    properties_query = {"propertyName": property}
                    tenants_data = list(db.tenants.find(properties_query))
                    if tenants_data:
                        for tenant in tenants_data:
                            tenants.append(tenant)
                property_managed = []
                for property in property_assigned_dict:
                    properties_query = {"propertyName": property}
                    property_data = list(db.property_managed.find(properties_query))
                    if property_data:
                        for property in property_data:
                            property_managed.append(property)
            else:
                tenants_query = {'company_name': company['company_name']}
                property_query = {'company_name': company['company_name']}
                tenants = list(db.tenants.find(tenants_query))
                property_managed = list(db.property_managed.find(property_query))
            
            if not tenants:
                flash('No tenant data found', 'error')
                return redirect('/load-dashboard-page')
            
            tenant_data = []
            month_mapping = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
                'Quarter 1': 3, 'Quarter 2': 6, 'Quarter 3': 9, 'Quarter 4': 12,
                '2024': 12, '2025': 12, '2026': 12
            }
            for tenant in tenants:
                for property in property_managed:
                    if tenant['propertyName'] == property['propertyName']:
                        last_payment_month = month_mapping.get(tenant['months_paid'], 0)
                        last_payment_date = datetime(year=tenant["date_last_paid"].year, month=last_payment_month, day=1)
                        next_payment_date = last_payment_date + timedelta(days=30)
                        remaining_days = (next_payment_date - datetime.now()).days
                        percentage_paid = round((tenant['available_amount'] / tenant['section_value']) * 100, 1)
                        date_last_paid = tenant['date_last_paid'].strftime('%Y-%m-%d')
                        amount_demanded = max(0, tenant['section_value'] - tenant['available_amount'])
                        if remaining_days < 0:
                            overdue = True
                            remaining_days = abs(remaining_days)
                            amount_next_month = int((round((remaining_days) / 30 + 0.5, 0)) * tenant['section_value'])
                            amount_demanded = (tenant['section_value'] - tenant['available_amount']) + amount_next_month                   
                        else:
                            overdue = False

                        if remaining_days < 7:
                            time_unit = 'day(s)'
                        elif remaining_days < 30:
                            remaining_days = round(remaining_days / 7)
                            time_unit = 'week(s)'
                        elif remaining_days < 365:
                            remaining_days = round(remaining_days / 30)
                            time_unit = 'month(s)'
                        else:
                            remaining_days = round(remaining_days / 365)
                            time_unit = 'year(s)'

                        overdue_status = 'overdue' if overdue else 'due in'
                        tenant_data.append((tenant['tenantName'], tenant['tenantPhone'], tenant['tenantEmail'],
                                            tenant['propertyName'], tenant['selected_section'], tenant['payment_type'],
                                            tenant['amount'], tenant['payment_mode'], tenant['months_paid'], 
                                            tenant['available_amount'], amount_demanded, tenant['payment_completion'], 
                                            tenant['section_value'], percentage_paid, tenant['currency'], 
                                            date_last_paid, remaining_days, time_unit, overdue_status))
            
            if 'dp' in company:
                dp = base64.b64decode(company['dp'])
                dp_str = base64.b64encode(dp).decode()
            
            return render_template('tenant information.html', tenant_data=tenant_data, dp=dp_str, current_year=current_year)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/get_receipt', methods=['GET'])
def get_receipt():
    db, fs = get_db_and_fs()
    tenant_email = request.args.get('tenantEmail')
    property_name = request.args.get('propertyName')
    selected_section = request.args.get('selected_section')
    months_paid = request.args.get('months_paid')
    year = request.args.get('year')
    year = int(year)

    receipt_data = db.tenants.find_one({
        'tenantEmail': tenant_email,
        'propertyName': property_name,
        'selected_section': selected_section,
        'months_paid': months_paid,
        'year': year
    }, {'payment_receipt': 1, '_id': 0})

    if receipt_data is None:
        old_receipt_data = db.old_tenant_data.find_one({
            'tenantEmail': tenant_email,
            'propertyName': property_name,
            'selected_section': selected_section,
            'months_paid': months_paid,
            'year': year
        }, {'payment_receipt': 1, '_id': 0})
        if old_receipt_data:
            # Convert the base64 string back to bytes
            payment_receipt = base64.b64decode(old_receipt_data['payment_receipt'])

            # Create a BytesIO object from the PDF data
            pdf_io = io.BytesIO(payment_receipt)

            # Create the file name
            file_name = f"{property_name}_{selected_section}_{months_paid}_{year}.pdf"

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
        file_name = f"{property_name}_{selected_section}_{months_paid}_{year}.pdf"

        # Create a custom response
        response = make_response(pdf_io.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={file_name}'

        return response
    
@app.route('/get_financial_receipt', methods=['GET'])
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

###########UPDATE TENANT INFO################
@app.route('/update', methods=['POST'])
def update():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    current_year = datetime.now().year
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

            new_amount_from_form = request.form.get('amount_paid')
            payment_mode = request.form.get('payment_mode')
            months_paid = request.form.get('months_paid')
            date = request.form.get('date')
            tenantEmail = request.form.get('tenantEmail')
            propertyName = request.form.get('propertyName')
            selected_section = request.form.get('selected_section')
            new_amount = int(new_amount_from_form)
            # Convert the date string to a datetime object
            date = datetime.strptime(date, '%Y-%m-%d')
            current_year = datetime.now().year

            section_tenant = db.tenants.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName, 'selected_section': selected_section})
            section_value = section_tenant['section_value']
            payment_status = ""

            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None

            old_data = db.tenants.find_one({'tenantEmail': tenantEmail, 'propertyName':propertyName, 'selected_section': selected_section})
            query = {'company_name': company['company_name']}
                    
            old_amount = old_data['available_amount']
            old_date = old_data['date_last_paid']
            late_payment_day = (db.property_managed.find_one({'propertyName': propertyName}))['late_payment_day']
            if date.day > late_payment_day:
                payment_status = "Late"
            else:
                payment_status = "Early"
            payment_completion = ''
            month_mapping = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
                'Quarter 1': 3, 'Quarter 2': 6, 'Quarter 3': 9, 'Quarter 4': 12,
                '2024': 12, '2025': 12, '2026': 12
            }

            available_amount = 0
            field_month = month_mapping.get(old_data['months_paid'], 0)
            months_paid_selected = month_mapping.get(months_paid, 0)
            if field_month != months_paid_selected:
                # Define the start and end of the current year
                start_date = datetime(date.year, 1, 1)
                end_date = datetime(date.year + 1, 1, 1)

                old_data2 = db.old_tenant_data.find_one({'tenantEmail': tenantEmail, 'propertyName':propertyName, 'selected_section': selected_section, 'months_paid': months_paid, 'date_last_paid': {'$gte': start_date,'$lt': end_date}})

                if old_data2:
                    flash('Selected period was fully paid', 'error')
                else:
                    if old_data['available_amount'] < section_value:
                        flash('First fully update current/previous period', 'error')
                    else:
                        available_amount = new_amount

                        balance = section_value - available_amount
                        # Create a payment receipt PDF file
                        buffer = BytesIO()
                        doc = SimpleDocTemplate(buffer, pagesize=letter)

                        # QR Code Generation
                        url = f'https://michmanagement.onrender.com//get_receipt?tenantEmail={tenantEmail}&propertyName={propertyName}&selected_section={selected_section}&months_paid={months_paid}&year={date.year}'
                        qr = qrcode.QRCode(
                            version=1,
                            error_correction=qrcode.constants.ERROR_CORRECT_L,
                            box_size=3,
                            border=4,
                        )
                        qr.add_data(url)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        login_data = session.get('login_username')
                        img.save(f'payment_receipt_qr_{login_data}.png')

                        # Create the receipt details
                        data = [
                            ['Rent Payment Receipt - ' + company['company_name'], ''],
                            ['Receipt for:', section_tenant['tenantName']],
                            ['Property Name:', propertyName],
                            ['Payment Type:', section_tenant['payment_type']],
                            ['Amount Paid:', f"{section_tenant['currency']} {new_amount}"],
                            ['Payment Mode:', payment_mode],
                            ['Month Paid for:', months_paid],
                            ['Date Paid:', date.strftime('%Y-%m-%d')],
                            ['Balance:', f"{section_tenant['currency']} {balance}"],
                            ['Prepared by:', company['name']]
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
                        qr_code_img = f'payment_receipt_qr_{login_data}.png'
                        qr_code = Image(qr_code_img)
                        qr_code.hAlign = 'CENTER'

                        # Add the QR code image to the elements list before building the PDF
                        elements = [table, qr_code]
                        doc.build(elements)

                        # Get the PDF data and encode it as base64
                        pdf_data = buffer.getvalue()
                        buffer.close()
                        payment_receipt_base64 = base64.b64encode(pdf_data).decode()

                        # Delete the QR code image file
                        os.remove(f'payment_receipt_qr_{login_data}.png')
                        
                        new_data = {
                            'username': login_data,
                            'company_name': company['company_name'],
                            'tenantName': old_data['tenantName'],
                            'tenantEmail': tenantEmail,
                            'tenantPhone': old_data['tenantPhone'],
                            'propertyName': propertyName,
                            'selected_section': selected_section,
                            'section_value': old_data['section_value'],
                            'payment_type': old_data['payment_type'],
                            'amount': new_amount,
                            'payment_mode': payment_mode,
                            'months_paid': months_paid,
                            'year': date.year,
                            'available_amount': available_amount,
                            'payment_completion': payment_completion,
                            'currency': old_data['currency'],
                            'date_last_paid': date,
                            'payment_status': payment_status,
                            'status': 'updated',
                            'payment_receipt': payment_receipt_base64
                        }
                        if available_amount < section_value:
                            payment_completion = 'Partial'
                            new_data['payment_completion'] = payment_completion
                            if date.year == old_date.year:
                                if field_month > months_paid_selected:
                                    db.old_tenant_data.insert_one(new_data)
                                    tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                                    if tenant_user:
                                        db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                        db.userNotifications.insert_one({
                                            'category': 'payment',
                                            'user': tenant_user["_id"],
                                            'notification': f"New payment recorded by manager {login_data}",
                                            'timestamp': datetime.utcnow()
                                        })
                                    # Create the email message
                                    if send_emails is not None:
                                        msg = Message('Rent Payment Receipt-Mich Manage', 
                                                    sender='michpmts@gmail.com', 
                                                    recipients=[tenantEmail])
                                        msg.html = f"""
                                        <html>
                                        <body>
                                        <p>Dear {section_tenant['tenantName']},</p>
                                        <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                        <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                        <p>Best Regards,</p>
                                        <p>Mich Manage</p>
                                        </body>
                                        </html>
                                        """

                                        # Attach the PDF receipt to the email
                                        msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                        # Send the email
                                        thread = threading.Thread(target=send_async_email, args=[app, msg])
                                        thread.start()
                                    db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                    flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                                else:
                                    db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
                                    tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                                    if tenant_user:
                                        db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                        db.userNotifications.insert_one({
                                            'category': 'payment',
                                            'user': tenant_user["_id"],
                                            'notification': f"New payment recorded by manager {login_data}",
                                            'timestamp': datetime.utcnow()
                                        })
                                    # Create the email message
                                    if send_emails is not None:
                                        msg = Message('Rent Payment Receipt-Mich Manage', 
                                                    sender='michpmts@gmail.com', 
                                                    recipients=[tenantEmail])
                                        msg.html = f"""
                                        <html>
                                        <body>
                                        <p>Dear {section_tenant['tenantName']},</p>
                                        <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                        <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                        <p>Best Regards,</p>
                                        <p>Mich Manage</p>
                                        </body>
                                        </html>
                                        """

                                        # Attach the PDF receipt to the email
                                        msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                        # Send the email
                                        thread = threading.Thread(target=send_async_email, args=[app, msg])
                                        thread.start()

                                    if '_id' in old_data:
                                        del old_data['_id']
                                    db.old_tenant_data.insert_one(old_data)
                                    db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                    flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                            elif date.year < old_date.year:
                                db.old_tenant_data.insert_one(new_data)
                                tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                                if tenant_user:
                                    db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                    db.userNotifications.insert_one({
                                        'category': 'payment',
                                        'user': tenant_user["_id"],
                                        'notification': f"New payment recorded by manager {login_data}",
                                        'timestamp': datetime.utcnow()
                                    })
                                # Create the email message
                                if send_emails is not None:
                                    msg = Message('Rent Payment Receipt-Mich Manage', 
                                                sender='michpmts@gmail.com', 
                                                recipients=[tenantEmail])
                                    msg.html = f"""
                                    <html>
                                    <body>
                                    <p>Dear {section_tenant['tenantName']},</p>
                                    <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                    <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                    <p>Best Regards,</p>
                                    <p>Mich Manage</p>
                                    </body>
                                    </html>
                                    """

                                    # Attach the PDF receipt to the email
                                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                    # Send the email
                                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                                    thread.start()
                                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                            else:
                                db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
                                tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                                if tenant_user:
                                    db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                    db.userNotifications.insert_one({
                                        'category': 'payment',
                                        'user': tenant_user["_id"],
                                        'notification': f"New payment recorded by manager {login_data}",
                                        'timestamp': datetime.utcnow()
                                    })
                                # Create the email message
                                if send_emails is not None:
                                    msg = Message('Rent Payment Receipt-Mich Manage', 
                                                sender='michpmts@gmail.com', 
                                                recipients=[tenantEmail])
                                    msg.html = f"""
                                    <html>
                                    <body>
                                    <p>Dear {section_tenant['tenantName']},</p>
                                    <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                    <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                    <p>Best Regards,</p>
                                    <p>Mich Manage</p>
                                    </body>
                                    </html>
                                    """

                                    # Attach the PDF receipt to the email
                                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                    # Send the email
                                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                                    thread.start()
                                if '_id' in old_data:
                                    del old_data['_id']
                                db.old_tenant_data.insert_one(old_data)
                                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                        elif available_amount > section_value:  
                            flash("Enter amount that does not exceed section value", 'error')

                        else:
                            payment_completion = 'Full'
                            new_data['payment_completion'] = payment_completion

                            if date.year == old_date.year:
                                if field_month > months_paid_selected:
                                    db.old_tenant_data.insert_one(new_data)
                                    tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                                    if tenant_user:
                                        db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                        db.userNotifications.insert_one({
                                            'category': 'payment',
                                            'user': tenant_user["_id"],
                                            'notification': f"New payment recorded by manager {login_data}",
                                            'timestamp': datetime.utcnow()
                                        })
                                    # Create the email message
                                    if send_emails is not None:
                                        msg = Message('Rent Payment Receipt-Mich Manage', 
                                                    sender='michpmts@gmail.com', 
                                                    recipients=[tenantEmail])
                                        msg.html = f"""
                                        <html>
                                        <body>
                                        <p>Dear {section_tenant['tenantName']},</p>
                                        <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                        <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                        <p>Best Regards,</p>
                                        <p>Mich Manage</p>
                                        </body>
                                        </html>
                                        """

                                        # Attach the PDF receipt to the email
                                        msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                        # Send the email
                                        thread = threading.Thread(target=send_async_email, args=[app, msg])
                                        thread.start()
                                    db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                    flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                                else:
                                    db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
                                    tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                                    if tenant_user:
                                        db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                        db.userNotifications.insert_one({
                                            'category': 'payment',
                                            'user': tenant_user["_id"],
                                            'notification': f"New payment recorded by manager {login_data}",
                                            'timestamp': datetime.utcnow()
                                        })
                                    # Create the email message
                                    if send_emails is not None:
                                        msg = Message('Rent Payment Receipt-Mich Manage', 
                                                    sender='michpmts@gmail.com', 
                                                    recipients=[tenantEmail])
                                        msg.html = f"""
                                        <html>
                                        <body>
                                        <p>Dear {section_tenant['tenantName']},</p>
                                        <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                        <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                        <p>Best Regards,</p>
                                        <p>Mich Manage</p>
                                        </body>
                                        </html>
                                        """

                                        # Attach the PDF receipt to the email
                                        msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                        # Send the email
                                        thread = threading.Thread(target=send_async_email, args=[app, msg])
                                        thread.start()
                                    if '_id' in old_data:
                                        del old_data['_id']
                                    db.old_tenant_data.insert_one(old_data)
                                    db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                    flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                            elif date.year < old_date.year:
                                db.old_tenant_data.insert_one(new_data)
                                tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                                if tenant_user:
                                    db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                    db.userNotifications.insert_one({
                                        'category': 'payment',
                                        'user': tenant_user["_id"],
                                        'notification': f"New payment recorded by manager {login_data}",
                                        'timestamp': datetime.utcnow()
                                    })
                                # Create the email message
                                if send_emails is not None:
                                    msg = Message('Rent Payment Receipt-Mich Manage', 
                                                sender='michpmts@gmail.com', 
                                                recipients=[tenantEmail])
                                    msg.html = f"""
                                    <html>
                                    <body>
                                    <p>Dear {section_tenant['tenantName']},</p>
                                    <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                    <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                    <p>Best Regards,</p>
                                    <p>Mich Manage</p>
                                    </body>
                                    </html>
                                    """

                                    # Attach the PDF receipt to the email
                                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                    # Send the email
                                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                                    thread.start()
                                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                            else:
                                db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
                                tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                                if tenant_user:
                                    db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                    db.userNotifications.insert_one({
                                        'category': 'payment',
                                        'user': tenant_user["_id"],
                                        'notification': f"New payment recorded by manager {login_data}",
                                        'timestamp': datetime.utcnow()
                                    })
                                # Create the email message
                                if send_emails is not None:
                                    msg = Message('Rent Payment Receipt-Mich Manage', 
                                                sender='michpmts@gmail.com', 
                                                recipients=[tenantEmail])
                                    msg.html = f"""
                                    <html>
                                    <body>
                                    <p>Dear {section_tenant['tenantName']},</p>
                                    <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                    <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                    <p>Best Regards,</p>
                                    <p>Mich Manage</p>
                                    </body>
                                    </html>
                                    """

                                    # Attach the PDF receipt to the email
                                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                    # Send the email
                                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                                    thread.start()
                                if '_id' in old_data:
                                    del old_data['_id']
                                db.old_tenant_data.insert_one(old_data)
                                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                flash(f"Updates for {old_data['tenantName']} were successful", 'success')

            elif field_month == months_paid_selected:
                if old_data['available_amount'] == section_value:
                    flash('Period selected is fully paid', 'error')
                else:
                    available_amount = new_amount + old_amount

                    balance = section_value - available_amount

                    buffer = BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=letter)

                    # QR Code Generation
                    url = f'https://michmanagement.onrender.com//get_receipt?tenantEmail={tenantEmail}&propertyName={propertyName}&selected_section={selected_section}&months_paid={months_paid}&year={date.year}'
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=3,
                        border=4,
                    )
                    qr.add_data(url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    img.save(f'payment_receipt_qr_{login_data}.png')

                    # Create the receipt details
                    data = [
                        ['Rent Payment Receipt - ' + company['company_name'], ''],
                        ['Receipt for:', section_tenant['tenantName']],
                        ['Property Name:', propertyName],
                        ['Payment Type:', section_tenant['payment_type']],
                        ['Amount Paid:', f"{section_tenant['currency']} {new_amount}"],
                        ['Payment Mode:', payment_mode],
                        ['Month Paid for:', months_paid],
                        ['Date Paid:', date.strftime('%Y-%m-%d')],
                        ['Balance:', f"{section_tenant['currency']} {balance}"],
                        ['Prepared by:', company['name']]
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
                    qr_code_img = f'payment_receipt_qr_{login_data}.png'
                    qr_code = Image(qr_code_img)
                    qr_code.hAlign = 'CENTER'

                    # Add the QR code image to the elements list before building the PDF
                    elements = [table, qr_code]
                    doc.build(elements)

                    # Get the PDF data and encode it as base64
                    pdf_data = buffer.getvalue()
                    buffer.close()
                    payment_receipt_base64 = base64.b64encode(pdf_data).decode()

                    # Delete the QR code image file
                    os.remove(f'payment_receipt_qr_{login_data}.png')
                    
                    new_data = {
                        'username': login_data,
                        'company_name': company['company_name'],
                        'tenantName': old_data['tenantName'],
                        'tenantEmail': tenantEmail,
                        'tenantPhone': old_data['tenantPhone'],
                        'propertyName': propertyName,
                        'selected_section': selected_section,
                        'section_value': old_data['section_value'],
                        'payment_type': old_data['payment_type'],
                        'amount': new_amount,
                        'payment_mode': payment_mode,
                        'months_paid': months_paid,
                        'year': date.year,
                        'available_amount': available_amount,
                        'payment_completion': payment_completion,
                        'currency': old_data['currency'],
                        'date_last_paid': date,
                        'payment_status': payment_status,
                        'status': 'updated',
                        'payment_receipt': payment_receipt_base64
                    }
                    if available_amount < section_value:
                        payment_completion = 'Partial'
                        new_data['payment_completion'] = payment_completion
                        if date.year == old_date.year:
                            db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
                            tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                            if tenant_user:
                                db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                db.userNotifications.insert_one({
                                    'category': 'payment',
                                    'user': tenant_user["_id"],
                                    'notification': f"New payment recorded by manager {login_data}",
                                    'timestamp': datetime.utcnow()
                                })
                            # Create the email message
                            if send_emails is not None:
                                msg = Message('Rent Payment Receipt-Mich Manage', 
                                            sender='michpmts@gmail.com', 
                                            recipients=[tenantEmail])
                                msg.html = f"""
                                <html>
                                <body>
                                <p>Dear {section_tenant['tenantName']},</p>
                                <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                thread = threading.Thread(target=send_async_email, args=[app, msg])
                                thread.start()
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                        elif date.year < old_date.year:
                            db.old_tenant_data.insert_one(new_data)
                            tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                            if tenant_user:
                                db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                db.userNotifications.insert_one({
                                    'category': 'payment',
                                    'user': tenant_user["_id"],
                                    'notification': f"New payment recorded by manager {login_data}",
                                    'timestamp': datetime.utcnow()
                                })
                            # Create the email message
                            if send_emails is not None:
                                msg = Message('Rent Payment Receipt-Mich Manage', 
                                            sender='michpmts@gmail.com', 
                                            recipients=[tenantEmail])
                                msg.html = f"""
                                <html>
                                <body>
                                <p>Dear {section_tenant['tenantName']},</p>
                                <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                thread = threading.Thread(target=send_async_email, args=[app, msg])
                                thread.start()
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                        else:
                            db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
                            tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                            if tenant_user:
                                db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                db.userNotifications.insert_one({
                                    'category': 'payment',
                                    'user': tenant_user["_id"],
                                    'notification': f"New payment recorded by manager {login_data}",
                                    'timestamp': datetime.utcnow()
                                })
                            # Create the email message
                            if send_emails is not None:
                                msg = Message('Rent Payment Receipt-Mich Manage', 
                                            sender='michpmts@gmail.com', 
                                            recipients=[tenantEmail])
                                msg.html = f"""
                                <html>
                                <body>
                                <p>Dear {section_tenant['tenantName']},</p>
                                <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                thread = threading.Thread(target=send_async_email, args=[app, msg])
                                thread.start()
                            if '_id' in old_data:
                                del old_data['_id']
                            db.old_tenant_data.insert_one(old_data)
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                    elif available_amount > section_value:        
                        flash("Enter amount that does not exceed section value", 'error')
                    else:
                        payment_completion = 'Full'
                        new_data['payment_completion'] = payment_completion
                        if date.year == old_date.year:
                            db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
                            tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                            if tenant_user:
                                db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                db.userNotifications.insert_one({
                                    'category': 'payment',
                                    'user': tenant_user["_id"],
                                    'notification': f"New payment recorded by manager {login_data}",
                                    'timestamp': datetime.utcnow()
                                })
                            # Create the email message
                            if send_emails is not None:
                                msg = Message('Rent Payment Receipt-Mich Manage', 
                                            sender='michpmts@gmail.com', 
                                            recipients=[tenantEmail])
                                msg.html = f"""
                                <html>
                                <body>
                                <p>Dear {section_tenant['tenantName']},</p>
                                <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                thread = threading.Thread(target=send_async_email, args=[app, msg])
                                thread.start()
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                        elif date.year < old_date.year:
                            db.old_tenant_data.insert_one(new_data)
                            tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                            if tenant_user:
                                db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                db.userNotifications.insert_one({
                                    'category': 'payment',
                                    'user': tenant_user["_id"],
                                    'notification': f"New payment recorded by manager {login_data}",
                                    'timestamp': datetime.utcnow()
                                })
                            # Create the email message
                            if send_emails is not None:
                                msg = Message('Rent Payment Receipt-Mich Manage', 
                                            sender='michpmts@gmail.com', 
                                            recipients=[tenantEmail])
                                msg.html = f"""
                                <html>
                                <body>
                                <p>Dear {section_tenant['tenantName']},</p>
                                <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                thread = threading.Thread(target=send_async_email, args=[app, msg])
                                thread.start()
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                        else:
                            db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
                            tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                            if tenant_user:
                                db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                                db.userNotifications.insert_one({
                                    'category': 'payment',
                                    'user': tenant_user["_id"],
                                    'notification': f"New payment recorded by manager {login_data}",
                                    'timestamp': datetime.utcnow()
                                })
                            # Create the email message
                            if send_emails is not None:
                                msg = Message('Rent Payment Receipt-Mich Manage', 
                                            sender='michpmts@gmail.com', 
                                            recipients=[tenantEmail])
                                msg.html = f"""
                                <html>
                                <body>
                                <p>Dear {section_tenant['tenantName']},</p>
                                <p>Please find attached your payment receipt for {months_paid} {date.year}.</p>
                                <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                thread = threading.Thread(target=send_async_email, args=[app, msg])
                                thread.start()
                            if '_id' in old_data:
                                del old_data['_id']
                            db.old_tenant_data.insert_one(old_data)
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful", 'success')
                    
            return redirect('/update-tenant-info')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

########LOAD PROPERTY DATA ################
def get_property_data(properties):
    property_data = []
    for property in properties:
        property_data.append((property['propertyName'], property['type'], property['property_value'],
                              property['address'], property['owner_name'], property['owner_phone']))
    return property_data

@app.route('/view-property-info')
def view_property_info():
    db, fs = get_db_and_fs()
    username = session.get('login_username')
    if username is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': username})
            dp_str = base64.b64encode(base64.b64decode(company.get('dp', ''))).decode() if 'dp' in company else None
            is_manager = db.managers.find_one({'manager_email': company['email']}) is not None

            properties_query = {'company_name': company['company_name']}
            if not is_manager:
                property_assigned = db.registered_managers.find({'username': username})
                property_assigned_dict = {property for doc in property_assigned if 'properties' in doc for property in doc['properties']}
                property_data = []
                for property in property_assigned_dict:
                    properties_query = {"propertyName": property}
                    properties = list(db.property_managed.find(properties_query))
                    if properties:
                        property_data.extend(get_property_data(properties))
                return render_template('property information.html', property_data=property_data, dp=dp_str)
            else:
                properties = list(db.property_managed.find(properties_query))
                if not properties:
                    flash('We did not find property data', 'error')
                    return redirect('/load-dashboard-page')
                
                property_data = get_property_data(properties)
                return render_template('property information.html', property_data=property_data, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

#####UPDATE PROPERTY INFO#############
@app.route('/update-property/<propertyName>')
def selected_property(propertyName):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            return render_template('update property information.html',propertyName=propertyName, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

##POSTING NEW PROPERTY INFORMATION
@app.route('/update-property', methods=["POST"])
def update_property():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            propertyName = request.form.get("propertyName")
            property_value = request.form.get("property_value")
            owner_name = request.form.get("owner_name")
            owner_email = request.form.get("owner_email")
            owner_phone = request.form.get("owner_phone")
            owner_residence = request.form.get("owner_residence")
            

            update_fields = {}

            if property_value:
                update_fields['property_value'] = property_value
            if owner_name:
                update_fields['owner_name'] = owner_name
            if owner_email:
                update_fields['owner_email'] = owner_email
            if owner_phone:
                update_fields['owner_phone'] = owner_phone
            if owner_residence:
                update_fields['owner_residence'] = owner_residence

            # Update the document with the non-empty fields
            db.property_managed.update_one({'propertyName': propertyName}, {'$set': update_fields})
            flash(f"{propertyName} was successfully updated", 'success')
            return redirect('/view-property-info')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

##VIEW MANAGER ACCOUNTS
def get_managers_data(registered_managers):
    managers = []
    for manager in registered_managers:
        managers.append((manager['name'], manager['email'], manager['phone_number'], manager['company_name']))
    return managers

@app.route('/view-user-accounts')
def view_user_accounts():
    db, fs = get_db_and_fs()
    # Get session data
    username = session.get('login_username')
    if username is None:
        flash('Login first', 'error')
        return redirect('/')

    # Get company data
    company = db.registered_managers.find_one({'username': username})
    dp_str = base64.b64encode(base64.b64decode(company.get('dp', ''))).decode() if 'dp' in company else None

    # Check if user is a manager
    is_manager = db.managers.find_one({'manager_email': company['email']}) is not None
    if not is_manager:
        flash("You do not have rights to view other users", 'error')

    # Get registered managers data
    registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': username}}))
    if not registered_managers:
        flash("We did not find other registered users", 'error')

    # Prepare managers data
    managers = get_managers_data(registered_managers)
    return render_template("view registered managers.html", managers=managers, dp=dp_str)


########DELETE PROPERTY################
@app.route('/delete_manager/<company_name>/<email>', methods=['POST'])
def delete_manager(company_name,email):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        manager = db.registered_managers.find_one({'company_name': company_name, 'email': email})
        company = db.managers.find_one({'name':company_name})
        managers = company['managers']
        for manager in managers:
            if email == manager:
                db.managers.update_one({'name': company_name}, {'$pull': {'managers': email}})
                db.other_managers.delete_one({'company_name': company_name, 'manager_email': email})
                db.registered_managers.delete_one({'company_name': company_name, 'email': email})
                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Delete manager', 'email':email, 'timestamp': datetime.now()})
        return redirect('/view-user-accounts')
    
########ADD NEW MANAGER EMAIL################
@app.route('/add-new-manager-email')
def add_new_manager_email():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
        is_manager = db.managers.find_one({'manager_email': company['email']})
        if is_manager:
            return render_template('add new manager email.html', dp=dp_str)
        else:
            flash("You do not have rights to add managers", 'error')
            return redirect('/load-dashboard-page')

@app.route('/update-new-manager-email', methods=['POST'])
def update_new_manager_email():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        email = request.form.get('email')
        account_type = request.form.get('account_type')
        manager_found = db.registered_managers.find_one({'username': login_data})
        company = db.managers.find_one({'name':manager_found['company_name']})
        managers = company['managers']
        exists = 0
        for manager in managers:
            if email == manager:
                flash('This email already exists', 'error')
                return redirect('/add-new-manager-email')
            else:
                exists = 1
        if exists == 1:
            db.managers.update_one({'name': manager_found['company_name']}, {'$push': {'managers': email}})
            db.other_managers.insert_one({'company_name': manager_found['company_name'], 'manager_email': email, 'account_type': account_type})
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add new manager', 'email':email, 'timestamp': datetime.now()})
            flash('New manager email was successfully added', 'success')
        return redirect('/add-new-manager-email')

#######CLICK TO UPDATE TENANT#############
@app.route('/selected-tenant/<tenantName>/<tenantEmail>/<propertyName>/<selected_section>/<payment_type>/<amount>/<months_paid>/<date_last_paid>')
def selected_tenant(tenantName, tenantEmail, propertyName, selected_section, payment_type, amount, months_paid,date_last_paid):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            date_last_paid = datetime.strptime(date_last_paid, '%Y-%m-%d')
            return render_template('update tenant information.html',tenantName=tenantName,tenantEmail=tenantEmail,propertyName=propertyName,selected_section=selected_section,payment_type=payment_type,amount=amount,months_paid=months_paid,year=date_last_paid.year,dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
        
##########EDIT TENANT INFO###################
@app.route('/edit/<tenantName>/<email>/<property_name>/<selected_section>/<payment_type>')
def edit(tenantName, email, property_name, selected_section, payment_type):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            # Retrieve the tenant's info using the email
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            tenant = db.tenants.find_one({'propertyName': property_name, 'selected_section': selected_section, 'tenantName': tenantName, 'company_name': company['company_name']})
            if tenant is None:
                return "Tenant not found", 404
            # Pass the tenant's info to the template
            return render_template('edit.html',tenantName=tenantName, tenant=tenant, payment_type=payment_type, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

############APPLY EDITS##############
@app.route('/make-edits', methods=["POST"])
def make_edits():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

            tenantEmail = request.form.get('tenantEmail')
            propertyName = request.form.get('propertyName')
            selected_section = request.form.get('selected_section')
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            # Create a dictionary for the fields to update
            fields_to_update = {}
            fields_to_update['status'] = 'edited'
            section_value = request.form.get('section_value')
            if section_value:
                section_value = int(section_value)
                fields_to_update['section_value'] = section_value
            else:
                tenant = db.tenants.find_one({'propertyName': propertyName, 'selected_section': selected_section, 'tenantEmail': tenantEmail, 'company_name': company['company_name']})
                section_value = tenant['section_value']

            date_last_paid = tenant['date_last_paid']
            amount = request.form.get('amount')
            if amount:
                amount = int(amount)
                fields_to_update['amount'] = amount
                fields_to_update['available_amount'] = amount + tenant['available_amount'] - tenant['amount']
                balance = section_value - (amount + tenant['available_amount'] - tenant['amount'])
                # Create a payment receipt PDF file
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)

                # QR Code Generation
                url = f'https://michmanagement.onrender.com//get_receipt?tenantEmail={tenantEmail}&propertyName={propertyName}&selected_section={selected_section}&months_paid={{{tenant["months_paid"]}}}&year={date_last_paid.year}'
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=3,
                    border=4,
                )
                qr.add_data(url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img.save(f'payment_receipt_qr_{login_data}.png')

                # Create the receipt details
                data = [
                    ['Rent Payment Receipt - ' + company['company_name'], ''],
                    ['Receipt for:', tenant['tenantName']],
                    ['Property Name:', propertyName],
                    ['Payment Type:', tenant['payment_type']],
                    ['Amount Paid:', f"{tenant['currency']} {amount}"],
                    ['Payment Mode:', tenant['payment_mode']],
                    ['Month Paid for:', tenant['months_paid']],
                    ['Date Paid:', date_last_paid.strftime('%Y-%m-%d')],
                    ['Balance:', f"{tenant['currency']} {balance}"],
                    ['Prepared by:', company['name']]
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
                qr_code_img = f'payment_receipt_qr_{login_data}.png'
                qr_code = Image(qr_code_img)
                qr_code.hAlign = 'CENTER'

                # Add the QR code image to the elements list before building the PDF
                elements = [table, qr_code]
                doc.build(elements)

                # Get the PDF data and encode it as base64
                pdf_data = buffer.getvalue()
                buffer.close()
                payment_receipt_base64 = base64.b64encode(pdf_data).decode()

                # Delete the QR code image file
                os.remove(f'payment_receipt_qr_{login_data}.png')

                fields_to_update['payment_receipt'] = payment_receipt_base64

                # Create the email message
                if send_emails is not None:
                    msg = Message('Rent Payment Receipt-Mich Manage', 
                                sender='michpmts@gmail.com', 
                                recipients=[tenantEmail])
                    msg.html = f"""
                    <html>
                    <body>
                    <p>Dear {tenant['tenantName']},</p>
                    <p>Please find attached your payment receipt for {tenant['months_paid']} {date_last_paid.year}.</p>
                    <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                    <p>Best Regards,</p>
                    <p>Mich Manage</p>
                    </body>
                    </html>
                    """

                    # Attach the PDF receipt to the email
                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                    # Send the email
                    thread = threading.Thread(target=send_async_email, args=[app, msg])
                    thread.start()

            payment_mode = request.form.get('payment_mode')
            if payment_mode:
                fields_to_update['payment_mode'] = payment_mode

            months_paid = request.form.get('months_paid')
            if months_paid:
                fields_to_update['months_paid'] = months_paid

            date_last_paid = request.form.get('date_last_paid')
            if date_last_paid:
                date_last_paid = datetime.strptime(date_last_paid, '%Y-%m-%d')
                fields_to_update['date_last_paid'] = date_last_paid

            if amount and section_value:
                if amount < section_value:
                    payment_completion = 'Partial'
                elif amount > section_value:
                    flash('Amount entered should not exceed section value', 'error')
                    return redirect(url_for('edit', email=tenantEmail))
                else:
                    payment_completion = 'Full'
                fields_to_update['payment_completion'] = payment_completion

            db.tenants.update_one({'propertyName': propertyName, 'selected_section': selected_section, 'tenantEmail':tenantEmail, 'company_name': company['company_name']},
                                    {'$set': fields_to_update})

            flash('Tenant was successfully edited', 'success')
            tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
            if tenant_user:
                db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                db.userNotifications.insert_one({
                    'category': 'payment',
                    'user': tenant_user["_id"],
                    'notification': f"New payment recorded by manager {login_data}",
                    'timestamp': datetime.utcnow()
                })
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Edit tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
            return redirect('/update-tenant-info')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
        
###########VIEW TENANT RECEIPT###############
@app.route('/view-receipt/<tenant_email>/<property_name>/<selected_section>', methods=["GET"])
def view_receipt(tenant_email, property_name, selected_section):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    # Retrieve the tenant document using tenant_id
    tenant = db.tenants.find_one({'username': login_data, 'propertyName': property_name, 'selected_section': selected_section, 'tenantEmail': tenant_email})

    if tenant is not None and 'payment_receipt' in tenant:
        # Convert the base64 string back to bytes
        payment_receipt = base64.b64decode(tenant['payment_receipt'])

        # Create a BytesIO object from the PDF data
        pdf_io = io.BytesIO(payment_receipt)

        # Create the file name
        file_name = f"{property_name}_{selected_section}_{{tenant['months_paid']}}_{{tenant['year']}}.pdf"

        # Create a custom response
        response = make_response(pdf_io.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={file_name}'

        return response

    else:
        return "No receipt found for this tenant", 404
                
#############ADD TENANT####################
@app.route('/add-tenant', methods=["POST"])
def add_tenant():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
            if send_emails is not None:
                app.config['MAIL_SERVER']='smtp.sendgrid.net'
                app.config['MAIL_PORT'] = 587
                app.config['MAIL_USERNAME'] = 'apikey'
                app.config['MAIL_PASSWORD'] = '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'
                app.config['MAIL_USE_TLS'] = True
                app.config['MAIL_USE_SSL'] = False
                mail.init_app(app)

            tenantName = request.form.get('tenantName')
            gender = request.form.get('gender')
            household_size = request.form.get('household_size')
            tenantEmail = request.form.get('tenantEmail')
            tenantPhone = request.form.get('tenantPhone')
            propertyName = request.form.get('propertyName')
            selected_section = request.form.get('selected_section')
            section_value = request.form.get('section_value')
            section_value = int(section_value)
            payment_type = request.form.get('payment_type')
            amount = request.form.get('amount')
            payment_completion = request.form.get('payment_completion')
            amount = int(amount)
            currency = request.form.get('currency')
            payment_mode = request.form.get('payment_mode')
            months_paid = request.form.get('months_paid')
            date_last_paid = request.form.get('date_last_paid')
            date_last_paid = datetime.strptime(date_last_paid, '%Y-%m-%d')

            balance = section_value - amount

            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})

            # Calculate the number of full months the payment covers
            num_full_months = amount // section_value
            receipt_month = months_paid
            if num_full_months > 1:
                number_of_months = num_full_months
                receipt_month = f"{number_of_months} months starting from {months_paid}"
                balance = 0
            # Create a payment receipt PDF file
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)

            # QR Code Generation
            url = f'https://michmanagement.onrender.com//get_receipt?tenantEmail={tenantEmail}&propertyName={propertyName}&selected_section={selected_section}&months_paid={months_paid}&year={date_last_paid.year}'
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(f'payment_receipt_qr_{login_data}.png')

            # Create the receipt details
            data = [
                ['Rent Payment Receipt - ' + company['company_name'], ''],
                ['Receipt for:', tenantName],
                ['Property Name:', propertyName],
                ['Payment Type:', payment_type],
                ['Amount Paid:', f"{currency} {amount}"],
                ['Payment Mode:', payment_mode],
                ['Month Paid for:', receipt_month],
                ['Date Paid:', date_last_paid.strftime('%Y-%m-%d')],
                ['Balance:', f"{currency} {balance}"],
                ['Prepared by:', company['name']]
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
            qr_code_img = f'payment_receipt_qr_{login_data}.png'
            qr_code = Image(qr_code_img)
            qr_code.hAlign = 'CENTER'

            # Add the QR code image to the elements list before building the PDF
            elements = [table, qr_code]
            doc.build(elements)

            # Get the PDF data and encode it as base64
            pdf_data = buffer.getvalue()
            buffer.close()
            payment_receipt_base64 = base64.b64encode(pdf_data).decode()

            # Delete the QR code image file
            os.remove(f'payment_receipt_qr_{login_data}.png')

            is_manager = db.managers.find_one({'manager_email': company['email']})
            num_tenants = db.tenants.count_documents({'company_name': company['company_name']})
            if is_manager['amount_per_month'] == 100000 and num_tenants>=50:
                flash('Maximum number of tenants is reached', 'error')
                return redirect('/load-dashboard-page')
            elif is_manager['amount_per_month'] == 150000 and num_tenants>=100:
                flash('Maximum number of tenants is reached', 'error')
                return redirect('/load-dashboard-page')
            elif is_manager['amount_per_month'] == 200000 and num_tenants>=200:
                flash('Maximum number of tenants is reached', 'error')
                return redirect('/load-dashboard-page')
            else:
                section_exists = db.tenants.find_one({'company_name': company['company_name'], 'propertyName': propertyName, 'selected_section': selected_section})
                if amount < section_value:
                    payment_completion = 'Partial'
                elif amount > section_value:
                    # Get the starting month number from the form data
                    starting_month = list(calendar.month_name).index(months_paid)

                    # Calculate the remaining amount after the full months
                    remaining_amount = amount % section_value

                    # Create a list to store the data for each month
                    monthly_data = []

                    # Add the data for the full months
                    for i in range(num_full_months):
                        month_number = (starting_month + i - 1) % 12 + 1
                        year = date_last_paid.year + (starting_month + i - 1) // 12
                        monthly_data.append({
                            'username': login_data,
                            'company_name': company['company_name'],
                            'tenantName': tenantName,
                            'gender': gender,
                            'household_size': household_size,
                            'tenantEmail': tenantEmail,
                            'tenantPhone': tenantPhone,
                            'propertyName': propertyName,
                            'selected_section': selected_section,
                            'section_value': section_value,
                            'payment_type': payment_type,
                            'amount': section_value,
                            'payment_mode': payment_mode,
                            'months_paid': calendar.month_name[month_number],
                            'year': year,
                            'available_amount': section_value,
                            'payment_completion': 'Full',
                            'currency': currency,
                            'date_last_paid': date_last_paid,
                            'payment_status': '',
                            'status': '',
                            'payment_receipt': payment_receipt_base64
                        })

                    # If there is a remaining amount, add the data for the partial month
                    if remaining_amount > 0:
                        month_number = (starting_month + num_full_months - 1) % 12 + 1
                        year = date_last_paid.year + (starting_month + num_full_months - 1) // 12
                        monthly_data.append({
                            'username': login_data,
                            'company_name': company['company_name'],
                            'tenantName': tenantName,
                            'gender': gender,
                            'household_size': household_size,
                            'tenantEmail': tenantEmail,
                            'tenantPhone': tenantPhone,
                            'propertyName': propertyName,
                            'selected_section': selected_section,
                            'section_value': section_value,
                            'payment_type': payment_type,
                            'amount': remaining_amount,
                            'payment_mode': payment_mode,
                            'months_paid': calendar.month_name[month_number],
                            'year': year,
                            'available_amount': remaining_amount,
                            'payment_completion': 'Partial',
                            'currency': currency,
                            'date_last_paid': date_last_paid,
                            'payment_status': '',
                            'status': '',
                            'payment_receipt': payment_receipt_base64
                        })

                    # Now you can store the data for each month separately
                    for i, data in enumerate(monthly_data):
                        if i < len(monthly_data) - 1:  # If it's not the last record
                            # Store in 'old_tenant_data'
                            db.old_tenant_data.insert_one(data)
                        else:  # If it's the last record
                            # Store in 'tenants', regardless of whether it's fully paid or not
                            db.tenants.insert_one(data)
                    
                    tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                    if tenant_user:
                        db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                        db.userNotifications.insert_one({
                            'category': 'payment',
                            'user': tenant_user["_id"],
                            'notification': f"New payment recorded by manager {login_data}",
                            'timestamp': datetime.utcnow()
                        })
                    # Create the email message
                    if send_emails is not None:
                        msg = Message('Rent Payment Receipt-Mich Manage', 
                                    sender='michpmts@gmail.com', 
                                    recipients=[tenantEmail])
                        msg.html = f"""
                        <html>
                        <body>
                        <p>Dear {tenantName},</p>
                        <p>Please find attached your payment receipt for {receipt_month} {date_last_paid.year}.</p>
                        <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                        <p>Best Regards,</p>
                        <p>Mich Manage</p>
                        </body>
                        </html>
                        """

                        # Attach the PDF receipt to the email
                        msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                        # Send the email
                        thread = threading.Thread(target=send_async_email, args=[app, msg])
                        thread.start()
                    db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add tenant data', 'tenantName': tenantName, 'timestamp': datetime.now()})
                    flash('Tenant was successfully added', 'success')
                    return redirect('/load-dashboard-page')
                else:
                    payment_completion = 'Full'
                if section_exists is None:
                    tenant_details = {'username': login_data,
                                        'company_name': company['company_name'],
                                        'tenantName': tenantName,
                                        'gender': gender,
                                        'household_size': household_size,
                                        'tenantEmail': tenantEmail,
                                        'tenantPhone': tenantPhone,
                                        'propertyName': propertyName,
                                        'selected_section': selected_section,
                                        'section_value': section_value,
                                        'payment_type': payment_type,
                                        'amount': amount,
                                        'payment_mode': payment_mode,
                                        'months_paid': months_paid,
                                        'year': date_last_paid.year,
                                        'available_amount': amount,
                                        'payment_completion': payment_completion,
                                        'currency': currency,
                                        'date_last_paid': date_last_paid,
                                        'payment_status': '',
                                        'status': '',
                                        'payment_receipt': payment_receipt_base64}
                    
                    db.tenants.insert_one(tenant_details)
                    tenant_user = db.tenant_user_accounts.find_one({'tenantEmail': tenantEmail, 'propertyName': propertyName})
                    if tenant_user:
                        db.userNotifications.create_index([("timestamp", ASCENDING)], expireAfterSeconds=20)
                        db.userNotifications.insert_one({
                            'category': 'payment',
                            'user': tenant_user["_id"],
                            'notification': f"New payment recorded by manager {login_data}",
                            'timestamp': datetime.utcnow()
                        })
                    # Create the email message
                    if send_emails is not None:
                        msg = Message('Rent Payment Receipt-Mich Manage', 
                                    sender='michpmts@gmail.com', 
                                    recipients=[tenantEmail])
                        msg.html = f"""
                        <html>
                        <body>
                        <p>Dear {tenantName},</p>
                        <p>Please find attached your payment receipt for {months_paid} {date_last_paid.year}.</p>
                        <p><b><a href="https://michmanagement.onrender.com//tenant%20login%20page">Login</a></b></p>
                        <p>Best Regards,</p>
                        <p>Mich Manage</p>
                        </body>
                        </html>
                        """

                        # Attach the PDF receipt to the email
                        msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                        # Send the email
                        thread = threading.Thread(target=send_async_email, args=[app, msg])
                        thread.start()
                    db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add tenant data', 'tenantName':tenantName, 'timestamp': datetime.now()})
                    flash('Tenant was successfully added', 'success')
                    return redirect('/load-dashboard-page')
                else:
                    flash('Section is already assigned', 'error')
                    return redirect('/load-dashboard-page')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

########DELETE TENANT################
@app.route('/delete_tenant/<tenantEmail>/<propertyName>/<selected_section>')
def delete_tenant(tenantEmail, propertyName, selected_section):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            tenants = db.tenants.find_one({'company_name': company['company_name'], 'tenantEmail': tenantEmail, 'propertyName': propertyName, 'selected_section': selected_section})
            # Remove the _id field
            if '_id' in tenants:
                del tenants['_id']
            db.old_tenant_data.insert_one(tenants)
            db.old_tenant_data.update_one({'company_name': company['company_name'], 'tenantEmail': tenantEmail, 'propertyName': propertyName, 'selected_section': selected_section}, {'$set': {'status': 'deleted'}})
            db.tenants.delete_one({'company_name': company['company_name'], 'tenantEmail': tenantEmail, 'propertyName': propertyName, 'selected_section': selected_section})
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Delete tenant', 'tenantName': tenants['tenantName'], 'timestamp': datetime.now()})
            return redirect('/update-tenant-info')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/admin-login', methods=["POST"])
def adminlogin():
    db, fs = get_db_and_fs()
    email = request.form.get('email')
    entered_password = request.form.get('password')
    password = entered_password.encode('utf-8')
    
    user = db.admin.find_one({'email':email})
    if user is None:
        flash('Not an admin', 'error')
        return redirect('/admin')
    else:
        stored_password = user['password'].encode('utf-8')
        if bcrypt.checkpw(password, stored_password):
            session.permanent = False
            session['admin_email'] = user['email']
            session['logged_in'] = True
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
            if send_emails is not None:
                session['send_emails'] = "yes"
            else:
                session['send_emails'] = "no"
            return render_template("managers accounts.html")
        else:
            flash('Wrong Password', 'error')
            return redirect('/admin')

@app.route('/registered clients')
def registered_clients():
    db, fs = get_db_and_fs()
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else: 
        managers = []
        clients = list(db.managers.find({},{'name': 1, 'last_subscribed_on': 1, 'subscribed_days': 1, 'amount_per_month': 1, 'account_type': 1, '_id': 0}))
        if len(clients) != 0:
            for client in clients:
                remaining_days = (client['last_subscribed_on'] + timedelta(days=client['subscribed_days']) - datetime.now()).days
                client['remaining_days'] = remaining_days
                account_type = client['account_type']
                if 'Enterprise Resource Planning' in account_type and len(account_type) == 1:
                    client['account_type'] = 'ERP'
                elif 'Property Management' in account_type and len(account_type) == 1:
                    client['account_type'] = 'Property Mgt'
                elif 'Enterprise Resource Planning' in account_type and 'Property Management' in account_type:
                    client['account_type'] = 'All types'
                managers.append(client)
        return render_template('registered clients.html',managers=managers)

@app.route('/add-property-manager-page')
def add_property_manager_page():
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else:
        return render_template("managers accounts.html")

##########ADD MANAGER COMPANY#############
@app.route('/add-property-manager', methods=["POST"])
def add_property_manager():
    db, fs = get_db_and_fs()
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else:   
        send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
        if send_emails is not None:
            app.config['MAIL_SERVER']='smtp.sendgrid.net'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USERNAME'] = 'apikey'
            app.config['MAIL_PASSWORD'] = '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'
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USE_SSL'] = False
            mail.init_app(app)

        email = request.form.get('email')
        name = request.form.get('name')
        allowed_managers = request.form.get('managers').split(',')
        manager_email = request.form.get('manager_email')
        subscribed_days = request.form.get('subscribed_days')
        subscribed_days = int(subscribed_days)
        amount_per_month_form_data = request.form.get('amount_per_month')
        amount_per_month = 0
        if amount_per_month_form_data == "100000":
            amount_per_month = 100000
        elif amount_per_month_form_data == "150000":
            amount_per_month = 150000
        elif amount_per_month_form_data == "200000":
            amount_per_month = 200000
        elif amount_per_month_form_data == "400000":
            amount_per_month = 400000
        
        account_type = request.form.getlist('account_type')
        if 'All Types' in account_type:
            account_type = ['Property Management', 'Enterprise Resource Planning']
        managers = db.managers.find_one({'name': name})
        if managers is None:
            manager = {'email': email, 'name': name, 'managers': allowed_managers,
                    'manager_email': manager_email, 'last_subscribed_on': datetime.now(),
                    'subscribed_days': subscribed_days, 'amount_per_month': amount_per_month, 'account_type': account_type}
            db.managers.insert_one(manager)
            user_data = session.get('user_data')

            if send_emails is not None:
                msg = Message('Account Creation Invitation from Mich Manage', 
                            sender='michpmts@gmail.com', 
                            recipients=allowed_managers)
                msg.html = f"""
                <html>
                <body>
                <p>Dear Manager,</p>
                <p>You have been granted permission to create an account with Mich Manage. Please click the link below to register:</p>
                <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com//manager%20register">Register Now</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                thread = threading.Thread(target=send_async_email, args=[app, msg])
                thread.start()

            flash('Company managers can now create accounts', 'success')
            return render_template("managers accounts.html", user_data=user_data)
        else:
            flash('Company already registered', 'error')
            return render_template("managers accounts.html")

#######NEW SUBSCRIPTION PAGE###############
@app.route("/new-subscription")
def new_subscription():
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else:
        db, fs = get_db_and_fs()
        companies = db.managers.find({}, {"name": 1, "_id": 0})
        company_names = [company['name'] for company in companies]
        
        if not company_names:
            flash('We found no companies', 'error')
            return render_template("managers accounts.html")
        else:
            return render_template("new_subscription.html", company_names=company_names)
    
#######STORING NEW SUBSCRIPTION###############
@app.route("/new-subscription-initiated", methods=["POST"])
def new_subscription_initiated():
    db, fs = get_db_and_fs()
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else:
        company_name = request.form.get('company_name')
        last_subscribed_on_str = request.form.get('last_subscribed_on')
        subscribed_days = request.form.get('subscribed_days')
        amount_per_month_form_data = request.form.get('amount_per_month')
        account_type = request.form.getlist('account_type')

        company = db.managers.find_one({'name': company_name})
        remaining_days = (company['last_subscribed_on'] + timedelta(days=company['subscribed_days']) - datetime.now()).days

        fields_to_update = {}
        if last_subscribed_on_str:
            last_subscribed_on = datetime.strptime(last_subscribed_on_str, '%Y-%m-%d')
            if last_subscribed_on <= company['last_subscribed_on']:
                flash('Enter a newer subscription date', 'error')
            else:
                fields_to_update['last_subscribed_on'] = last_subscribed_on
                flash('New Subscription was added')
        if subscribed_days:
            subscribed_days = int(subscribed_days)
            if remaining_days <= 0:
                subscribed_days = subscribed_days + 0
                fields_to_update['subscribed_days'] = subscribed_days
            else:
                if last_subscribed_on <= company['last_subscribed_on']:
                    flash('Enter a newer subscription date', 'error')
                else:
                    subscribed_days = subscribed_days + remaining_days
                    fields_to_update['subscribed_days'] = subscribed_days
        if amount_per_month_form_data:
            amount_per_month = 0
            if amount_per_month_form_data == "100000":
                amount_per_month = 100000
            elif amount_per_month_form_data == "150000":
                amount_per_month = 150000
            elif amount_per_month_form_data == "200000":
                amount_per_month = 200000
            elif amount_per_month_form_data == "400000":
                amount_per_month = 400000
            fields_to_update['amount_per_month'] = amount_per_month
            flash('New Subscription plan was set', 'success')
        if account_type:
            if 'All Types' in account_type:
                account_type = ['Property Management', 'Enterprise Resource Planning']
            fields_to_update['account_type'] = account_type
            flash('New Subscription plan was set', 'success')

        db.managers.update_one({'name': company_name},{'$set': fields_to_update})
        return render_template("managers accounts.html")

#############DASHBOARD PAGE#######################
@app.route('/load-dashboard-page', methods=["GET", "POST"])
def load_dashboard_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    # get the current month number
    current_month = datetime.now().month
    # convert the month number to its name
    month_name = calendar.month_name[current_month]
    # capitalize the first letter
    month_name = month_name.capitalize()

    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

            if send_emails is None:
                session['send_emails_message'] = "Our email service is currently unavailable. We apologize for any inconvenience. Our team is working hard to fix the issue and we expect the service to be back soon."
                    
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")

            month_mapping = {
                'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12,
                'Quarter 1': 3, 'Quarter 2': 6, 'Quarter 3': 9, 'Quarter 4': 12,
                '2024': 12, '2025': 12, '2026': 12
            }

            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            subscription = db.managers.find_one({'name': company['company_name']}, {'account_type': 1, 'manager_email': 1, '_id': 0})
            account_type = subscription['account_type']
            # Remove any empty strings from the list
            account_type = [atype for atype in account_type if atype]

            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None

            if subscription['manager_email'] == company['email']:
                user_query  = {'company_name': company['company_name']}
            else:
                user_query  = {'username': login_data, 'company_name': company['company_name']}
                
            projection = {'payment_receipt': 0, 'username': 0, 'company_name': 0, 'tenantEmail': 0, 'tenantPhone': 0, 'payment_mode': 0,
                        'gender': 0, 'household_size': 0, 'payment_type': 0, 'payment_completion': 0, 'currency': 0, 'payment_status': 0,
                        '_id': 0}
            property_data_list = list(db.property_managed.find(user_query))
            if len(property_data_list) == 0:
                flash('No property data found', 'error')
                return render_template('dashboard.html', chart_property_performance_trended_data=[],chart_property_performance_data=[],chart_property_type_data=[],dp=dp_str)
            else:
                if startdate_on_str and enddate_on_str:
                    startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
                    enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
                    latest_year = enddate.year

                    date_query = {'date_last_paid': {'$gte': startdate, '$lte': enddate}, 'status': {'$ne': 'deleted'}}
                    date_query.update(user_query)

                    current_tenant_data = list(db.tenants.find(date_query, projection))

                    old_tenant_data = list(db.old_tenant_data.find(date_query, projection))

                    tenant_data_stats = list(db.tenants.find({}, projection))

                    month_name = f"{startdate_on_str} to {enddate_on_str}"
                else:
                    latest_document = db.tenants.find_one(sort=[('date_last_paid', -1)], projection={'date_last_paid': 1, '_id': 0})
                    if latest_document is None:
                        latest_document_old = db.old_tenant_data.find_one(sort=[('date_last_paid', -1)], projection={'date_last_paid': 1, '_id': 0})
                        if latest_document_old is None:
                            flash('No tenant data found', 'error')
                            return render_template('dashboard.html', chart_property_performance_trended_data=[],chart_property_performance_data=[],chart_property_type_data=[],dp=dp_str)
                        else:
                            latest_year = latest_document_old['date_last_paid'].year
                    else:    
                        latest_year = latest_document['date_last_paid'].year

                    startdate = datetime(latest_year, 1, 1)
                    enddate = datetime(latest_year, 12, 31, 23, 59, 59)

                    date_query = {'date_last_paid': {'$gte': startdate, '$lte': enddate}, 'status': {'$ne': 'deleted'}}
                    date_query.update(user_query)

                    current_tenant_data = list(db.tenants.find(date_query, projection))

                    old_tenant_data = list(db.old_tenant_data.find(date_query, projection))

                    tenant_data_stats = list(db.tenants.find({}, projection))

                    month_name = f"{startdate.strftime('%Y-%m-%d')} to {enddate.strftime('%Y-%m-%d')}"
                
                overdue_tenants = []
                count_current_tenants = 0
                if len(tenant_data_stats) != 0:
                    for count_tenant in tenant_data_stats:
                        if count_tenant['status'] != 'deleted':
                            count_current_tenants += 1

                            last_payment_month = month_mapping.get(count_tenant['months_paid'], 0)
                            last_payment_date = datetime(year=count_tenant['year'], month=last_payment_month, day=1)
                            next_payment_date = last_payment_date + timedelta(days=30)
                            remaining_days = (next_payment_date - datetime.now()).days
                            if remaining_days < 0:
                                overdue = True
                                remaining_days = abs(remaining_days)
                                if remaining_days < 7:
                                    time_unit = 'day(s)'
                                elif remaining_days < 30:
                                    remaining_days = round(remaining_days / 7)
                                    time_unit = 'week(s)'
                                elif remaining_days < 365:
                                    remaining_days = round(remaining_days / 30)
                                    time_unit = 'month(s)'
                                else:
                                    remaining_days = round(remaining_days / 365)
                                    time_unit = 'year(s)'

                                overdue_status = 'overdue' if overdue else 'due in'
                                overdue_tenants.append((count_tenant['tenantName'], count_tenant['propertyName'],count_tenant['selected_section'], remaining_days, time_unit, overdue_status))

                    overdue_tenants = sorted(overdue_tenants, key=lambda x: x[3], reverse=True)

                doc_query = {'status': {'$ne': 'deleted'}}
                doc_query.update(user_query)
                tenant_data_cursor = db.tenants.find(doc_query, projection)
                
                property_data_dict = {doc['propertyName']: doc['sections'] for doc in property_data_list}
                property_occupancy = {doc['propertyName']: {'total': len(doc['sections']), 'occupied': 0} for doc in property_data_list}
                for tenant_exists in tenant_data_cursor:
                    tenant_property_name = tenant_exists.get('propertyName', '').strip()
                    selected_section = tenant_exists.get('selected_section', '').strip()
                    # Check if the property exists in updated_property_data and the section is in the property's sections
                    if tenant_property_name in property_data_dict and selected_section in property_data_dict[tenant_property_name]:
                        # Remove the section
                        property_data_dict[tenant_property_name].remove(selected_section)
                        # Increase the count of occupied sections
                        property_occupancy[tenant_property_name]['occupied'] += 1
                        # If there are no more sections for this property, remove the property
                        if not property_data_dict[tenant_property_name]:
                            del property_data_dict[tenant_property_name]

                if current_tenant_data or old_tenant_data:  # Check if data is available
                    combined_data = current_tenant_data + old_tenant_data

                    # Create a mapping of property values
                    property_value_dict = {item['propertyName']: item['property_value'] for item in property_data_list}

                    # Initialize dictionaries to hold data
                    property_performance = defaultdict(lambda: {
                        'available_amount': 0,
                        'months_paid': set(),
                        'property_value': 0,
                        'demanded_amount': 0
                    })
                    
                    # Process combined_data
                    for item in combined_data:
                        prop_name = item['propertyName']
                        if prop_name in property_value_dict:
                            property_value = property_value_dict[prop_name]
                            property_performance[prop_name]['available_amount'] += item.get('available_amount', 0)
                            property_performance[prop_name]['months_paid'].add(item.get('months_paid', ''))
                            property_performance[prop_name]['property_value'] = property_value
                    
                    # Compute months_paid_count and total_property_value
                    for prop_name, data in property_performance.items():
                        data['months_paid_count'] = len(data['months_paid'])
                        data['total_property_value'] = data['months_paid_count'] * data['property_value']
                        data['demanded_amount'] = data['total_property_value'] - data['available_amount']
                    
                    # Initialize for property_performance_line
                    property_performance_line = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
                    for item in combined_data:
                        year = item.get('year')
                        month = item.get('months_paid')
                        prop_name = item['propertyName']
                        property_performance_line[year][month][prop_name] += item.get('available_amount', 0)
                    
                    # Prepare data for property_performance_line for the chart
                    month_order = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
                    labels = month_order
                    datasets = {prop_name: [property_performance_line[year].get(month, {}).get(prop_name, 0) for month in month_order] for prop_name in property_performance.keys()}

                    chart_property_performance_trended_data = {
                        'labels': labels,
                        'datasets': [{'label': prop_name, 'data': datasets[prop_name]} for prop_name in property_performance.keys()]
                    }

                    chart_property_performance_data = {
                        'labels': list(property_performance.keys()),
                        'available_amount': [data['available_amount'] for data in property_performance.values()],
                        'demanded_amount': [data['demanded_amount'] for data in property_performance.values()]
                    }

                    # Count properties and available amount
                    count_property = len(property_data_list)
                    available_amount = sum(item.get('available_amount', 0) for item in combined_data)

                    # Group property data
                    property_type_counts = defaultdict(int)
                    for item in property_data_list:
                        property_type_counts[item['type']] += 1
                    
                    chart_property_type_data = {
                        'labels': list(property_type_counts.keys()),
                        'values': list(property_type_counts.values())
                    }

                    return render_template('dashboard.html', 
                                        chart_property_performance_trended_data=chart_property_performance_trended_data,
                                        chart_property_performance_data=chart_property_performance_data,
                                        chart_property_type_data=chart_property_type_data, 
                                        count_property=count_property,
                                        available_amount=available_amount,
                                        overdue_tenants=overdue_tenants,
                                        property_occupancy=property_occupancy,
                                        count_current_tenants=count_current_tenants,
                                        month_name=month_name, dp=dp_str)
                else:
                    flash('No tenant data found', 'error')
                    return render_template('dashboard.html', chart_property_performance_trended_data=[],chart_property_performance_data=[],chart_property_type_data=[],dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
        
#############MANAGER DOWNLOAD DATA######################
@app.route('/download', methods=["POST"])
def download():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')

            # Fetch company information
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'address': 0, 'password': 0, 'auth': 0, 'dark_mode': 0})
            if not company:
                flash('Company not found', 'error')
                return redirect('/')
            
            is_manager = db.managers.find_one({'manager_email': company['email']})
            if is_manager is None:
                user_query = {'username': login_data, 'company_name': company['company_name'], 'date_last_paid': {'$gte': startdate, '$lte': enddate}}
            else:
                user_query = {'company_name': company['company_name'], 'date_last_paid': {'$gte': startdate, '$lte': enddate}}
            
            projection = {'payment_receipt': 0, '_id': 0, 'marital_status': 0, 'age': 0, 'available_amount': 0, 'payment_completion': 0,
                        'currency': 0, 'payment_status': 0, 'status': 0, 'household_size': 0}

            # Fetch tenant data
            current_tenant_data = list(db.tenants.find(user_query, projection))
            old_tenant_data = list(db.old_tenant_data.find(user_query, projection))

            if not (current_tenant_data or old_tenant_data):
                flash('No tenant data found', 'error')
                return redirect('/load-dashboard-page')
            
            # Combine data
            combined_data = current_tenant_data + old_tenant_data

            # Define column names and month order
            new_column_names = {
                'username': 'Property manager',
                'company_name': 'Company',
                'tenantName': 'Tenant name',
                'gender': 'Gender',
                'tenantEmail': 'Tenant email',
                'tenantPhone': 'Tenant phone',
                'propertyName': 'Property name',
                'selected_section': 'Section',
                'section_value': 'Section value',
                'payment_type': 'Payment type',
                'amount': 'Amount paid',
                'payment_mode': 'Payment mode',
                'months_paid': 'Month paid',
                'year': 'Year',
                'date_last_paid': 'Date paid',
            }
            
            month_order = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6, 'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12}
            
            # Create an Excel workbook
            output = BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "Tenants"

            # Write column headers
            headers = list(new_column_names.values())
            for col_idx, col_name in enumerate(headers, start=1):
                ws.cell(row=1, column=col_idx, value=col_name)

            # Write data rows
            for r_idx, item in enumerate(combined_data, start=2):
                for c_idx, key in enumerate(new_column_names.keys(), start=1):
                    value = item.get(key, '')
                    if key == 'months_paid' and value in month_order:
                        value = month_order[value]
                    ws.cell(row=r_idx, column=c_idx, value=value)

            # Protect the Excel file with a password
            file_password = generate_file_password()
            ws.protection.set_password(file_password)

            existing_password = db.file_passwords.find_one({'username': login_data, 'detail': 'Tenant data file'})
            if existing_password:
                db.file_passwords.delete_one({'username': login_data, 'detail': 'Tenant data file'})
            db.file_passwords.insert_one({'username': login_data, 'password': file_password, 'detail': 'Tenant data file'})

            # Save the workbook to a BytesIO buffer
            output.seek(0)
            wb.save(output)
            wb.close()

            # Set the buffer position to the beginning
            output.seek(0)
            protected_data = output.read()

            # Create a response with the protected Excel file
            response = make_response(protected_data)
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_{startdate_on_str}_{enddate_on_str}.xlsx"
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

            # Optionally, save the password to the database (if needed)
            existing_password = db.file_passwords.find_one({'username': login_data, 'detail': 'Tenant data file'})
            if existing_password:
                db.file_passwords.delete_one({'username': login_data, 'detail': 'Tenant data file'})
            db.file_passwords.insert_one({'username': login_data, 'password': file_password, 'detail': 'Tenant data file'})

            return response
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
        
#####FILE PASSWORDS
@app.route('/view-file-passwords')
def view_file_passwords():
    db, fs = get_db_and_fs()
    username = session.get('login_username')
    if username is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': username})
            dp_str = base64.b64encode(base64.b64decode(company.get('dp', ''))).decode() if 'dp' in company else None
            
            file_passwords = list(db.file_passwords.find({'username': username}))
            if len(file_passwords)==0:
                flash('No encryption keys found', 'error')
                return redirect('/load-dashboard-page')
            else:
                found_passwords = []
                for password in file_passwords:
                    found_passwords.append(password)
            return render_template('file passwords.html', found_passwords=found_passwords, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

####MANAGE CONTRACTS
@app.route('/manage-contracts')
def manage_contracts():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            is_manager = db.managers.find_one({'manager_email': company['email']})
            ####CHECK IS LOGEDIN MANAGER HAS FULL RIGHTS
            if is_manager is None:
                user_querry = {'username': login_data, 'company_name': company['company_name']}
            else:
                user_querry = {'company_name': company['company_name']}

            contracts = list(db.contracts.find(user_querry))
            if len(contracts)==0:
                flash('You are not managing any contracts!', 'error')
                return redirect('/load-dashboard-page')
            else:
                tenant_contracts = []
                for contract in contracts:
                    end_date = contract['end_date']
                    now = datetime.now()
                    # Calculate the remaining period from now
                    remaining_seconds = int((end_date - now).total_seconds())
                    remaining_minutes, remaining_seconds = divmod(remaining_seconds, 60)
                    remaining_hours, remaining_minutes = divmod(remaining_minutes, 60)
                    remaining_days, remaining_hours = divmod(remaining_hours, 24)
                    remaining_days += 1

                    if remaining_days < 0:
                        contract['remaining'] = 'Expired'
                    elif remaining_days < 7:
                        contract['remaining'] = f"In {remaining_days} days, {remaining_hours} hours, and {remaining_minutes} minutes"
                    elif 7 <= remaining_days < 30:
                        weeks, days = divmod(remaining_days, 7)
                        contract['remaining'] = f"In {weeks} weeks, {days} days, {remaining_hours} hours, and {remaining_minutes} minutes"
                    elif 30 <= remaining_days < 365:
                        months, days = divmod(remaining_days, 30)
                        contract['remaining'] = f"In {months} months, {days} days, {remaining_hours} hours, and {remaining_minutes} minutes"
                    else:
                        years, days = divmod(remaining_days, 365)
                        contract['remaining'] = f"In {years} years, {days} days, {remaining_hours} hours, and {remaining_minutes} minutes"
                    tenant_contracts.append(contract)
                return render_template('manage contracts.html', tenant_contracts=tenant_contracts, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
        
@app.route('/upload-contract-page')
def upload_contract_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            is_manager = db.managers.find_one({'manager_email': company['email']})
            ####CHECK IS LOGEDIN MANAGER HAS FULL RIGHTS
            if is_manager is None:
                user_querry = {'username': login_data, 'company_name': company['company_name']}
            else:
                user_querry = {'company_name': company['company_name']}
            
            tenants = list(db.tenants.find(user_querry))

            if len(tenants) == 0:
                flash('No tenant data found', 'error')
                return redirect('/load-dashboard-page')
            else:
                tenant_names = []
                for tenant in tenants:
                    tenant_names.append(tenant['tenantName'])
            return render_template('add contracts.html',tenant_names=tenant_names, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/upload-contract', methods=['POST'])
def upload_contract():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            if 'contract_document' not in request.files:
                flash("No file part", 'error')
                return redirect('/upload-contract-page')
            file = request.files['contract_document']
            if file.filename == '':
                flash("No file selected", 'error')
                return redirect('/upload-contract-page')
            if file:
                filename = secure_filename(file.filename)
                content_type = file.content_type
                file_id = fs.put(file.read(), filename=filename, content_type=content_type)
                company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
                receiver = request.form.get('receiver')
                start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
                end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')

                contract = {
                    'username': login_data,
                    'company_name': company['company_name'],
                    'file_id': file_id,
                    'issuer': company['name'],
                    'receiver': receiver,
                    'start_date': start_date,
                    'end_date': end_date
                }

                db.contracts.insert_one(contract)
                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add new contract', 'file_id': file_id, 'timestamp': datetime.now()})
                flash("Contract was uploaded successfully", 'success')
                return redirect('/upload-contract-page')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

########DELETE CONTRACTS################
@app.route('/delete-contract/<contractID>')
def delete_contract(contractID):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            contract = db.contracts.find_one({'_id': ObjectId(contractID)})
            # Remove the _id field
            if '_id' in contract:
                del contract['_id']
            db.old_contracts.insert_one(contract)
            db.contracts.delete_one({'_id': ObjectId(contractID)})
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Delete contract', 'contractID':contractID, 'timestamp': datetime.now()})
            return redirect('/manage-contracts')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

##UPDATE CONTRACTS
@app.route('/update-contract/<contractID>/<company_name>/<receiver>')
def selected_contract(contractID, company_name, receiver):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            return render_template('update contract.html',contractID=contractID,company_name=company_name,receiver=receiver,dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/updated-contract', methods=['POST'])
def updated_contract():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            if 'contract_document' not in request.files:
                flash("No file part", 'error')
                return redirect('/manage-contracts')
            file = request.files['contract_document']
            if file.filename == '':
                flash("No file selected", 'error')
                return redirect('/manage-contracts')
            if file:
                filename = secure_filename(file.filename)
                content_type = file.content_type
                file_id = fs.put(file.read(), filename=filename, content_type=content_type)
                end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
                contractID = request.form.get('contractID')

                contract = db.contracts.find_one({'_id': ObjectId(contractID)})
                if contract:
                    # If a contract exists, update the document and end date
                    fs.delete(contract['file_id'])
                    db.contracts.update_one(
                        {'_id': ObjectId(contractID)},
                        {'$set': {'file_id': file_id, 'end_date': end_date}}
                    )
                    db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update contract', 'file_id': file_id, 'timestamp': datetime.now()})
                    flash("Contract was updated successfully", 'success')
                    return redirect('/manage-contracts')
                else:
                    flash("Contract was not found", 'error')
                    return redirect('/manage-contracts')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
            
@app.route('/download-contract/<fileID>')
def download_contract(fileID):
    db, fs = get_db_and_fs()
    file = fs.get(ObjectId(fileID))
    
    # Create a BytesIO buffer to zip the file
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr(file.filename, file.read())
    
    zip_buffer.seek(0)
    zip_data = zip_buffer.getvalue()
    
    response = make_response(zip_data)
    response.headers['Content-Disposition'] = f'attachment; filename={file.filename}.zip'
    response.headers['Content-Type'] = 'application/zip'
    
    return response

####MANAGE USER RIGHTS
@app.route('/manage-user-rights')
def manage_user_rights():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
        
        # Get registered managers data
        registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': login_data}}))
        if not registered_managers:
            flash("We did not find other registered users", 'error')

        # Prepare managers data
        managers = get_managers_data(registered_managers)

        return render_template('user rights.html',managers=managers,dp=dp_str)
    
@app.route('/manage-user-rights-page/<email>/<company_name>')
def manage_user_rights_page(email,company_name):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
        manager = db.registered_managers.find_one({'email': email, 'company_name': company_name})
        add_properties = manager.get('add_properties', "no")
        add_tenants = manager.get('add_tenants', "no")
        update_tenant = manager.get('update_tenant', "no")
        edit_tenant = manager.get('edit_tenant', "no")
        manage_contracts = manager.get('manage_contracts', "no")
        add_stock = manager.get('add_stock', "no")
        update_stock = manager.get('update_stock', "no")
        update_sales = manager.get('update_sales', "no")
        inhouse = manager.get('inhouse', "no")
        view_stock_info = manager.get('view_stock_info', "no")
        view_revenue = manager.get('view_revenue', "no")
        view_sales = manager.get('view_revenue', "no")
        view_finance_dashboard = manager.get('view_finance_dashboard', "no")
        add_new_finance_account = manager.get('add_new_finance_account', "no")
        update_finance_account = manager.get('update_finance_account', "no")
        view_finance = manager.get('view_finance', "no")
        edit_finance = manager.get('edit_finance', "no")
        delete_finance = manager.get('delete_finance', "no")
        
        return render_template('user rights page.html', email=email,company_name=company_name,
                               add_properties=add_properties,add_tenants=add_tenants,
                               update_tenant=update_tenant,edit_tenant=edit_tenant,
                               manage_contracts=manage_contracts,add_stock=add_stock,
                               update_stock=update_stock,update_sales=update_sales,inhouse=inhouse,
                               view_stock_info=view_stock_info,view_revenue=view_revenue,view_sales=view_sales,
                               view_finance_dashboard=view_finance_dashboard,add_new_finance_account=add_new_finance_account,
                               update_finance_account=update_finance_account,view_finance=view_finance,
                               edit_finance=edit_finance,delete_finance=delete_finance,dp=dp_str)

@app.route('/user-rights-initiated', methods=["POST"])
def user_rights_initiated():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        email = request.form.get('email')
        company_name = request.form.get('company_name')
        add_properties = request.form.get("add_properties")
        add_tenants = request.form.get("add_tenants")
        update_tenant = request.form.get("update_tenant")
        edit_tenant = request.form.get("edit_tenant")
        manage_contracts = request.form.get('manage_contracts')
        add_stock = request.form.get('add_stock')
        update_stock = request.form.get('update_stock')
        update_sales = request.form.get('update_sales')
        inhouse = request.form.get('inhouse')
        view_stock_info = request.form.get('view_stock_info')
        view_revenue = request.form.get('view_revenue')
        view_sales = request.form.get('view_sales')
        view_finance_dashboard = request.form.get('view_finance_dashboard')
        add_new_finance_account = request.form.get('add_new_finance_account')
        update_finance_account = request.form.get('update_finance_account')
        view_finance = request.form.get('view_finance')
        edit_finance = request.form.get('edit_finance')
        delete_finance = request.form.get('delete_finance')

        update_fields = {}
        if add_properties:
            update_fields['add_properties'] = add_properties
        if add_tenants:
            update_fields['add_tenants'] = add_tenants
        if update_tenant:
            update_fields['update_tenant'] = update_tenant
        if edit_tenant:
            update_fields['edit_tenant'] = edit_tenant
        if manage_contracts:
            update_fields['manage_contracts'] = manage_contracts        
        if add_stock:
            update_fields['add_stock'] = add_stock
        if update_stock:
            update_fields['update_stock'] = update_stock
        if update_sales:
            update_fields['update_sales'] = update_sales
        if inhouse:
            update_fields['inhouse'] = inhouse
        if view_stock_info:
            update_fields['view_stock_info'] = view_stock_info
        if view_revenue:
            update_fields['view_revenue'] = view_revenue
        if view_sales:
            update_fields['view_sales'] = view_sales
        if view_finance_dashboard:
            update_fields['view_finance_dashboard'] = view_finance_dashboard
        if add_new_finance_account:
            update_fields['add_new_finance_account'] = add_new_finance_account
        if update_finance_account:
            update_fields['update_finance_account'] = update_finance_account
        if view_finance:
            update_fields['view_finance'] = view_finance
        if edit_finance:
            update_fields['edit_finance'] = edit_finance
        if delete_finance:
            update_fields['delete_finance'] = delete_finance

        if not update_fields:
            flash("No updates were made", 'error')
        else:
            # Update the document with the non-empty fields
            db.registered_managers.update_one({'email': email, 'company_name': company_name}, {'$set': update_fields})
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Change of user rights', 'email':email, 'timestamp': datetime.now()})
            flash("User rights were set successfully", 'success')
        return redirect('/manage-user-rights')
    
####ASSIGN PROPERTIES TO MANAGERS
@app.route('/assign-properties')
def assign_properties():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            
            # Get registered managers data
            registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': login_data}}))
            if not registered_managers:
                flash("We did not find other registered users", 'error')
                return redirect('/load-dashboard-page')

            # Prepare managers data
            managers = get_managers_data(registered_managers)

            return render_template('assign properties.html',managers=managers,dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/assign-properties-page/<name>/<email>/<company_name>')
def assign_properties_page(name,email,company_name):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            properties = db.property_managed.find({'company_name': company['company_name']}, {"propertyName": 1})
            property_names = [property['propertyName'] for property in properties]
            
            return render_template('assign properties page.html', property_names=property_names,name=name,email=email,company_name=company_name,dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/assign-properties-initiated', methods=["POST"])
def assign_properties_initiated():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            name = request.form.get('name')
            email = request.form.get('email')
            company_name = request.form.get('company_name')
            propertyName = request.form.get("propertyName")

            db.registered_managers.update_one(
                {'email': email, 'company_name': company_name}, 
                {'$addToSet': {'properties': propertyName}},
                upsert=True
            )
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Assign property', 'email':email, 'timestamp': datetime.now()})
            flash(f"{propertyName} was assigned to {name}", 'success')
            return redirect('/assign-properties')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

####UNASSIGN PROPERTIES FROM MANAGERS
@app.route('/unassign-properties')
def unassign_properties():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            
            # Get registered managers data
            registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': login_data}}))
            if not registered_managers:
                flash("We did not find other registered users", 'error')
                return redirect('/load-dashboard-page')

            # Prepare managers data
            managers = get_managers_data(registered_managers)

            return render_template('unassign properties.html',managers=managers,dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/unassign-properties-page/<name>/<email>/<company_name>')
def unassign_properties_page(name,email,company_name):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None
            property_assigned = db.registered_managers.find({'email': email, 'company_name': company_name})
            property_assigned_dict = {property for doc in property_assigned if 'properties' in doc for property in doc['properties']}
            
            return render_template('unassign properties page.html', property_names=property_assigned_dict,name=name,email=email,company_name=company_name,dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/unassign-properties-initiated', methods=["POST"])
def unassign_properties_initiated():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Property Management':
            name = request.form.get('name')
            email = request.form.get('email')
            company_name = request.form.get('company_name')
            propertyName = request.form.get("propertyName")

            db.registered_managers.update_one(
                {'email': email, 'company_name': company_name}, 
                {'$pull': {'properties': propertyName}}
            )
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Unassign property', 'email':email, 'timestamp': datetime.now()})
            flash(f"{propertyName} was unassigned from {name}", 'success')
            return redirect('/unassign-properties')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

# Function to rename the fourth field to 'details'
def rename_fourth_field(doc):
    keys = list(doc.keys())
    if len(keys) >= 4:
        # Fourth field's key (position 3 in zero-indexed list)
        fourth_key = keys[3]
        doc['details'] = doc.pop(fourth_key)
    if 'timestamp' in doc and isinstance(doc['timestamp'], datetime):
        doc['timestamp'] = doc['timestamp'].strftime('%Y-%m-%d %H:%M')
    return doc

# Function to convert timestamp to EAT
def convert_to_eat(timestamp):
    # Parse the timestamp (assuming it's in ISO 8601 format)
    utc_dt = datetime.fromisoformat(timestamp)
    # Define the UTC and EAT timezones
    utc = pytz.utc
    eat = pytz.timezone('Africa/Nairobi')
    # Localize the datetime to UTC
    utc_dt = utc.localize(utc_dt)
    # Convert the datetime to EAT
    eat_dt = utc_dt.astimezone(eat)
    # Return the formatted datetime string
    return eat_dt.strftime('%Y-%m-%d %H:%M')

##AUDIT LOGS
@app.route('/view-audit-logs')
def view_audit_logs():
    db, fs = get_db_and_fs()
    username = session.get('login_username')
    if username is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': username})
        dp_str = base64.b64encode(base64.b64decode(company.get('dp', ''))).decode() if 'dp' in company else None
        # is_manager = db.managers.find_one({'manager_email': company['email']}) is not None
        usernames = db.registered_managers.find({'company_name': company['company_name']}, {'username': 1})
        renamed_logs = []
        for user in usernames:
            audit_logs = db.audit_logs.find({'user': user['username']})
            for log in audit_logs:
                renamed_log = rename_fourth_field(log)
                timestamp = log.get('timestamp')
                log['timestamp'] = convert_to_eat(timestamp)
                renamed_logs.append(renamed_log)
        sorted_logs = sorted(renamed_logs, key=lambda x: x["timestamp"], reverse=True)
        logs_first_40 = sorted_logs[:40]
        return render_template('audit logs.html', audit_logs=logs_first_40, dp=dp_str)

# Function to rename the fourth field to 'details'
def format_time(doc):
    if 'timestamp' in doc and isinstance(doc['timestamp'], datetime):
        doc['timestamp'] = doc['timestamp'].strftime('%Y-%m-%d %H:%M')
    return doc

##LOGIN HISTORY
@app.route('/view-login-history')
def view_login_history():
    db, fs = get_db_and_fs()
    username = session.get('login_username')
    if username is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': username})
        dp_str = base64.b64encode(base64.b64decode(company.get('dp', ''))).decode() if 'dp' in company else None
        usernames = db.registered_managers.find({'company_name': company['company_name']}, {'username': 1})
        logindata = []
        for user in usernames:
            login_info = db.logged_in_data.find({'username': user['username']})
            for login in login_info:
                formated_time = format_time(login)
                timestamp = login.get('timestamp')
                login['timestamp'] = convert_to_eat(timestamp)
                logindata.append(formated_time)
        sorted_logins = sorted(logindata, key=lambda x: x["timestamp"], reverse=True)
        logindata_first_40 = sorted_logins[:40]
        return render_template('login history.html', logindata=logindata_first_40, dp=dp_str)

###DOANLOAD AUDIT DATA   
@app.route('/download-audit-logs', methods=["POST"])
def download_audit_logs():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    
    startdate_on_str = request.form.get("startdate")
    enddate_on_str = request.form.get("enddate")
    startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
    enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
    
    company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'address': 0, 'password': 0, 'auth': 0, 'dark_mode': 0})
    if not company:
        flash('Company not found', 'error')
        return redirect('/')
    
    usernames = db.registered_managers.find({'company_name': company['company_name']}, {'username': 1})
    renamed_logs = []

    for user in usernames:
        audit_logs = list(db.audit_logs.find({
            'user': user['username'],
            'timestamp': {'$gte': startdate, '$lte': enddate}
        }))
        if audit_logs:
            for log in audit_logs:
                renamed_log = rename_fourth_field(log)
                timestamp = log.get('timestamp')
                renamed_log['timestamp'] = convert_to_eat(timestamp)

                # Convert non-serializable types to strings
                for key, value in log.items():
                    if isinstance(value, ObjectId):
                        log[key] = str(value)
                    elif isinstance(value, (bytes, bytearray)):
                        log[key] = value.decode('utf-8')

                renamed_logs.append(renamed_log)
    
    # Sort logs by timestamp
    sorted_logs = sorted(renamed_logs, key=lambda x: x["timestamp"], reverse=True)

    # Create an Excel workbook
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Audit Logs"

    # Define headers based on sorted_logs keys
    headers = sorted_logs[0].keys() if sorted_logs else []
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx, value=header)

    # Write data rows
    for r_idx, log in enumerate(sorted_logs, start=2):
        for c_idx, header in enumerate(headers, start=1):
            ws.cell(row=r_idx, column=c_idx, value=log.get(header, ''))

    # Save the workbook to a BytesIO buffer
    output.seek(0)
    wb.save(output)
    wb.close()

    # Set the buffer position to the beginning
    output.seek(0)
    excel_data = output.read()

    # Create the response with the Excel file
    response = make_response(excel_data)
    response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_audit_logs_{startdate_on_str}_{enddate_on_str}.xlsx"
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    return response

###DOANLOAD LOGIN DATA   
@app.route('/download-login-data', methods=["POST"])
def download_login_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    
    startdate_on_str = request.form.get("startdate")
    enddate_on_str = request.form.get("enddate")
    startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
    enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
    company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'address': 0, 'password': 0, 'auth': 0, 'dark_mode': 0})
    usernames = db.registered_managers.find({'company_name': company['company_name']}, {'username': 1})
    logindata = []
    for user in usernames:
        login_info = list(db.logged_in_data.find({'username': user['username'], 'timestamp': {'$gte': startdate, '$lte': enddate}}))
        if login_info:
            for login in login_info:
                formated_time = format_time(login)
                timestamp = login.get('timestamp')
                login['timestamp'] = convert_to_eat(timestamp)

                # Convert non-serializable types to strings
                for key, value in login.items():
                    if isinstance(value, ObjectId):
                        login[key] = str(value)
                    elif isinstance(value, (bytes, bytearray)):
                        login[key] = value.decode('utf-8')
                        
                logindata.append(formated_time)
    
    # Sort logins
    sorted_logins = sorted(logindata, key=lambda x: x["timestamp"], reverse=True)

    # Create an Excel workbook
    output = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Login Data"
    
    # Define headers based on sorted_logs keys
    headers = sorted_logins[0].keys() if sorted_logins else []
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=1, column=col_idx, value=header)
    
    # Write data rows
    for r_idx, log in enumerate(sorted_logins, start=2):
        for c_idx, header in enumerate(headers, start=1):
            ws.cell(row=r_idx, column=c_idx, value=log.get(header, ''))
    
    # Save the workbook to a BytesIO buffer
    output.seek(0)
    wb.save(output)
    wb.close()

    # Set the buffer position to the beginning
    output.seek(0)
    excel_data = output.read()

    # Create the response
    response = make_response(excel_data)
    response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_login_data_{startdate_on_str}_{enddate_on_str}.xlsx"
    response.headers['Content-Type'] = 'application/zip'

    return response

#####ACTIVATE SENDING EMAILS
@app.route('/activate sending emails/<send_emails>')
def activate_send_emails(send_emails):
    db, fs = get_db_and_fs()
    send_emails_state = db.send_emails.find_one()
    if send_emails_state is None:
        db.send_emails.insert_one({'emails': send_emails})
        if send_emails == "yes":
            flash(f"Emails have been activated", 'success')
        else:
            flash(f"Emails have been deactivated", 'success')
    else:
        if send_emails == "yes":
            db.send_emails.update_one({'emails': "no"}, {'$set': {'emails': send_emails}})
            flash(f"Emails have been activated", 'success')
        else:
            db.send_emails.update_one({'emails': "yes"}, {'$set': {'emails': send_emails}})
            flash(f"Emails have been deactivated", 'success')
    session['send_emails'] = send_emails
    return render_template("managers accounts.html")


###############ENTREPRISE RESOURCE PLANNING (ERP)############################
@app.route('/add-new-stock', methods=['POST'])
def add_new_stock():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                    'password': 0, 'auth': 0, 'dark_mode': 0})
                
            all_items = request.json.get('items', [])  # Access the JSON data sent from the client
            skipped_items = []  # List to hold names of items that were not added
            added_items = []  # List to hold names of items that were successfully added
            timestamp = datetime.now()

            for item in all_items:
                item['itemName'] = item.get('itemName', '').strip()
                
                try:
                    # Convert 'quantity' and 'unitPrice' to floats
                    item['quantity'] = float(item.get('quantity', 0))
                    item['available_quantity'] = item['quantity']
                    item['unitPrice'] = float(item.get('unitPrice', 0))
                    item['stockDate'] = datetime.strptime(item.get('stockDate', ''), '%Y-%m-%d')

                    # Add 'totalPrice' field which is 'unitPrice' * 'quantity'
                    item['totalPrice'] = item['unitPrice'] * item['quantity']
                    item['company_name'] = company.get('company_name', '')
                    item['timestamp'] = timestamp

                    # Check if the item already exists in the database
                    existing_item = db.inventories.find_one({
                        'itemName': item['itemName'],
                        'company_name': item['company_name']
                    })

                    if existing_item:
                        skipped_items.append(item['itemName'])  # Add the name of the skipped item
                        continue  # Skip this iteration and don't add the existing item

                    # Insert the new stock entry into MongoDB
                    db.inventories.insert_one(item)
                    db.audit_logs.insert_one({
                        'user': login_data,
                        'Activity': 'Added new item to stock',
                        'Item': item['itemName'],
                        'timestamp': datetime.now()
                    })
                    added_items.append(item['itemName'])
                except (ValueError, TypeError) as e:
                    # Log or handle the exception as needed
                    flash(f"Error processing item {item.get('itemName', 'unknown')}: {e}", 'error')
                    skipped_items.append(item.get('itemName', 'unknown'))

            message = ""
            if added_items:
                message += '. The following items were added: ' + ', '.join(added_items)
                flash(message, 'success')
            if skipped_items:
                message_skipped = 'The following items were not added because they already exist: ' + ', '.join(skipped_items)
                flash(message_skipped, 'error')

            return jsonify({'redirect': url_for('add_new_stock_page')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/update-new-stock', methods=['POST'])
def update_new_stock():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                    'password': 0, 'auth': 0, 'dark_mode': 0})
                
            all_items = request.json.get('items', [])  # Access the JSON data sent from the client
            timestamp = datetime.now()

            for item in all_items:
                item['itemName'] = item.get('itemName', '').strip()

                try:
                    # Convert 'quantity' and 'unitPrice' to floats
                    item['quantity'] = float(item.get('quantity', 0))
                    item['unitPrice'] = float(item.get('unitPrice', 0))
                    item['stockDate'] = datetime.strptime(item.get('stockDate', ''), '%Y-%m-%d')
                    item['company_name'] = company.get('company_name', '')
                    item['status'] = "updated stock"
                    item['timestamp'] = timestamp

                    # Check if the item already exists in the database
                    existing_item = db.inventories.find_one({
                        'itemName': item['itemName'],
                        'company_name': item['company_name']
                    })

                    if existing_item:
                        if 'available_quantity' in existing_item:
                            if existing_item['available_quantity'] > 0:
                                # Add 'totalPrice' field which is 'unitPrice' * 'quantity'
                                item['totalPrice'] = item['quantity'] * item['unitPrice']
                                item['unitOfMeasurement'] = existing_item.get('unitOfMeasurement', '')
                                item['oldTotalPrice'] = existing_item.get('totalPrice', 0)
                                item['oldUnitPrice'] = existing_item.get('unitPrice', 0)
                                new_available_quantity = existing_item['available_quantity'] + item['quantity']
                                item['available_quantity'] = new_available_quantity
                            else:
                                new_available_quantity = existing_item['available_quantity'] + item['quantity']
                                item['available_quantity'] = new_available_quantity
                                item['totalPrice'] = item['quantity'] * item['unitPrice']
                        else:
                            new_available_quantity = item['quantity']
                            item['available_quantity'] = new_available_quantity
                            item['totalPrice'] = item['quantity'] * item['unitPrice']

                        # Insert the updated stock entry into MongoDB
                        db.inventories.insert_one(item)
                        db.audit_logs.insert_one({
                            'user': login_data,
                            'Activity': 'Updated item in stock',
                            'Item': item['itemName'],
                            'timestamp': datetime.now()
                        })
                        db.inventories.delete_one({'_id': existing_item['_id']})
                        existing_item.pop('_id', None)
                        db.old_inventories.insert_one(existing_item)
                    else:
                        # Handle case where item does not exist if necessary
                        flash(f"Item {item['itemName']} does not exist.", 'error')
                except (ValueError, TypeError) as e:
                    flash(f"Error processing item {item.get('itemName', 'unknown')}: {e}", 'error')

            flash('Stock updated successfully', 'success')
            return jsonify({'redirect': url_for('update_existing_stock')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/update-sale', methods=['POST'])
def update_sale():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                    'password': 0, 'auth': 0, 'dark_mode': 0})
                
            all_items = request.json.get('items', [])  # Access the JSON data sent from the client
            out_of_stock_items = []
            over_quantified = []
            timestamp = datetime.now()
            updates = 0
            for item in all_items:
                try:
                    item['quantity'] = float(item.get('quantity', 0))
                    item['unitPrice'] = float(item.get('unitPrice', 0))
                    item['saleDate'] = datetime.strptime(item.get('saleDate', ''), '%Y-%m-%d')
                    item['company_name'] = company.get('company_name', '')
                    item['timestamp'] = timestamp

                    existing_item = db.inventories.find_one({
                        'itemName': item['itemName'],
                        'company_name': company['company_name']
                    })

                    if existing_item:
                        if item['saleDate'] >= existing_item['stockDate']:
                            updates = 1
                            if 'available_quantity' in existing_item:
                                if existing_item['available_quantity'] <= 0:
                                    out_of_stock_items.append(item['itemName'])
                                    continue
                                if item['quantity'] > existing_item['available_quantity']:
                                    over_quantified.append(item['itemName'])
                                    continue
                                revenue = item['quantity'] * item['unitPrice']
                                available_quantity = existing_item['available_quantity'] - item['quantity']
                                item['revenue'] = revenue
                                item['stockDate'] = existing_item['stockDate']
                            else:
                                if item['quantity'] > existing_item['quantity']:
                                    over_quantified.append(item['itemName'])
                                    continue
                                revenue = item['quantity'] * item['unitPrice']
                                available_quantity = existing_item['quantity'] - item['quantity']
                                item['revenue'] = revenue
                                item['stockDate'] = existing_item['stockDate']
                            
                            item['stock_id'] = existing_item['_id']

                            db.stock_sales.insert_one(item)
                            db.audit_logs.insert_one({
                                'user': login_data,
                                'Activity': 'Added a new sale',
                                'Item': item['itemName'],
                                'timestamp': datetime.now()
                            })
                            db.inventories.update_one({'_id': existing_item['_id']}, {'$set': {'available_quantity': available_quantity}})
                        else:
                            flash(f"Sales date must be newer than stock date for {item['itemName']}.", 'error')
                    else:
                        flash(f"Item {item['itemName']} does not exist.", 'error')
                except (ValueError, TypeError) as e:
                    flash(f"Error processing item {item.get('itemName', 'unknown')}: {e}", 'error')
            
            if updates ==1:
                message = 'Sales updated successfully'
                flash(message, 'success')

            if out_of_stock_items:
                flash(f'The following items are out of stock: {", ".join(out_of_stock_items)}', 'error')
            if over_quantified:
                flash(f'Enter smaller quantities for the following items: {", ".join(over_quantified)}', 'error')

            return jsonify({'redirect': url_for('update_sales_page')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/in-house-use', methods=['POST'])
def inhouse():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                    'password': 0, 'auth': 0, 'dark_mode': 0})
                
            all_items = request.json.get('items', [])  # Access the JSON data sent from the client

            # Initialize empty lists for item details
            itemNames = []
            itemQuantities = []
            itemStockDates = []
            itemUnitPrices = []
            itemOldUnitPrices = []
            
            # Extract details from the first item
            if all_items:
                productName = all_items[0].get('productName', '')
                productQuantity = float(all_items[0].get('productQuantity', 0))
                productPrice = float(all_items[0].get('productPrice', 0))
                useDate = datetime.strptime(all_items[0].get('useDate', ''), '%Y-%m-%d')
                company_name = company.get('company_name', '')

                out_of_stock_items = []
                over_quantified = []
                in_stockID = []
                in_stockQty = []

                for item in all_items:
                    itemNames.append(item.get('itemName', ''))
                    itemQuantity = float(item.get('itemQuantity', 0))
                    itemQuantities.append(itemQuantity)

                    # Check if the item exists in the database
                    existing_item = db.inventories.find_one({
                        'itemName': item['itemName'],
                        'company_name': company_name
                    })

                    if existing_item:
                        if 'available_quantity' in existing_item:
                            if existing_item['available_quantity'] <= 0:
                                out_of_stock_items.append(item['itemName'])
                                flash(f'Item {item["itemName"]} is out of stock', 'error')
                                continue
                            if itemQuantity > existing_item['available_quantity']:
                                over_quantified.append(item['itemName'])
                                flash(f'Quantity for item {item["itemName"]} is too high', 'error')
                                continue
                            else:
                                available_quantity = existing_item['available_quantity'] - itemQuantity
                                itemStockDates.append(existing_item['stockDate'])
                                in_stockID.append(existing_item['_id'])
                                in_stockQty.append(available_quantity)
                                itemUnitPrices.append(existing_item['unitPrice'])
                                itemOldUnitPrices.append(existing_item.get('oldUnitPrice', 0))
                                flash(f'Inhouse use of {item["itemName"]} updated successfully', 'success')
                        else:
                            if itemQuantity > existing_item['quantity']:
                                over_quantified.append(item['itemName'])
                                flash(f'Quantity for item {item["itemName"]} is too high', 'error')
                            else:
                                available_quantity = existing_item['quantity'] - itemQuantity
                                itemStockDates.append(existing_item['stockDate'])
                                in_stockID.append(existing_item['_id'])
                                in_stockQty.append(available_quantity)
                                itemUnitPrices.append(existing_item['unitPrice'])
                                itemOldUnitPrices.append(existing_item.get('oldUnitPrice', 0))
                                flash(f'Inhouse use of {item["itemName"]} updated successfully', 'success')
                    else:
                        flash(f"Item {item['itemName']} does not exist.", 'error')

                if out_of_stock_items:
                    flash(f'The following items are out of stock: {", ".join(out_of_stock_items)}', 'error')
                if over_quantified:
                    flash(f'Please enter smaller quantities for the following items: {", ".join(over_quantified)}', 'error')

                if not out_of_stock_items and not over_quantified:
                    document = {
                        'productName': productName,
                        'productQuantity': productQuantity,
                        'productPrice': productPrice,
                        'useDate': useDate,
                        'itemName': itemNames,
                        'itemQuantity': itemQuantities,
                        'itemUnitPrices': itemUnitPrices,
                        'itemOldUnitPrices': itemOldUnitPrices,
                        'itemStockDates': itemStockDates,
                        'company_name': company_name
                    }
                    for id, available_quantity in zip(in_stockID, in_stockQty):
                        db.inventories.update_one({'_id': id}, {'$set': {'available_quantity': available_quantity}})
                    db.inhouse.insert_one(document)
                    db.audit_logs.insert_one({
                        'user': login_data,
                        'Activity': 'Inhouse production',
                        'Item': 'Items',
                        'timestamp': datetime.now()
                    })

            return jsonify({'redirect': url_for('update_production_activity')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/in-house-used-items', methods=['POST'])
def inhouse_used_items():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Please login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                    'password': 0, 'auth': 0, 'dark_mode': 0})
                
            all_items = request.json.get('items', [])  # Access the JSON data sent from the client

            # Initialize lists for item details
            itemNames = []
            itemQuantities = []
            itemStockDates = []
            itemUseDates = []
            itemUnitPrices = []
            itemOldUnitPrices = []
            
            company_name = company.get('company_name', '')

            out_of_stock_items = []
            over_quantified = []
            in_stockID = []
            in_stockQty = []

            for item in all_items:
                itemName = item.get('usedItemName', '')
                itemQuantity = float(item.get('usedItemQuantity', 0))
                use_date = item.get('usedUseDate', '')
                useDate = datetime.strptime(use_date, '%Y-%m-%d') if use_date else None

                itemNames.append(itemName)
                itemQuantities.append(itemQuantity)
                itemUseDates.append(useDate)

                existing_item = db.inventories.find_one({
                    'itemName': itemName,
                    'company_name': company_name
                })

                if existing_item:
                    if 'available_quantity' in existing_item:
                        if existing_item['available_quantity'] <= 0:
                            out_of_stock_items.append(itemName)
                            flash(f'Item {itemName} is out of stock', 'error')
                            continue
                        if itemQuantity > existing_item['available_quantity']:
                            over_quantified.append(itemName)
                            flash(f'Quantity for item {itemName} is too high', 'error')
                            continue
                        available_quantity = existing_item['available_quantity'] - itemQuantity
                        itemStockDates.append(existing_item['stockDate'])
                        in_stockID.append(existing_item['_id'])
                        in_stockQty.append(available_quantity)
                        itemUnitPrices.append(existing_item['unitPrice'])
                        itemOldUnitPrices.append(existing_item.get('oldUnitPrice', 0))
                        flash(f'Inhouse use of {itemName} updated successfully', 'success')
                    else:
                        if itemQuantity > existing_item['quantity']:
                            over_quantified.append(itemName)
                            flash(f'Quantity for item {itemName} is too high', 'error')
                        else:
                            available_quantity = existing_item['quantity'] - itemQuantity
                            itemStockDates.append(existing_item['stockDate'])
                            in_stockID.append(existing_item['_id'])
                            in_stockQty.append(available_quantity)
                            itemUnitPrices.append(existing_item['unitPrice'])
                            itemOldUnitPrices.append(existing_item.get('oldUnitPrice', 0))
                            flash(f'Inhouse use of {itemName} updated successfully', 'success')
                else:
                    flash(f'Item {itemName} does not exist', 'error')

            if out_of_stock_items:
                flash(f'The following items are out of stock: {", ".join(out_of_stock_items)}', 'error')
            if over_quantified:
                flash(f'Please enter smaller quantities for the following items: {", ".join(over_quantified)}', 'error')

            if not out_of_stock_items and not over_quantified:
                document = {
                    'itemName': itemNames,
                    'itemQuantity': itemQuantities,
                    'itemUnitPrices': itemUnitPrices,
                    'itemOldUnitPrices': itemOldUnitPrices,
                    'itemStockDates': itemStockDates,
                    'useDate': itemUseDates,
                    'company_name': company_name
                }
                for id, available_quantity in zip(in_stockID, in_stockQty):
                    db.inventories.update_one({'_id': id}, {'$set': {'available_quantity': available_quantity}})
                db.inhouse_use.insert_one(document)
                db.audit_logs.insert_one({
                    'user': login_data,
                    'Activity': 'Inhouse use of items',
                    'Item': 'Items',
                    'timestamp': datetime.now()
                })

            return jsonify({'redirect': url_for('update_inhouse_use_page')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/revenue-details')
def revenue_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            
            subscription = db.managers.find_one({'name': company['company_name']}, {'account_type': 1, 'manager_email': 1, '_id': 0})
            account_type = subscription['account_type']
            # Remove any empty strings from the list
            account_type = [atype for atype in account_type if atype]

            if 'Enterprise Resource Planning' in account_type:
                company_name = company['company_name']
                twelve_months_ago = datetime.now() - timedelta(days=365)
                pipeline = [
                    {
                        '$match': {
                            'company_name': company_name,
                            'stockDate': {'$gte': twelve_months_ago}
                        }
                    },
                    {
                        '$group': {
                            '_id': {'itemName': '$itemName', 'stockDate': '$stockDate'},
                            'totalRevenue': {'$sum': '$revenue'},
                            'quantitysold': {'$sum': '$quantity'}
                        }
                    },
                    {
                        '$lookup': {
                            'from': 'inventories',
                            'let': {'itemName': '$_id.itemName', 'stockDate': '$_id.stockDate'},
                            'pipeline': [
                                {
                                    '$match': {
                                        '$expr': {
                                            '$and': [
                                                {'$eq': ['$itemName', '$$itemName']},
                                                {'$eq': ['$company_name', company_name]},
                                                {'$gte': ['$stockDate', twelve_months_ago]}
                                            ]
                                        }
                                    }
                                },
                                {
                                    '$project': {
                                        '_id': 0,
                                        'quantity': 1,
                                        'unitPrice': 1,
                                        'stockDate': 1,
                                        'totalPrice': {
                                            '$add': [
                                                '$totalPrice',
                                                {'$ifNull': ['$oldTotalPrice', 0]}
                                            ]
                                        }
                                    }
                                }
                            ],
                            'as': 'inventoryDetails'
                        }
                    },
                    {
                        '$match': {
                            'inventoryDetails': {'$ne': []}
                        }
                    }
                ]

                revenue_info = list(db.stock_sales.aggregate(pipeline))
                revenue_info.sort(key=lambda x: x['_id']['itemName'])
                dp = company.get('dp')
                dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
                return render_template('revenue info.html', revenue_info = revenue_info, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/sales-details')
def sales_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            
            subscription = db.managers.find_one({'name': company['company_name']}, {'account_type': 1, 'manager_email': 1, '_id': 0})
            account_type = subscription['account_type']
            # Remove any empty strings from the list
            account_type = [atype for atype in account_type if atype]

            if 'Enterprise Resource Planning' in account_type:
                company_name = company['company_name']

                twelve_months_ago = datetime.now() - timedelta(days=365)

                sales_info = list(db.stock_sales.find({'company_name': company_name, 'saleDate': {'$gte': twelve_months_ago}}))
                sales_info.sort(key=lambda x: x['saleDate'], reverse=True)
                dp = company.get('dp')
                dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
                return render_template('sales info.html', sales_info = sales_info, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/stock-details')
def stock_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            
            subscription = db.managers.find_one({'name': company['company_name']}, {'account_type': 1, 'manager_email': 1, '_id': 0})
            account_type = subscription['account_type']
            # Remove any empty strings from the list
            account_type = [atype for atype in account_type if atype]

            if 'Enterprise Resource Planning' in account_type:
                company_name = company['company_name']
                stock_info = list(db.inventories.find({'company_name': company_name}))
                stock_info.sort(key=lambda x: x.get('timestamp', x['stockDate']), reverse=True)
                stock_info.sort(key=lambda x: x['itemName'])

                dp = company.get('dp')
                dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
                return render_template('stock info.html', stock_info = stock_info, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
        
@app.route('/stock-history-details')
def stock_history_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            
            subscription = db.managers.find_one({'name': company['company_name']}, {'account_type': 1, 'manager_email': 1, '_id': 0})
            account_type = subscription['account_type']
            # Remove any empty strings from the list
            account_type = [atype for atype in account_type if atype]

            if 'Enterprise Resource Planning' in account_type:
                company_name = company['company_name']
                twelve_months_ago = datetime.now() - timedelta(days=365)
                stock_info = list(db.old_inventories.find({'company_name': company_name, 'stockDate': {'$gte': twelve_months_ago}}))
                stock_info.sort(key=lambda x: x.get('timestamp', x['stockDate']), reverse=True)
                stock_info.sort(key=lambda x: x['itemName'])

                dp = company.get('dp')
                dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
                return render_template('stock history.html', stock_info = stock_info, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/inhouse-item-use-details')
def inhouse_items_use_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            
            company_name = company['company_name']
            twelve_months_ago = datetime.now() - timedelta(days=365)
            inhouse_item_use = list(db.inhouse_use.find({'company_name': company_name, 'useDate': {'$gte': twelve_months_ago}}))
            inhouse_item_use.sort(key=lambda x: max(x['useDate']), reverse=True)

            available_itemNames = []
            items_to_update = []
            available_items = list(db.inventories.find({'company_name': company['company_name']}))
            if len(available_items) != 0:
                for item in available_items:
                    if 'available_quantity' in item:
                        if item['available_quantity'] > 0:
                            available_itemNames.append(item['itemName'])
                    else:
                        available_itemNames.append(item['itemName'])
                for item in available_items:
                    items_to_update.append(item['itemName'])
            dp = company.get('dp')
            dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
            return render_template('inhouse item use info.html', inhouse_item_use = inhouse_item_use, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/stock-overview', methods=["GET", "POST"])
def stock_overview():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            # Clear sessions
            session.pop("profits_chart", None)
            session.pop("loss_chart", None)
            session.pop("revenue_and_qty_chart", None)
            session.pop("monthly_profits_chart", None)
            session.pop("inhouse_costs_chart", None)
            session.pop("inhouse_revenue_chart", None)

            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            company_name = company['company_name']

            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")

            if startdate_on_str and enddate_on_str:
                start_of_previous_month = datetime.strptime(startdate_on_str, '%Y-%m-%d')
                first_day_of_current_month = datetime.strptime(enddate_on_str, '%Y-%m-%d')
            else:
                # Get today's date
                today = datetime.today()

                # Get the first day of the current month
                start_of_previous_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                # Calculate the first day of the next month
                if today.month == 12:  # If it's December, the next month is January of the next year
                    first_day_of_current_month = today.replace(year=today.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                else:
                    first_day_of_current_month = today.replace(month=today.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

            pipeline = [
                {
                    '$match': {
                        'company_name': company_name,
                        'stockDate': {
                            '$gte': start_of_previous_month,
                            '$lt': first_day_of_current_month
                        }
                    }
                },
                {
                    '$group': {
                        '_id': {'itemName': '$itemName','stockDate': '$stockDate'},
                        'totalRevenue': {'$sum': '$revenue'},
                        'quantitysold': {'$sum': '$quantity'}
                    }
                },
                {
                    '$lookup': {
                        'from': 'inventories',
                        'let': {'itemName': '$_id.itemName', 'stockDate': '$_id.stockDate'},
                        'pipeline': [
                            {
                                '$match': {
                                    '$expr': {
                                        '$and': [
                                            {'$eq': ['$itemName', '$$itemName']},
                                            {'$eq': ['$company_name', company_name]},
                                            { '$gte': ['$stockDate', start_of_previous_month] },
                                            { '$lt': ['$stockDate', first_day_of_current_month] }
                                        ]
                                    }
                                }
                            },
                            {
                                '$project': {
                                    '_id': 0,
                                    'quantity': 1,
                                    'unitPrice': 1,
                                    'stockDate': 1,
                                    'totalPrice': {
                                        '$add': [
                                            '$totalPrice',
                                            {'$ifNull': ['$oldTotalPrice', 0]}
                                        ]
                                    }
                                }
                            }
                        ],
                        'as': 'inventoryDetails'
                    }
                }
            ]

            revenue_info = list(db.stock_sales.aggregate(pipeline))
            item_names = []
            quantities_sold = []
            quantities_stocked = []
            total_revenues = []
            total_prices = []
            profits = []

            for record in revenue_info:
                item_names.append(record['_id']['itemName'])
                quantities_sold.append(record['quantitysold'])
                total_revenues.append(record['totalRevenue'])

                # Initialize variables for each iteration
                quantities_stocked_iter = 0
                total_price_iter = 0
                profit_iter = 0

                # Check if 'inventoryDetails' is in record and has the necessary structure
                if 'inventoryDetails' in record and record['inventoryDetails']:
                    quantity_stocked = record['inventoryDetails'][0].get('quantity', 0)
                    quantities_stocked_iter = quantity_stocked
                    unitPrice = record['inventoryDetails'][0].get('unitPrice', 0)
                    quantitysold = record['quantitysold']
                    total_price_iter = unitPrice * quantitysold
                    profit_iter = record['totalRevenue'] - total_price_iter

                # Append values for this iteration to the lists
                quantities_stocked.append(quantities_stocked_iter)
                total_prices.append(total_price_iter)
                profits.append(profit_iter)

            # Create the DataFrame
            df_ungrouped = pd.DataFrame({
                'Item Name': item_names,
                'Quantity Sold': quantities_sold,
                'Quantity Stocked': quantities_stocked,
                'Total Revenue': total_revenues,
                'Total Price': total_prices,
                'Profit': profits
            })

            # Group by 'Item Name' and aggregate using sum
            df = df_ungrouped.groupby('Item Name', as_index=False).agg({
                'Quantity Sold': 'sum',
                'Quantity Stocked': 'sum',
                'Total Revenue': 'sum',
                'Total Price': 'sum',
                'Profit': 'sum'
            })

            #####PLOTS
            #profits and losses
            # Filter positive profits
            positive_profits_df = df[df['Profit'] > 0]
            if not positive_profits_df.empty:
                session['profits_chart'] = 'profits_chart'
            
            profits_chart = {
                'labels': positive_profits_df['Item Name'].tolist(),
                'values': positive_profits_df['Profit'].tolist()
            }

            # Filter negative profits
            negative_profits_df = df[df['Profit'] < 0]
            if not negative_profits_df.empty:
                session['loss_chart'] = 'loss_chart'
            negative_profits_df['Profit'] = -1*negative_profits_df['Profit']

            Losses_chart = {
                'labels': negative_profits_df['Item Name'].tolist(),
                'values': negative_profits_df['Profit'].tolist()
            }

            ##total revenue
            if not df.empty:
                session['revenue_and_qty_chart'] = 'revenue_and_qty_chart'

            revenue = {
                'labels': df['Item Name'].tolist(),
                'values': df['Total Revenue'].tolist()
            }

            ##Quantity sold

            quantity_sold_stocked = {
                'labels': df['Item Name'].tolist(),
                'values': df['Quantity Sold'].tolist()
            }

            ###PROFIT TRENDS
            twelve_months_ago = datetime.now() - timedelta(days=365)
            pipeline_profits = [
                {
                    '$match': {
                        'company_name': company_name,
                        'stockDate': {'$gte': twelve_months_ago}
                    }
                },
                {
                    '$group': {
                        '_id': {'itemName': '$itemName', 'stockDate': '$stockDate'},
                        'totalRevenue': {'$sum': '$revenue'},
                        'quantitysold': {'$sum': '$quantity'}
                    }
                },
                {
                    '$lookup': {
                        'from': 'inventories',
                        'let': {'itemName': '$_id.itemName', 'stockDate': '$_id.stockDate'},
                        'pipeline': [
                            {
                                '$match': {
                                    '$expr': {
                                        '$and': [
                                            {'$eq': ['$itemName', '$$itemName']},
                                            {'$eq': ['$company_name', company_name]},
                                            {'$gte': ['$stockDate', twelve_months_ago]}
                                        ]
                                    }
                                }
                            },
                            {
                                '$project': {
                                    '_id': 0,
                                    'quantity': 1,
                                    'unitPrice': 1,
                                    'stockDate': 1,
                                    'totalPrice': {
                                        '$add': [
                                            '$totalPrice',
                                            {'$ifNull': ['$oldTotalPrice', 0]}
                                        ]
                                    }
                                }
                            }
                        ],
                        'as': 'inventoryDetails'
                    }
                }
            ]
            profit_info = list(db.stock_sales.aggregate(pipeline_profits))

            profit_item_names = []
            profit_data = []
            profit_stock_dates = []


            for profit_record in profit_info:
                if 'inventoryDetails' in profit_record and profit_record['inventoryDetails']:
                    profit_item_names.append(profit_record['_id']['itemName'])
                    profit_data.append(profit_record['totalRevenue'] - profit_record['inventoryDetails'][0]['totalPrice'])
                    profit_stock_dates.append(profit_record['_id']['stockDate'])

            # Create the DataFrame
            profit_info_df = pd.DataFrame({
                'Item Name': profit_item_names,
                'Profit': profit_data,
                'Stock Date': profit_stock_dates
            })

            # Convert 'Stock Date' to datetime
            profit_info_df['Stock Date'] = pd.to_datetime(profit_info_df['Stock Date'])

            # Group by month and calculate the sum of profits
            monthly_profits = profit_info_df.groupby(profit_info_df['Stock Date'].dt.to_period('M'))['Profit'].sum()

            # Create a DataFrame with month names
            monthly_profits_df = pd.DataFrame({
                'Month': monthly_profits.index.to_timestamp().strftime('%B'),
                'Monthly Profit': monthly_profits
            })

            # Create the line chart
            if not monthly_profits_df.empty:
                session['monthly_profits_chart'] = 'monthly_profits_chart'

            trended_profit = {
                'labels': monthly_profits_df['Month'].tolist(),
                'values': monthly_profits_df['Monthly Profit'].tolist()
            }

            del df_ungrouped, df, positive_profits_df, negative_profits_df, profit_info_df, monthly_profits, monthly_profits_df
            gc.collect()
            dp = company.get('dp')
            dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
            return render_template('stock dashboard.html',profits_chart=profits_chart,Losses_chart=Losses_chart,revenue=revenue,
                                quantity_sold_stocked=quantity_sold_stocked,trended_profit=trended_profit,
                                start_of_previous_month=start_of_previous_month,
                                first_day_of_current_month=first_day_of_current_month, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

###DOANLOAD STOCK DATA   
@app.route('/download-stock-data', methods=["POST"])
def download_stock_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')

            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            current_stock = db.inventories.find(
                {'company_name': company['company_name'], 'stockDate': {'$gte': startdate, '$lte': enddate}},
                {'_id': 0, 'company_name': 0, 'available_quantity': 0}
            )
            old_stock = db.old_inventories.find(
                {'company_name': company['company_name'], 'stockDate': {'$gte': startdate, '$lte': enddate}},
                {'_id': 0, 'company_name': 0, 'available_quantity': 0}
            )
            combined_stock = list(current_stock) + list(old_stock)

            # Sort data by stockDate in descending order
            sorted_combined_stock = sorted(combined_stock, key=lambda x: x["stockDate"], reverse=True)

            # Create Excel file
            excel_buffer = BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "Stock Data"

            # Write header row
            headers = ['Item Name', 'Stocked Quantity', 'Unit Of Measurement', 'Unit Buying Price', 'Stock Date', 'Total Buying Price']
            ws.append(headers)

            # Write data rows
            for record in sorted_combined_stock:
                row = [
                    record.get('itemName', ''),
                    record.get('quantity', 0),
                    record.get('unitOfMeasurement', ''),
                    record.get('unitPrice', 0),
                    record.get('stockDate', '').strftime('%Y-%m-%d') if isinstance(record.get('stockDate'), datetime) else '',
                    record.get('totalPrice', 0)
                ]
                ws.append(row)

            wb.save(excel_buffer)
            excel_buffer.seek(0)

            # Create the response
            response = make_response(excel_buffer.getvalue())
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Stock_Data_{startdate_on_str}_{enddate_on_str}.xlsx"
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

            # Clean up
            del wb
            del excel_buffer
            gc.collect()

            return response
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
###DOANLOAD REVENUE DATA   
@app.route('/download-revenue-data', methods=["POST"])
def download_revenue_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            

            company_name = company['company_name']

            pipeline = [
                {
                    '$match': {
                        'company_name': company_name,
                        'stockDate': {
                            '$gte': startdate,
                            '$lt': enddate
                        }
                    }
                },
                {
                    '$group': {
                        '_id': {'itemName': '$itemName', 'stockDate': '$stockDate'},
                        'totalRevenue': {'$sum': '$revenue'},
                        'quantitysold': {'$sum': '$quantity'}
                    }
                },
                {
                    '$lookup': {
                        'from': 'inventories',
                        'let': {'itemName': '$_id.itemName', 'stockDate': '$_id.stockDate'},
                        'pipeline': [
                            {
                                '$match': {
                                    '$expr': {
                                        '$and': [
                                            {'$eq': ['$itemName', '$$itemName']},
                                            {'$eq': ['$company_name', company_name]},
                                            { '$gte': ['$stockDate', startdate] },
                                            { '$lt': ['$stockDate', enddate] }
                                        ]
                                    }
                                }
                            },
                            {
                                '$project': {
                                    '_id': 0,
                                    'quantity': 1,
                                    'unitPrice': 1,
                                    'stockDate': 1,
                                    'totalPrice': {
                                        '$add': [
                                            '$totalPrice',
                                            {'$ifNull': ['$oldTotalPrice', 0]}
                                        ]
                                    }
                                }
                            }
                        ],
                        'as': 'inventoryDetails'
                    }
                }
            ]

            itemNames = []
            stockDates = []
            stockQtys = []
            unitBuyingPrices = []
            totalBuyingPrices = []
            quantitiesSold = []
            totalRevenues = []
            profits = []
            revenue_info = list(db.stock_sales.aggregate(pipeline))

            if len(revenue_info) != 0:
                for info in revenue_info:
                    itemNames.append(info['_id']['itemName'])
                    for detail in info['inventoryDetails']:
                        stockDates.append(detail['stockDate'])
                        stockQtys.append(detail['quantity'])
                        unitBuyingPrices.append(detail['unitPrice'])
                        totalBuyingPrices.append(detail['totalPrice'])

                        profit = info['totalRevenue'] - detail['totalPrice']
                        profits.append(profit)
                    quantitiesSold.append(info['quantitysold'])
                    totalRevenues.append(info['totalRevenue'])

            revenue_info = pd.DataFrame({
                'Item Name': itemNames,
                'Stock Date': stockDates,
                'Stock Quantity': stockQtys,
                'Unit Buying Price': unitBuyingPrices,
                'Total Buying Price': totalBuyingPrices,
                'Sold Quantity': quantitiesSold,
                'Total Revenue': totalRevenues,
                'Profit/Loss': profits
            })

            df = pd.DataFrame(revenue_info)

            # Create an in-memory buffer for the Excel file
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Revenue Data', index=False)
            excel_buffer.seek(0)

            del df, revenue_info
            gc.collect()
            # Create the response
            response = make_response(excel_buffer.getvalue())
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Revenue_Data_{startdate_on_str}_{enddate_on_str}.xlsx"
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

            return response
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
###DOANLOAD SALES DATA   
@app.route('/download-sales-data', methods=["POST"])
def download_sales_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            company_name = company['company_name']

            sales_info = list(db.stock_sales.find({
                'company_name': company_name,
                'saleDate': {'$gte': startdate, '$lte': enddate}
            }, {
                '_id': 0,
                'company_name': 0,
                'stockDate': 0
            }))

            # Sort sales info by saleDate in descending order
            sorted_sales_info = sorted(sales_info, key=lambda x: x["saleDate"], reverse=True)

            # Create Excel file
            excel_buffer = BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "Sales Data"

            # Write header row
            headers = ['Item Name', 'Sold Quantity', 'Unit Selling Price', 'Revenue', 'Sale Date']
            ws.append(headers)

            # Write data rows
            for sale in sorted_sales_info:
                row = [
                    sale.get('itemName', ''),
                    sale.get('quantity', 0),
                    sale.get('unitPrice', 0),
                    sale.get('revenue', 0),
                    sale.get('saleDate', '').strftime('%Y-%m-%d') if isinstance(sale.get('saleDate'), datetime) else ''
                ]
                ws.append(row)

            wb.save(excel_buffer)
            excel_buffer.seek(0)

            # Create the response
            response = make_response(excel_buffer.getvalue())
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Sales_Data_{startdate_on_str}_{enddate_on_str}.xlsx"
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

            # Clean up
            del wb
            del excel_buffer
            gc.collect()

            return response
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

# Function to calculate total production cost
def calculate_total_cost(row):
    total_cost = 0
    for qty, prices in zip(row['Item Quantity'], row['Item Unit Price']):
        total_cost += np.sum(np.array(qty) * np.array(prices))
    return total_cost

@app.route('/view-production-info')
def view_production_info():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            twelve_months_ago = datetime.now() - timedelta(days=365)
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            company_name = company['company_name']

            inhouse_info = list(db.inhouse.find({'company_name': company_name, 'useDate': {'$gte': twelve_months_ago}}, {'company_name': 0}))

            if not inhouse_info:
                flash('No inhouse production data available for the past 12 months.', 'info')
                return render_template('production info.html', inhouse_df=None, dp=None)

            inhouse_product_ids = []
            inhouse_productName = []
            inhouse_productQuantity = []
            inhouse_productPrice = []
            inhouse_useDate = []
            inhouse_itemName = []
            inhouse_itemQuantity = []
            inhouse_itemUnitPrices = []
            inhouse_itemStockDates = []

            for record in inhouse_info:
                productID = record['_id']
                productName = record['productName']
                productQuantity = record['productQuantity']
                productPrice = record['productPrice']
                useDate = record['useDate']
                item_name = record['itemName']
                item_quantity = record['itemQuantity']
                item_unit_price = record['itemUnitPrices']
                itemStockDates = record['itemStockDates']
            
                inhouse_product_ids.append(productID)
                inhouse_productName.append(productName)
                inhouse_productQuantity.append(productQuantity)
                inhouse_productPrice.append(productPrice)
                inhouse_useDate.append(useDate)
                inhouse_itemName.append(item_name)
                inhouse_itemQuantity.append(item_quantity)
                inhouse_itemUnitPrices.append(item_unit_price)
                inhouse_itemStockDates.append(itemStockDates)

            # Create the DataFrame
            inhouse_df = pd.DataFrame({
                'Product ID': inhouse_product_ids,
                'Product Name': inhouse_productName,
                'Product Quantity': inhouse_productQuantity,
                'Product Unit Price': inhouse_productPrice,
                'Date Produced': inhouse_useDate,
                'Item Used': inhouse_itemName,
                'Item Quantity': inhouse_itemQuantity,
                'Item Unit Price': inhouse_itemUnitPrices,
                'Item Stock Date': inhouse_itemStockDates
            })

            # Ensure calculate_total_cost returns a single value
            def calculate_total_cost(row):
                return row['Product Quantity'] * row['Item Unit Price']

            # Apply the function to each row to calculate 'Total Production Cost'
            inhouse_df['Total Production Cost'] = inhouse_df.apply(calculate_total_cost, axis=1)
            inhouse_df_sorted = inhouse_df.sort_values(by='Date Produced')
            dp = company.get('dp')
            dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
            return render_template('production info.html', inhouse_df=inhouse_df_sorted, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
       
###DOANLOAD SALES DATA   
@app.route('/download-inhouse-data', methods=["POST"])
def download_inhouse():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            company_name = company['company_name']

            inhouse_info = list(db.inhouse.find({
                'company_name': company_name,
                'useDate': {'$gte': startdate, '$lte': enddate}
            }, {
                'company_name': 0
            }))

            inhouse_product_ids = []
            inhouse_productName = []
            inhouse_productQuantity = []
            inhouse_productPrice = []
            inhouse_useDate = []
            inhouse_itemName = []
            inhouse_itemQuantity = []
            inhouse_itemUnitPrices = []
            inhouse_itemStockDates = []

            for record in inhouse_info:
                productID = record['_id']
                productName = record['productName']
                productQuantity = record['productQuantity']
                productPrice = record['productPrice']
                useDate = record['useDate']
                item_name = record['itemName']
                item_quantity = record['itemQuantity']
                item_unit_price = record['itemUnitPrices']
                itemStockDates = record['itemStockDates']
            
                inhouse_product_ids.append(productID)
                inhouse_productName.append(productName)
                inhouse_productQuantity.append(productQuantity)
                inhouse_productPrice.append(productPrice)
                inhouse_useDate.append(useDate)
                inhouse_itemName.append(item_name)
                inhouse_itemQuantity.append(item_quantity)
                inhouse_itemUnitPrices.append(item_unit_price)
                inhouse_itemStockDates.append(itemStockDates)

            # Create the DataFrame
            inhouse_df = pd.DataFrame({
                'Product ID': inhouse_product_ids,
                'Product Name': inhouse_productName,
                'Product Quantity': inhouse_productQuantity,
                'Product Unit Price': inhouse_productPrice,
                'Date Produced': inhouse_useDate,
                'Item Used': inhouse_itemName,
                'Item Quantity': inhouse_itemQuantity,
                'Item Unit Price': inhouse_itemUnitPrices,
                'Item Stock Date': inhouse_itemStockDates
            })

            # Apply the function to each row to calculate 'Total Production Cost'
            inhouse_df['Total Production Cost'] = inhouse_df.apply(calculate_total_cost, axis=1)
            inhouse_df_sorted = inhouse_df.sort_values(by='Date Produced')

            # Create an in-memory buffer for the Excel file
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                inhouse_df_sorted.to_excel(writer, sheet_name='Inhouse Data', index=False)
            excel_buffer.seek(0)

            # Create a zip file containing the Excel file
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, 'w') as zip_file:
                zip_file.writestr(f"{company['company_name']}_Inhouse_Data_{startdate_on_str}_{enddate_on_str}.xlsx", excel_buffer.read())
            
            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()
            del inhouse_df, inhouse_df_sorted
            gc.collect()
            # Create the response
            response = make_response(zip_data)
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Inhouse_Data_{startdate_on_str}_{enddate_on_str}.zip"
            response.headers['Content-Type'] = 'application/zip'

            return response
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/download-inhouse-item-data', methods=["POST"])
def download_inhouse_item_use():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            company_name = company['company_name']

            inhouse_info = list(db.inhouse_use.find({
                'company_name': company_name,
                'useDate': {'$gte': startdate, '$lte': enddate}
            }, {
                'company_name': 0
            }))

            inhouse_itemName = []
            inhouse_useDate = []
            inhouse_itemQuantity = []
            inhouse_itemAverageUnitPrices = []
            inhouse_itemStockDates = []

            for record in inhouse_info:
                item_name = record['itemName']
                useDate = record['useDate']
                item_quantity = record['itemQuantity']
                if 'oldUnitPrice' in record:
                    average_unit_price = (record['oldUnitPrice'] + record['itemUnitPrices']) / 2
                else:
                    average_unit_price = record['itemUnitPrices']
                itemStockDates = record['itemStockDates']
            
                inhouse_itemName.append(item_name)
                inhouse_useDate.append(useDate)
                inhouse_itemQuantity.append(item_quantity)
                inhouse_itemAverageUnitPrices.append(average_unit_price)
                inhouse_itemStockDates.append(itemStockDates)

            # Create the DataFrame
            inhouse_df = pd.DataFrame({
                'Item Used': inhouse_itemName,
                'Date Used': inhouse_useDate,
                'Item Quantity': inhouse_itemQuantity,
                'Item Average Price': inhouse_itemAverageUnitPrices,
                'Item Stock Date': inhouse_itemStockDates
            })

            # Explode DataFrame to handle lists in columns
            inhouse_df_exploded = inhouse_df.explode('Item Used')
            inhouse_df_exploded['Date Used'] = inhouse_df.explode('Date Used')['Date Used']
            inhouse_df_exploded['Item Quantity'] = inhouse_df.explode('Item Quantity')['Item Quantity']
            inhouse_df_exploded['Item Average Price'] = inhouse_df.explode('Item Average Price')['Item Average Price']
            inhouse_df_exploded['Item Stock Date'] = inhouse_df.explode('Item Stock Date')['Item Stock Date']
            inhouse_df_exploded.reset_index(drop=True, inplace=True)  # Reset the index

            inhouse_df_exploded['Average Total Cost'] = inhouse_df_exploded['Item Quantity'] * inhouse_df_exploded['Item Average Price']

            # Create an in-memory buffer for the Excel file
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                inhouse_df_exploded.to_excel(writer, sheet_name='Inhouse item use data', index=False)
            excel_buffer.seek(0)

            # Create a zip file containing the Excel file
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, 'w') as zip_file:
                zip_file.writestr(f"{company['company_name']}_Inhouse_Item_Use_Data_{startdate_on_str}_{enddate_on_str}.xlsx", excel_buffer.read())
            
            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()
            del inhouse_df, inhouse_df_exploded
            gc.collect()
            # Create the response
            response = make_response(zip_data)
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Inhouse_Item_Use_Data_{startdate_on_str}_{enddate_on_str}.zip"
            response.headers['Content-Type'] = 'application/zip'

            return response
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

#Manager notifications
@app.route('/manager notifications')
def manager_notifications():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        notifications = []
        timestamps = []

        tenants = list(db.tenant_user_accounts.find({'account_manager': login_data}, {'_id': 1}))
        if len(tenants) != 0:
            for tenant in tenants:
                # Retrieve new complaints
                new_complaints = list(db.tenant_complaints.find(
                    {'tenantID': tenant['_id']}
                ))

                if new_complaints:
                    for new_complaint in new_complaints:
                        complained_on = new_complaint['complained_on']
                        if isinstance(complained_on, datetime):
                            formatted_complaint_date = complained_on.strftime('%Y-%m-%d %H:%M')
                        else:
                            complained_on = datetime.fromisoformat(complained_on)
                            formatted_complaint_date = complained_on.strftime('%Y-%m-%d %H:%M')

                        notification = f"Complaint from {new_complaint['tenant_name']} on {formatted_complaint_date}"
                        notifications.append(notification)
                        timestamps.append(complained_on)

                    # Retrieve and sort replies, limiting to 20
                    replies = list(db.tenant_complaints_replies.find(
                        {'complaintID': {'$in': [complaint['_id'] for complaint in new_complaints]}}
                    ).sort('reply_date', DESCENDING).limit(20))

                    if replies:
                        for reply in replies:
                            reply_date = reply['reply_date']
                            if isinstance(reply_date, datetime):
                                formatted_reply_date = reply_date.strftime('%Y-%m-%d %H:%M')
                            else:
                                reply_date = datetime.fromisoformat(reply_date)
                                formatted_reply_date = reply_date.strftime('%Y-%m-%d %H:%M')
                            
                            if reply['who'] != 'Manager':
                                notification = f"Reply from {reply['who']} on {formatted_reply_date}"
                                notifications.append(notification)
                                timestamps.append(reply_date)

        # Combine notifications with their timestamps and sort
        combined = list(zip(notifications, timestamps))
        combined.sort(key=lambda x: x[1], reverse=True)  # Sort by timestamp, latest first

        # Separate sorted notifications and timestamps
        notifications = [notif for notif, _ in combined]

        company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
        dp = company.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        
        return render_template('manager_notifications.html', notifications=notifications, dp=dp_str)
    
#Tenant notifications
@app.route('/tenant notifications')
def tenant_notifications():
    db, fs = get_db_and_fs()
    login_data = session.get('tenantID')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant-login-page')
    else:
        notifications = []

        tenant_user = db.tenant_user_accounts.find_one({'_id': ObjectId(login_data)})
        tenant_payment = db.tenants.find_one({'username': tenant_user['account_manager'], 'tenantEmail': tenant_user['tenantEmail']})
        payment_date = tenant_payment['date_last_paid']

        if isinstance(payment_date, datetime):
            formatted_payment_date = payment_date.strftime('%Y-%m-%d %H:%M')
        else:
            payment_date = datetime.fromisoformat(payment_date)
            formatted_payment_date = payment_date.strftime('%Y-%m-%d %H:%M')

        notification = {
            'message': f"{tenant_payment['months_paid']} {tenant_payment['year']} payment recorded by {tenant_payment['username']} on {formatted_payment_date}",
            'timestamp': payment_date,
            'type': 'payment'
        }
        notifications.append(notification)

        # Retrieve new complaints
        new_complaints = list(db.tenant_complaints.find({'tenantID': ObjectId(login_data)}))

        if new_complaints:
            # Retrieve and sort replies, limiting to 20
            replies = list(db.tenant_complaints_replies.find(
                {'complaintID': {'$in': [complaint['_id'] for complaint in new_complaints]}}
            ).sort('reply_date', DESCENDING).limit(20))

            if replies:
                for reply in replies:
                    reply_date = reply['reply_date']
                    if isinstance(reply_date, datetime):
                        formatted_reply_date = reply_date.strftime('%Y-%m-%d %H:%M')
                    else:
                        reply_date = datetime.fromisoformat(reply_date)
                        formatted_reply_date = reply_date.strftime('%Y-%m-%d %H:%M')
                    
                    if reply['who'] == 'Manager':
                        notification = {
                            'message': f"Reply from {reply['who']} on {formatted_reply_date}",
                            'timestamp': reply_date,
                            'type': 'reply'
                        }
                        notifications.append(notification)

        # Combine notifications with their timestamps and sort
        notifications.sort(key=lambda x: x['timestamp'], reverse=True)  # Sort by timestamp, latest first

        dp = tenant_user.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None

        return render_template('tenant_notifications.html', notifications=notifications, dp=dp_str)
    
@app.route('/notifications')
def notifications():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')

    manager_account = db.registered_managers.find_one({'username': login_data}, {'_id':0,'createdAt':0,'code':0,'phone_number':0,'address':0,'registered_on':0,'password':0,'auth':0,'dp':0,'dark_mode':0,'password':0})
    if manager_account:
        fields = ['add_properties', 'add_tenants', 'update_tenant', 'edit_tenant', 'manage_contracts', 'add_stock', 'update_stock',
                      'update_sales','inhouse','view_stock_info','view_revenue','view_sales','view_finance_dashboard','add_new_finance_account',
                      'update_finance_account','view_finance','edit_finance','delete_finance']
        for field in fields:
            value = manager_account.get(field)
            if value is not None:
                session[field] = value

        account_type = manager_account.get('account_type')
        if account_type is None:
            manager_type = db.managers.find_one({'name': manager_account['company_name']})
            account_type = manager_type['account_type']
            # Remove any empty strings from the list
            account_type = [atype for atype in account_type if atype]
            if 'Enterprise Resource Planning' in account_type and len(account_type) == 1:
                session['account_type'] = 'Enterprise Resource Planning'
            elif 'Property Management' in account_type and len(account_type) == 1:
                session['account_type'] = 'Property Management'
            elif 'Accounting' in account_type and len(account_type) == 1:
                session['account_type'] = 'Accounting'
        else:
            if account_type == 'Property Management':
                session['account_type'] = 'Property Management'
            elif account_type == 'Enterprise Resource Planning':
                session['account_type'] = 'Enterprise Resource Planning'
            elif 'Accounting' in account_type and len(account_type) == 1:
                session['account_type'] = 'Accounting'
            session['is_manager'] = 'is_manager'

    # Get the last seen timestamp from the session
    last_seen_timestamp = session.get('last_seen_timestamp', datetime.min)

    # Get the list of viewed notification IDs from the session
    viewed_notifications = session.get('viewed_notifications', [])

    # Fetch notifications with a timestamp greater than the last seen timestamp
    notifications_cursor = db.userNotifications.find({
        'user': login_data,
        'timestamp': {'$gt': last_seen_timestamp},
        '_id': {'$nin': [ObjectId(id) for id in viewed_notifications]}  # Exclude already viewed notifications
    }, {'_id': 1, 'notification': 1, 'timestamp': 1})

    # Convert cursor to list
    notifications_list = list(notifications_cursor)

    # Prepare the response with only new notifications
    notifications_to_send = [
        {
            'notification': notification['notification'],
            'timestamp': notification['timestamp'].isoformat()
        }
        for notification in notifications_list
    ]
    
    if notifications_to_send:
        # Update the last seen timestamp to the maximum timestamp of the fetched notifications
        new_last_seen_timestamp = max(notification['timestamp'] for notification in notifications_list)
        session['last_seen_timestamp'] = new_last_seen_timestamp

        # Update the list of viewed notifications
        new_viewed_notifications = [str(notification['_id']) for notification in notifications_list]
        session['viewed_notifications'] = viewed_notifications + new_viewed_notifications
    
    # Prepare the response with only new notifications
    notifications_list = [notification['notification'] for notification in notifications_to_send]

    return jsonify(notifications_list)

@app.route('/tenant_popup_notifications')
def tenant_popup_notifications():
    db, fs = get_db_and_fs()
    login_data = session.get('tenantID')

    # Get the last seen timestamp from the session
    last_seen_timestamp = session.get('last_seen_timestamp', datetime.min)

    # Get the list of viewed notification IDs from the session
    viewed_notifications = session.get('viewed_notifications', [])

    # Fetch notifications with a timestamp greater than the last seen timestamp
    notifications_cursor = db.userNotifications.find({
        'user': ObjectId(login_data),
        'timestamp': {'$gt': last_seen_timestamp},
        '_id': {'$nin': [ObjectId(id) for id in viewed_notifications]}  # Exclude already viewed notifications
    }, {'_id': 1, 'notification': 1, 'timestamp': 1})

    # Convert cursor to list
    notifications_list = list(notifications_cursor)

    # Prepare the response with only new notifications
    notifications_to_send = [
        {
            'notification': notification['notification'],
            'timestamp': notification['timestamp'].isoformat()
        }
        for notification in notifications_list
    ]
    
    if notifications_to_send:
        # Update the last seen timestamp to the maximum timestamp of the fetched notifications
        new_last_seen_timestamp = max(notification['timestamp'] for notification in notifications_list)
        session['last_seen_timestamp'] = new_last_seen_timestamp

        # Update the list of viewed notifications
        new_viewed_notifications = [str(notification['_id']) for notification in notifications_list]
        session['viewed_notifications'] = viewed_notifications + new_viewed_notifications

    return jsonify([notification['notification'] for notification in notifications_to_send])

####edit items
@app.route('/edit-item/<item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            manager = db.registered_managers.find_one({'username':login_data},{'_id':0,'createdAt':0,'code':0,'address':0})
            if manager.get('update_stock') in ('yes', None):
                selected_item = db.inventories.find_one({'_id': ObjectId(item_id)})
                if selected_item:
                    company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
                    if 'dp' in company:
                        dp_str = company['dp']
                    else:
                        dp_str = None
                    return render_template('edit-stock.html',item_id=item_id,dp=dp_str)
                else:
                    flash('Please select an up-to-date item', 'error')
                    return redirect('/stock-details')
            else:
                flash('You do not have rights to edit', 'error')
                return redirect('/stock-details')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/apply-item-edits', methods=['POST'])
def apply_item_edits():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            item_id = request.form.get("item_id")
            item_name = request.form.get("item_name")
            quantity = request.form.get("quantity")
            unit_price = request.form.get("unit_price")
            stockdate = request.form.get("stockdate")
            unit_of_measurement = request.form.get("unit_of_measurement")

            selected_item = db.inventories.find_one({'_id': ObjectId(item_id)})

            applied = 0
            if selected_item:
                if item_name:
                    db.inventories.update_one({'itemName': selected_item['itemName']}, {'$set': {'itemName': item_name}})
                    db.old_inventories.update_many({'itemName': selected_item['itemName']}, {'$set': {'itemName': item_name}})
                    db.stock_sales.update_many({'itemName': selected_item['itemName']}, {'$set': {'itemName': item_name}})
                    applied = 1
                if unit_of_measurement:
                    db.inventories.update_one({'itemName': selected_item['itemName']}, {'$set': {'unitOfMeasurement': unit_of_measurement}})
                    applied = 1
                if quantity:
                    quantity = float(quantity)
                    if 'available_quantity' in selected_item:
                        new_qty = selected_item['available_quantity'] - selected_item['quantity']
                        if new_qty < 0:
                            new_qty = 0
                            flash('Item sales were already updated', 'error')
                        available_quantity = new_qty + quantity
                    else:
                        available_quantity = quantity
                    db.inventories.update_one({'_id': ObjectId(item_id)}, {'$set': {'quantity': quantity, 'available_quantity': available_quantity}})
                    applied = 1
                if unit_price:
                    unit_price = float(unit_price)
                    if quantity:
                        new_total_price = quantity * unit_price
                    else:
                        new_total_price = selected_item['quantity'] * unit_price
                    db.inventories.update_one({'_id': ObjectId(item_id)}, {'$set': {'unitPrice': unit_price, 'totalPrice': new_total_price}})
                    applied = 1
                if stockdate:
                    stockDate = datetime.strptime(stockdate, '%Y-%m-%d')
                    db.inventories.update_one({'_id': ObjectId(item_id)}, {'$set': {'stockDate': stockDate}})
                    applied = 1

                if applied == 1:
                    flash('Item updates were applied', 'success')
                    db.audit_logs.insert_one({'user': login_data,'Activity': 'Stock edit','Item': item_id,'timestamp': datetime.now()})
                else:
                    flash('No edits were made', 'error')
                return redirect('/stock-details')
            else:
                flash('Please select an up-to-date item', 'error')
                return redirect('/stock-details')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
        
####delete items
@app.route('/delete-item/<item_id>', methods=['POST'])
def delete_item(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            manager = db.registered_managers.find_one({'username':login_data},{'_id':0,'createdAt':0,'code':0,'address':0})
            if manager.get('update_stock') in ('yes', None):
                selected_item = db.inventories.find_one({'_id': ObjectId(item_id)})
                if selected_item:
                    db.inventories.delete_one({'_id': ObjectId(item_id)})
                    db.audit_logs.insert_one({'user': login_data,'Activity': 'Stock deletion','Item': item_id,'timestamp': datetime.now()})
                    flash('Item was deleted', 'success')
                else:
                    flash('Please select an up-to-date item', 'error')
            else:
                flash('You do not have rights to delete', 'error')
            return redirect('/stock-details')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
####delete sale
@app.route('/delete-sale/<item_id>', methods=['POST'])
def delete_sale(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            manager = db.registered_managers.find_one({'username':login_data},{'_id':0,'createdAt':0,'code':0,'address':0})
            if manager.get('update_sales') in ('yes', None):
                sale_to_delete = db.stock_sales.find_one({'_id': ObjectId(item_id)})
                if sale_to_delete:
                    if 'stock_id' in sale_to_delete:
                        stock_to_undo = db.inventories.find_one({'_id': sale_to_delete['stock_id']})
                        if stock_to_undo:
                            available_quantity = stock_to_undo['available_quantity'] + sale_to_delete['quantity']
                            db.inventories.update_one({'_id': sale_to_delete['stock_id']}, {'$set': {'available_quantity': available_quantity}})
                            db.stock_sales.delete_one({'_id': ObjectId(item_id)})
                            db.audit_logs.insert_one({'user': login_data,'Activity': 'Sale deletion','Item': item_id,'timestamp': datetime.now()})
                            flash('Sale was deleted', 'success')
                        else:
                            flash('Unable to delete: No stock available', 'error')
                    else:
                        stock_to_undo = db.inventories.find_one({'itemName': sale_to_delete['itemName']})
                        if stock_to_undo:
                            available_quantity = stock_to_undo['available_quantity'] + sale_to_delete['quantity']
                            db.inventories.update_one({'itemName': sale_to_delete['itemName']}, {'$set': {'available_quantity': available_quantity}})
                            db.stock_sales.delete_one({'_id': ObjectId(item_id)})
                            db.audit_logs.insert_one({'user': login_data,'Activity': 'Sale deletion','Item': item_id,'timestamp': datetime.now()})
                            flash('Sale was deleted', 'success')
                        else:
                            flash('Unable to delete: No stock available', 'error')
                else:
                    flash('Sale does not exist', 'error')
            else:
                flash('You do not have rights to delete', 'error')
            return redirect('/sales-details')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

######add expenses
@app.route('/expenses-page')
def expenses_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            
            if company.get('update_sales') in ('yes', None):
                if 'dp' in company:
                    dp_str = company['dp']
                else:
                    dp_str = None
                return render_template('stock expenses.html', dp=dp_str)
            else:
                flash('You do not have rights to add expenses', 'error')
                return redirect('/stock-details')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/add-new-expense', methods=['POST'])
def add_new_expense():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                    'password': 0, 'auth': 0, 'dark_mode': 0})
                
            all_items = request.json.get('items', [])  # Access the JSON data sent from the client
            timestamp = datetime.now()

            for expense in all_items:
                expense['expenseName'] = expense.get('expenseName', '').strip()
                
                try:
                    # Convert 'quantity' and 'unitPrice' to floats
                    expense['amount'] = float(expense.get('amount', 0))
                    expense['expenseDate'] = datetime.strptime(expense.get('expenseDate', ''), '%Y-%m-%d')

                    expense['company_name'] = company.get('company_name', '')
                    expense['timestamp'] = timestamp

                    # Insert the new stock entry into MongoDB
                    db.stock_expenses.insert_one(expense)
                    db.audit_logs.insert_one({
                        'user': login_data,
                        'Activity': 'Added new expense',
                        'Item': expense['expenseName'],
                        'timestamp': datetime.now()
                    })
                    flash('Expense(s) were added', 'success')
                except (ValueError, TypeError) as e:
                    # Log or handle the exception as needed
                    flash(f"Error processing expense {expense.get('expenseName', 'unknown')}: {e}", 'error')

            return jsonify({'redirect': url_for('expenses_page')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

###viewing stock history
@app.route('/view-expenses')
def view_expenses():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
            if company.get('update_sales') in ('yes', None):
                subscription = db.managers.find_one({'name': company['company_name']}, {'account_type': 1, 'manager_email': 1, '_id': 0})
                account_type = subscription['account_type']
                # Remove any empty strings from the list
                account_type = [atype for atype in account_type if atype]

                if 'Enterprise Resource Planning' in account_type:
                    company_name = company['company_name']
                    twelve_months_ago = datetime.now() - timedelta(days=365)
                    expense_info = list(db.stock_expenses.find({'company_name': company_name, 'expenseDate': {'$gte': twelve_months_ago}}))
                    expense_info.sort(key=lambda x: x.get('timestamp', x['expenseDate']), reverse=True)

                    dp = company.get('dp')
                    dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
                    return render_template('view expenses.html', expense_info = expense_info, dp=dp_str)
            else:
                flash('You do not have rights to view expenses', 'error')
                return redirect('/stock-details')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

###DOANLOAD EXPENSE DATA   
@app.route('/download-expense-data', methods=["POST"])
def download_expense_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            startdate_on_str = request.form.get("startdate")
            enddate_on_str = request.form.get("enddate")
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')

            company = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})

            expenses = list(db.stock_expenses.find(
                {'company_name': company['company_name'], 'expenseDate': {'$gte': startdate, '$lte': enddate}},
                {'_id': 0, 'company_name': 0}
            ))

            # Sort data by expenseDate in descending order
            sorted_expenses = sorted(expenses, key=lambda x: x["expenseDate"], reverse=True)

            # Create Excel file
            excel_buffer = BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "Expenses"

            # Write header row
            headers = ['Expense', 'Amount', 'Date']
            ws.append(headers)

            # Write data rows
            for expense in sorted_expenses:
                row = [
                    expense.get('expenseName', ''),
                    expense.get('amount', 0),
                    expense.get('expenseDate', '').strftime('%Y-%m-%d') if isinstance(expense.get('expenseDate'), datetime) else '',
                ]
                ws.append(row)

            wb.save(excel_buffer)
            excel_buffer.seek(0)

            # Create the response
            response = make_response(excel_buffer.getvalue())
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Expenses_{startdate_on_str}_{enddate_on_str}.xlsx"
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

            # Clean up
            del wb
            del excel_buffer
            gc.collect()

            return response
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
####edit expense
@app.route('/edit-expense/<item_id>', methods=['GET', 'POST'])
def edit_expense(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            manager = db.registered_managers.find_one({'username':login_data},{'_id':0,'createdAt':0,'code':0,'address':0})
            if manager.get('update_sales') in ('yes', None):
                company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
                if 'dp' in company:
                    dp_str = company['dp']
                else:
                    dp_str = None
                return render_template('edit-expense.html',item_id=item_id,dp=dp_str)
            else:
                flash('You do not have rights to edit', 'error')
                return redirect('/stock-details')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/apply-expense-edits', methods=['POST'])
def apply_expense_edits():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            item_id = request.form.get("item_id")
            expense_name = request.form.get("expense_name")
            amount = request.form.get("amount")
            expensedate = request.form.get("expensedate")

            selected_item = db.stock_expenses.find_one({'_id': ObjectId(item_id)})

            fields_to_update = {}
            if selected_item:
                if expense_name:
                    fields_to_update['expenseName'] = expense_name
                if amount:
                    fields_to_update['amount'] = float(amount)
                if expensedate:
                    expensedate = datetime.strptime(expensedate, '%Y-%m-%d')
                    fields_to_update['expenseDate'] = expensedate
            else:
                flash('Please select an up-to-date expense', 'error')
            
            if not fields_to_update:
                flash('No edits were applied', 'error')
            else:
                db.stock_expenses.update_one({'_id': ObjectId(item_id)},
                                    {'$set': fields_to_update})
                db.audit_logs.insert_one({'user': login_data,'Activity': 'Edit expense','Item': item_id,'timestamp': datetime.now()})
                flash('Expense updates were applied', 'success')
            return redirect('/view-expenses')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

####delete expense
@app.route('/delete-expense/<item_id>', methods=['POST'])
def delete_expense(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            manager = db.registered_managers.find_one({'username':login_data},{'_id':0,'createdAt':0,'code':0,'address':0})
            if manager.get('update_sales') in ('yes', None):
                selected_item = db.stock_expenses.find_one({'_id': ObjectId(item_id)})
                if selected_item:
                    db.stock_expenses.delete_one({'_id': ObjectId(item_id)})
                    db.audit_logs.insert_one({'user': login_data,'Activity': 'Expense deletion','Item': item_id,'timestamp': datetime.now()})
                    flash('Expense was deleted', 'success')
                else:
                    flash('Expense does not exist', 'error')
            else:
                flash('You do not have rights to delete', 'error')
            return redirect('/view-expenses')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/new-accounts-page')
def new_accounts_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Accounting':
            company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0,'auth':0,'dark_mode':0})
            if 'dp' in company:
                dp_str = company['dp']
            else:
                dp_str = None

            items_to_update = []
            # Aggregate current and old accounts
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
            return redirect('/')

@app.route('/add-new-account', methods=['POST'])
def add_new_account():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
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

            all_items = request.json.get('items', [])  # Access the JSON data sent from the client
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
                            ['Payment Status:', f"Cleared"],
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
                        qr_code = Image(qr_code_img)
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
                        qr_code = Image(qr_code_img)
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
                                        sender='michpmts@gmail.com', 
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
                            thread = threading.Thread(target=send_async_email, args=[app, msg])
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
            return jsonify({'redirect': url_for('new_accounts_page')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/update existing account')
def update_existing_account():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
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
            return redirect('/')

@app.route('/update-accounts', methods=['POST'])
def update_accounts():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
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

                ##generate payment receipt
                # Create a payment receipt PDF file
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)

                # QR Code Generation
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

                # Create the receipt details
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
                qr_code_img = f'payment_receipt_qr_{item["client_id"]}.png'
                qr_code = Image(qr_code_img)
                qr_code.hAlign = 'CENTER'

                # Add the QR code image to the elements list before building the PDF
                elements = [table, qr_code]
                doc.build(elements)

                # Get the PDF data and encode it as base64
                pdf_data = buffer.getvalue()
                buffer.close()
                payment_receipt_base64 = base64.b64encode(pdf_data).decode()

                # Delete the QR code image file
                os.remove(f'payment_receipt_qr_{item["client_id"]}.png')

                ###send payment receipt
                email = account.get('email')
                if email and email.strip():
                    if send_emails is not None:
                        msg = Message(f"Payment Receipt From {account['company_name']}", 
                                    sender='michpmts@gmail.com', 
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
                        thread = threading.Thread(target=send_async_email, args=[app, msg])
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
            return jsonify({'redirect': url_for('update_existing_account')})
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/current-accounts')
def current_accounts():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
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
            return redirect('/')

@app.route('/accounts-history')
def accounts_history():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
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
            return redirect('/')

####edit finances
@app.route('/edit-finance-accounts/<item_id>', methods=['GET', 'POST'])
def edit_finance_accounts(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
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
            return redirect('/')
 
@app.route('/apply-finance-edits', methods=['POST'])
def apply_finance_edits():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
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
                        qr_code = Image(qr_code_img)
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
                                            sender='michpmts@gmail.com', 
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
                                thread = threading.Thread(target=send_async_email, args=[app, msg])
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
            return redirect('/')
    
####delete expense
@app.route('/delete-finance-account/<item_id>', methods=['POST'])
def delete_finance_account(item_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
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
            return redirect('/')

###DOANLOAD FINANCE DATA   
@app.route('/download-financial-data', methods=["POST"])
def download_financial_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
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
            return redirect('/')
        
@app.route('/accounts-overview', methods=["GET", "POST"])
def accounts_overview():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
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

                # Get the first day of the current month
                start_of_previous_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

                # Calculate the first day of the next month
                if today.month == 12:  # If it's December, the next month is January of the next year
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
                        '_id': '$project_name',  # Group by project_name
                        'total_amount': {'$sum': '$amount'},  # Sum of amount
                        'total_amount_demanded': {'$sum': '$amount_demanded'}  # Sum of amount_demanded
                    }
                },
                {
                    '$sort': {'total_amount': -1}  # Sort by total_amount in descending order
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

            # Count of clients by project
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
                        'unique_clients': {'$addToSet': '$client_id'}
                    }
                },
                {
                    '$project': {
                        '_id': 1,
                        'unique_client_count': {'$size': '$unique_clients'}
                    }
                }
            ])

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
                        'unique_clients': {'$addToSet': '$_id'}
                    }
                },
                {
                    '$project': {
                        '_id': 1,
                        'unique_client_count': {'$size': '$unique_clients'}
                    }
                }
            ])

            old_accounts_dict = {item['_id']: item['unique_client_count'] for item in old_accounts_counts}
            current_accounts_dict = {item['_id']: item['unique_client_count'] for item in current_accounts_counts}

            combined_counts = []

            for project_name in set(old_accounts_dict.keys()).union(current_accounts_dict.keys()):
                old_count = old_accounts_dict.get(project_name, 0)
                current_count = current_accounts_dict.get(project_name, 0)
                combined_count = old_count + current_count
                combined_counts.append({
                    'Project Name': project_name,
                    'Count': combined_count
                })

            count_clients_per_project_df = pd.DataFrame(combined_counts)
            default_count_labels = []
            default_count_values = []
            if not count_clients_per_project_df.empty:
                count_clients_per_project_df = count_clients_per_project_df.sort_values(by='Count', ascending=False)
                count_clients_per_project_df = count_clients_per_project_df.reset_index(drop=True) 
                count_labels = count_clients_per_project_df['Project Name'].tolist()
                count_values = count_clients_per_project_df['Count'].tolist()
            else:
                count_labels = default_count_labels
                count_values = default_count_values

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
            current_total_amount_paid_chart = {
                'labels': current_accounts_info_df['Project Name'].tolist(),
                'values': current_accounts_info_df['Total Amount Paid'].tolist()
            }

            current_total_amount_demanded_chart = {
                'labels': current_accounts_info_df['Project Name'].tolist(),
                'values': current_accounts_info_df['Amount Demanded'].tolist()
            }

            count_clients_by_project_chart = {
                'labels': count_labels,
                'values': count_values
            }

            trended_chart = {
                'labels': df_trended['Month_Name'].tolist(),
                'values': df_trended['Total Amount'].tolist()
            }

            del current_accounts_info_df,count_clients_per_project_df,df_trended
            gc.collect()
            dp = company.get('dp')
            dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
            return render_template('accounting dashboard.html',current_total_amount_paid_chart=current_total_amount_paid_chart,
                                current_total_amount_demanded_chart=current_total_amount_demanded_chart,
                                count_clients_by_project_chart=count_clients_by_project_chart,trended_chart=trended_chart,
                                start_of_previous_month=start_of_previous_month,
                                first_day_of_current_month=first_day_of_current_month, dp=dp_str)
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')
    
@app.route('/view-finance-receipt/<id>', methods=["GET"])
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
        old_account = db.old_transaction_finance_accounts.find_one({'client_id': ObjectId(id)})
        if old_account:
            if 'payment_receipt' in old_account:
                # Convert the base64 string back to bytes
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

def remove_file_later(filepath, delay=10):
    """ Schedule file deletion after a delay """
    def delayed_removal():
        time.sleep(delay)
        if os.path.exists(filepath):
            os.remove(filepath)
    threading.Thread(target=delayed_removal).start()

@app.route('/store-bar-code', methods=['POST'])
def store_bar_code():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        account_type = session.get('account_type')
        if account_type == 'Enterprise Resource Planning':
            product_name = request.form.get('typed_input')
            price = request.form.get('update_sale_unit_price')
            if product_name and price:
                manager = db.registered_managers.find_one({'username': login_data}, {'_id': 0, 'createdAt': 0, 'code': 0, 'phone_number': 0, 'address': 0,
                                                                                'password': 0, 'auth': 0, 'dark_mode': 0})
                company = db.managers.find_one({'name': manager['company_name']})
                product_id = db.inventories.find_one({'itemName': product_name})
                product_id_string = str(product_id['_id'])
                company_id = str(company["_id"])
                # QR Code Generation
                url = f'https://michmanagement.onrender.com//verify_user_making_sale?company_id={company_id}&product_id={product_id_string}'
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=3,
                    border=4,
                )
                qr.add_data(url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                
                img.save(f'{product_name}.png')


                # Load your QR code image
                qr_code_img = f'{product_name}.png'
                qr_code = Image(qr_code_img)
                qr_code.hAlign = 'CENTER'

                selling_price = float(price)

                filename = f'{product_name}.png'
                filepath = os.path.join('.', filename)

                db.inventories.update_one({'itemName': product_name}, {'$set': {'selling_price': selling_price}})
                flash(f'Bar code for {product_name} was generated and downloaded to your device', 'success')
                remove_file_later(filepath, delay=10)
                return jsonify({
                    'download_url': url_for('download_barcode', filename=filename),
                    'redirect_url': url_for('generate_bar_codes')
                })
            else:
                flash('Failed to generate QR Code', 'error')
                return redirect('/generate product bar codes page')
        else:
            flash('Your session expired or does not exist', 'error')
            return redirect('/')

@app.route('/download-barcode/<filename>')
def download_barcode(filename):
    return send_from_directory(directory='.', path=filename, as_attachment=True, download_name=filename)

@app.route('/verify_user_making_sale')
def verify_user_making_sale():
    db, fs = get_db_and_fs()
    # Extract company_name and product_id from the query parameters
    company_id = request.args.get('company_id')
    product_id = request.args.get('product_id')

    existing_item = db.inventories.find_one({'_id': ObjectId(product_id)})
    if existing_item:
        if 'selling_price' in existing_item:
            selling_price = existing_item['selling_price']
            # Render the verification page with hidden inputs
            return render_template('verify qr code sale.html', company_id=company_id, product_id=product_id, selling_price=selling_price)
        else:
            flash('No selling price set for the item', 'error')
            return redirect('/')
    else:
        flash('Scanned item is not in stock list', 'error')
        return redirect('/')

@app.route('/get_product')
def get_product():
    db, fs = get_db_and_fs()
    
    secret_id = request.form.get('secret_id')
    company_id = request.form.get('company_id')
    product_id = request.form.get('product_id')
    selling_price = request.form.get('selling_price')
    selling_price = float(selling_price)
    print(secret_id)
    print(company_id)
    print(product_id)
    print(selling_price)
    company = db.managers.find_one({'_id': ObjectId(company_id)},{'secret_id': 1, '_id': 0})
    if company:
        print(company)
        if 'secret_id' in company:
            if secret_id == company['secret_id']:
                print(secret_id)
                existing_item = db.inventories.find_one({'_id': ObjectId(product_id)})

                if existing_item:
                    if 'selling_price' in existing_item:
                        revenue = existing_item['selling_price']
                        timestamp = datetime.now()
                        if 'available_quantity' in existing_item:
                            if existing_item['available_quantity'] > 0:
                                available_quantity = existing_item['available_quantity'] - 1
                                stockDate = existing_item['stockDate']
                            else:
                                flash('Item is out of stock', 'error')
                                return redirect('/')
                        else:
                            if existing_item['quantity'] > 0:  
                                available_quantity = existing_item['quantity'] - 1
                                stockDate = existing_item['stockDate']
                            else:
                                flash('Item is out of stock', 'error')
                                return redirect('/')
                        stock_id = existing_item['_id']
                        data = {
                            'itemName': existing_item['itemName'],
                            'quantity': 1,
                            'unitPrice': revenue,
                            'saleDate': timestamp,
                            'company_name': company['company_name'],
                            'timestamp': timestamp,
                            'revenue': revenue,
                            'stockDate': stockDate,
                            'stock_id': stock_id
                        }

                        db.stock_sales.insert_one(data)
                        db.audit_logs.insert_one({
                            'user': company_id,
                            'Activity': 'Added a new sale',
                            'Item': existing_item['itemName'],
                            'timestamp': datetime.now()
                        })
                        db.inventories.update_one({'itemName': existing_item['itemName']}, {'$set': {'available_quantity': available_quantity}})
                        flash(f'Sale for {existing_item["itemName"]} was successful', 'success')
                        return redirect('/')
            else:
                print("Wrong secret ID")
                flash('Wrong secret id was provided', 'error')
                return render_template('verify qr code sale.html', company_id=company_id, product_id=product_id, selling_price=selling_price)
        else:
            flash('No secret id set for the company', 'error')
            return redirect('/')
    else:
        flash('Company does not exist, contact your admin', 'error')
        return redirect('/')

##########SEND PAYMENT REMINDERS###########
def send_payment_financial_reminders():
    current_day_of_week = datetime.now().weekday()
    if current_day_of_week != 3:
        return
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    accounts = list(db.transaction_finance_accounts.find())
    for account in accounts:
        if account['amount_demanded'] > 0:
            email = account.get('email')
            if email and email.strip():
                user_email = account['email']
                #Sending reminder message
                if send_emails is not None:
                    msg = Message('Payment Reminders - Mich Manage', 
                    sender='michpmts@gmail.com', 
                    recipients=[user_email])
                    msg.html = f"""
                    <html>
                    <body>
                    <p>Dear {account['client_name']},</p>
                    <p>This is a friendly reminder that a payment of <b>{ account['amount_demanded'] }</b> is currently due from <b>{ account['company_name'] }</b>.</p>
                    <p>We kindly request that you ensure your payment is processed at your earliest convenience.</p>
                    <p>If you have any questions or require further assistance, please do not hesitate to contact us.</p>
                    <p>Thank you for your prompt attention to this matter.</p>
                    <p>Best Regards,</p>
                    <p>Mich Manage</p>
                    </body>
                    </html>
                    """
                    # Send the email
                    with app.app_context():
                        thread = threading.Thread(target=send_async_email, args=[app, msg])
                        thread.start()

########SCHEDULE TASKS
scheduler.add_job(
    func=send_reports,
    trigger=CronTrigger(day=1, hour=9, minute=0),
    id='send_reports_job',
    name='Send reports on the 1st of every month',
    replace_existing=True
)

scheduler.add_job(
    send_payment_reminders,
    CronTrigger(hour=9, minute=0),
    id='send_payment_reminders_job',
    name='Run job every day at 9 AM',
    replace_existing=True
)

scheduler.add_job(
    send_contract_expiry_reminders,
    CronTrigger(hour=9, minute=0),
    id='send_payment_reminders_job',
    name='Run job every day at 9 AM',
    replace_existing=True
)

scheduler.add_job(
    send_payment_financial_reminders,
    CronTrigger(hour=9, minute=0),
    id='send_payment_reminders_job',
    name='Run job every day at 9 AM',
    replace_existing=True
)

scheduler.start()

if __name__ == '__main__':
    app.run()
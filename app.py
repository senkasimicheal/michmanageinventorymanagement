from flask import Flask, render_template, url_for, send_from_directory, request, flash, redirect, session, make_response, send_file, jsonify
from flask_mail import Mail, Message
from flask_apscheduler import APScheduler
from docx import Document
from pymongo import MongoClient, ASCENDING
import secrets
import bcrypt
from datetime import datetime, timedelta
import calendar
import pytz
import pandas as pd 
from io import BytesIO
import plotly
import plotly.graph_objs as go
import plotly.express as px
import plotly.utils
import json
from bson.objectid import ObjectId
from PIL import Image
import io
import base64
import calendar
import random
import os
from docx import Document
from werkzeug.utils import secure_filename
from gridfs import GridFS
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image
from openpyxl import Workbook, load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import tempfile
import string
import qrcode

app = Flask(__name__, static_folder='static')
app.secret_key = secrets.token_hex(16)
client = MongoClient('mongodb+srv://micheal:QCKh2uCbPTdZ5sqS@cluster0.rivod.mongodb.net/ANALYTCOSPHERE?retryWrites=true&w=majority')
# client = MongoClient('mongodb://localhost:27017/')
db = client.PropertyManagement
fs = GridFS(db, collection='contracts')

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Declare send_emails as a global variable
send_emails = send_emails = db.send_emails.find_one({'emails': "yes"})
mail = Mail(app)

def update_send_emails():
    global send_emails
    send_emails = db.send_emails.find_one({'emails': "yes"})
    if send_emails is not None:
        app.config['MAIL_SERVER']='smtp.sendgrid.net'
        app.config['MAIL_PORT'] = 587
        app.config['MAIL_USERNAME'] = 'apikey'
        app.config['MAIL_PASSWORD'] = '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'
        app.config['MAIL_USE_TLS'] = True
        app.config['MAIL_USE_SSL'] = False
        mail.init_app(app)

scheduler.add_job('update_send_emails', update_send_emails, trigger='interval', seconds=5)

utc = pytz.UTC

def generate_file_password(length=12):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def send_reports():
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
        doc.add_paragraph(f'Manimum Number Of Days Taken To Resolve Complaints: {max_days}')
        doc.add_paragraph(f'Minimum Number Of Days Taken To Resolve Complaints: {min_days}')


        # Save the document
        report_filename = f'{email}_report.docx'
        doc.save(report_filename)

        # Create a new Flask-Mail Message
        if send_emails is not None:
            msg = Message(
                'Mich PMT Systems - Monthly Property Performance Report',
                sender='michpmts@gmail.com',
                recipients=[email]
            )

            # Attach the report
            with app.open_resource(report_filename) as fp:
                msg.attach(report_filename, "application/docx", fp.read())

            # Set the HTML body of the email
            msg.html = f"""
            <html>
            <body>
            <p>Dear {company_name},</p>
            <p>Please find attached your monthly report.</p>
            <p>Best Regards,</p>
            <p>Mich Manage</p>
            </body>
            </html>
            """

            # Send the email
            with app.app_context():
                mail.send(msg)
            # Delete the report
            os.remove(report_filename)

scheduler.add_job('send_reports', send_reports, trigger='cron', day='1', hour=11, minute=59)

##########SEND PAYMENT REMINDERS###########
def send_payment_reminders():
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
                <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com">Visit Our Website</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                # Send the email
                with app.app_context():
                    mail.send(msg)
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
                <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com">Visit Our Website</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                # Send the email
                with app.app_context():
                    mail.send(msg)

scheduler.add_job('send_payment_reminders', send_payment_reminders, trigger='cron', day_of_week='wed', hour=9)

##########SEND CONTRACT EXPIRY REMINDERS###########
def send_contract_expiry_reminders():
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
            <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com">Visit Our Website</a></b></p>
            <p>Best Regards,</p>
            <p>Mich Manage</p>
            </body>
            </html>
            """
            # Send the email
            with app.app_context():
                mail.send(msg)

scheduler.add_job('send_contract_expiry_reminders', send_contract_expiry_reminders, trigger='cron', day_of_week='fri', hour=9)
    
@app.route("/")
def index():
    companies = db.managers.find({}, {"name": 1})
    company_names = [company['name'] for company in companies]
    
    cursor = list(db.property_managed.find())
    df = pd.DataFrame(cursor)
    if 'propertyName' in df.columns:
        property_data = df['propertyName'].tolist()
    else:
        property_data = []

    resp = make_response(render_template("index.html", property_data=property_data, company_names=company_names))
    return resp
    
###########SEND US A MESSAGE###############
@app.route('/send-message', methods=["POST"])
def send_message():
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
        <p>{name} has just contacted Mich PMTS</p>
        <p>Phone number: {phone}</p>
        <p>Email: {email}</p>
        <p><b style="font-size: 20px;">Message</b></p>
        <p>{message}</p>
        <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com">Visit Our Website</a></b></p>
        </body>
        </html>
        """
        mail.send(msg)
    flash('Your inquiry was sent')
    return redirect('/')

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Expires"] = '0'
    response.headers["Pragma"] = "no-cache"
    return response

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/', code=303)

@app.route('/logout-admin')
def logout_admin():
    session.clear()
    return redirect('/admin', code=303)

@app.before_request
def before_request():
    if 'logged_in' not in session and request.endpoint not in ('send_message', 'tenant_register_account', 'register_account','load_verification_page', 'verifying_your_account', 'terms_of_service', 'privacy_policy', 'admin', 'adminlogin', 'add_property_manager', 'complaint_form', 'tenant_data', 'tenant_download', 'get_receipt',
                                                               'google_verification', 'contact', 'sitemap', 'about', 'tenant_login_page', 'tenant_login', 'tenant_register', 'register', 'login', 'userlogin', 'index', 'static', 'verify_username', 'send_verification_code', 'password_reset_verifying_user', 'add_property_manager_page',
                                                               'add_complaint', 'my_complaints', 'tenant_reply_complaint', 'resolve_complaints' , 'update_complaint', 'new_subscription', 'new_subscription_initiated', 'export', 'apply_for_advert', 'submit_advert_application', 'search_apartment', 'authentication'):
        return redirect('/')
    
@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy policy.html')

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms of service.html')

@app.route('/google534116b25df7d103.html')
def google_verification():
    return render_template('google534116b25df7d103.html')

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
    # Get form data
    form_data = request.form
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
        flash('Passwords do not match')
        return redirect('/register')

    # Check if user is a manager
    company = db.managers.find_one({'name': company_name})
    if email not in company.get('managers', []):
        flash('Not a manager in the registered companies')
        return redirect('/')

    # Check if username or email already exists
    if db.tenant_user_accounts.find_one({'username': username}):
        flash('Username already taken')
        return redirect('/')
    if db.registered_managers.find_one({'username': username}):
        flash('Username already taken')
        return redirect('/')
    if db.registered_managers.find_one({'email': email, 'company_name': company_name}):
        flash('User already registered')
        return redirect('/')

    # Generate verification code
    code = generate_code()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    is_manager = db.managers.find_one({'manager_email': email})
    if is_manager:
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
            'password': hashed_password
        }
    else:
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
            'add_properties': 'no',
            'add_tenants': 'no',
            'update_tenant': 'no',
            'edit_tenant': 'no',
            'manage_contracts': 'no'
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
        <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com/load-verification-page">Verify</a></b></p>
        <p>Best Regards,</p>
        <p>Mich Manage</p>
        </body>
        </html>
        """
        mail.send(msg)
    else:
        session['no_send_emails_code'] = 'no_send_emails_code'
        no_send_emails_code = code
    # Create an index on the 'createdAt' field
    db.registration_verification_codes.create_index([("createdAt", ASCENDING)], expireAfterSeconds=43200)
    # Insert verification code into database
    db.registration_verification_codes.insert_one(manager)

    flash('Please verify your account')
    return render_template('verify_manager.html', no_send_emails_code=no_send_emails_code)

    
##########VERIFYING MANAGER ACCOUNT##############
@app.route('/load-verification-page')
def load_verification_page():
    return render_template('verify_manager.html')

@app.route('/verifying-your-account', methods=["POST"])
def verifying_your_account():
    # Get form data
    email = request.form.get('email')
    code = request.form.get('code')

    # Check if code exists
    code_exists = db.registration_verification_codes.find_one({'email': email, 'code': code})
    if code_exists is None:
        flash('Check the code and try again')
        return render_template('verify_manager.html')

    # Insert manager into registered managers
    try:
        db.registered_managers.insert_one(code_exists)
        flash('User registered')
        return redirect('/')
    except Exception as e:
        flash('An error occurred while registering the user: ' + str(e))
        return render_template('verify_manager.html')


def mask_email(email):
    at_index = email.index("@")
    return email[0] + "*"*(at_index-2) + email[at_index-1:]

##########FORGOT PASSWORD##############
@app.route('/verify-username')
def verify_username():
    return render_template('forgot_password_verify_username.html')

def send_verification_email(manager_email, manager_name, code):
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
        <p>Please note that this code is only valid for 5 minutes from the time of this email. For security reasons, please do not share this code with anyone, including Mich PMT support staff.</p>
        <p>If you did not request this password reset, please disregard this email. Your account security is important to us.</p>
        <p>Thank you for choosing Mich PMT</p>
        <p>Best Regards,</p>
        <p>Mich Manage</p>
        </body>
        </html>
        """
        mail.send(msg)

@app.route('/send-verification-code', methods=["POST"])
def send_verification_code():
    username = request.form.get('username')
    manager_exists = db.registered_managers.find_one({'username': username})
    if manager_exists is None:
        flash('Check username and try again')
        return redirect('/verify-username')

    code = generate_code()
    manager_email = manager_exists['email']
    masked_email = mask_email(manager_email)
    reset_requested = db.forgot_password_codes.find_one({'username': username})

    if reset_requested is None:
        manager = {'createdAt': datetime.now(), 'code': code, 'username': username, 'email': manager_email}
        send_verification_email(manager_email, manager_exists['name'], code)
        db.forgot_password_codes.insert_one(manager)
        flash('A verification code was sent to your email')
        return render_template('forgot_password_code.html', masked_email=masked_email)
    else:
        flash(f"Code was sent to {masked_email}")
        return redirect('/verify-username')

    
@app.route('/password-reset-verifying_user', methods=["POST"])
def password_reset_verifying_user():
    # Get form data
    email = request.form.get('email')
    code = request.form.get('code')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    # Check if passwords match
    if password != confirm_password:
        flash('Passwords do not match')
        return render_template('forgot_password_code.html')

    # Check if code exists
    request_exists = db.forgot_password_codes.find_one({'email': email, 'code': code})
    if request_exists is None:
        flash('Check code or email and try again')
        return render_template('forgot_password_code.html')

    # Update password
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    try:
        db.registered_managers.update_one({'username': request_exists['username']},{'$set': {'password': hashed_password}})
        db.forgot_password_codes.delete_one({'email': email, 'code': code})
    except Exception as e:
        flash('An error occurred while resetting the password: ' + str(e))
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
        <p>We're writing to inform you that the password for your account at Mich PMT has been successfully reset.</p>
        <p>If you initiated this password reset, you can now log in to your account using your new password. Please keep this password secure and do not share it with anyone.</p>
        <p>If you did not request this password reset, or if you have any concerns about the security of your account, please contact our support team immediately.</p>
        <p>Thank you for choosing Mich PMT. If you have any further questions or need assistance, please don't hesitate to reach out.</p>
        <p>Best Regards,</p>
        <p>Mich Manage</p>
        </body>
        </html>
        """
        mail.send(msg)

    flash('Your password was successfully reset')
    return redirect('/login')
         
#######PROPERTY MANAGER LOGIN##############
@app.route("/userlogin", methods=["POST"])
def userlogin():
    session.clear()

    global send_emails
    send_emails = db.send_emails.find_one({'emails': "yes"})
    if send_emails is not None:
        app.config['MAIL_SERVER']='smtp.sendgrid.net'
        app.config['MAIL_PORT'] = 587
        app.config['MAIL_USERNAME'] = 'apikey'
        app.config['MAIL_PASSWORD'] = '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'
        app.config['MAIL_USE_TLS'] = True
        app.config['MAIL_USE_SSL'] = False
        mail.init_app(app)

    username = request.form.get('username')
    password = request.form.get('password')

    manager = db.registered_managers.find_one({'username':username})
    if manager is None:
        flash('Not a manager')
        return redirect('/')
    else:
        subscription = db.managers.find_one({'name': manager['company_name']})
        stored_password = manager['password']
        if not bcrypt.checkpw(password.encode('utf-8'), stored_password):
            flash('Wrong Password')
            return redirect('/')

        remaining_days = (subscription['last_subscribed_on'] + timedelta(days=subscription['subscribed_days']) - datetime.now()).days
        if remaining_days <= 0:
            flash('Your subscription has expired, please contact management')
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
                <p>Mich Manage Personal Identification</p>
                <p><b style="font-size: 20px;">Verification Code: {code}</b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                mail.send(msg)
            else:
                session['no_send_emails_code'] = 'no_send_emails_code'
                no_send_emails_code = code

            db.login_auth.create_index([("createdAt", ASCENDING)], expireAfterSeconds=300)
            db.login_auth.insert_one(user_auth)
            return render_template("authentication.html", no_send_emails_code=no_send_emails_code)
        else:
            user_message1 = f"{manager['name']}"
            login_username = f"{manager['username']}"
            phone_number = f"{manager['phone_number']}"
            is_manager = db.managers.find_one({'manager_email': manager['email']})
            if is_manager:
                session['is_manager'] = 'is_manager'

            last_logged_in_data = db.logged_in_data.find_one({'username': username}, sort=[('timestamp', -1)])

            if last_logged_in_data is None:
                # This is a new user, so we don't have a last login time.
                session['time_since_last_login_secs'] = None
                session['time_since_last_login_mins'] = None
                session['time_since_last_login_hrs'] = None
            else:
                last_login = last_logged_in_data['timestamp']
                now = datetime.now()
                total_seconds  = (now - last_login).total_seconds()

                if total_seconds < 60:  # less than a minute
                    time_since_last_login_secs = int(total_seconds)
                    session['time_since_last_login_secs'] = time_since_last_login_secs
                elif total_seconds < 3600:  # less than an hour
                    time_since_last_login_mins = int(total_seconds / 60)
                    session['time_since_last_login_mins'] = time_since_last_login_mins
                elif total_seconds < 86400:  # less than a day
                    time_since_last_login_hrs = int(total_seconds / 3600)
                    session['time_since_last_login_hrs'] = time_since_last_login_hrs
                elif total_seconds < 604800:  # less than a week
                    time_since_last_login_days = int(total_seconds / 86400)
                    session['time_since_last_login_days'] = time_since_last_login_days
                elif total_seconds < 2629800:  # less than a month
                    time_since_last_login_weeks = int(total_seconds / 604800)
                    session['time_since_last_login_weeks'] = time_since_last_login_weeks
                elif total_seconds < 31557600:  # less than a year
                    time_since_last_login_months = int(total_seconds / 2629800)
                    session['time_since_last_login_months'] = time_since_last_login_months
                else:  # more than a year
                    time_since_last_login_years = int(total_seconds / 31557600)
                    session['time_since_last_login_years'] = time_since_last_login_years

            logged_in_data = {
                'username': username,
                'timestamp': datetime.now()
            }
            db.logged_in_data.insert_one(logged_in_data)

            session.permanent = False
            session['logged_in'] = True
            session['user_id'] = str(manager["_id"])
            session['user_message1'] = user_message1
            session['user_message2'] = remaining_days
            session['login_username'] = login_username
            session['phone_number'] = phone_number

            fields = ['add_properties', 'add_tenants', 'update_tenant', 'edit_tenant', 'manage_contracts']
            for field in fields:
                value = manager.get(field)
                if value is not None:
                    session[field] = value

            return redirect("/load-dashboard-page")


#USER AUTHENTICATION
@app.route("/authentication", methods=["POST"])
def authentication():
    # Get form data
    code = request.form.get("code")

    # Check if code exists
    user_auth = db.login_auth.find_one({"code": code})
    if user_auth is None:
        flash("Check code and try again")
        return render_template("authentication.html")

    # Get manager and subscription data
    manager = db.registered_managers.find_one({'username': user_auth["username"]})
    if manager is None:
        flash('Not a manager')
        return redirect('/')
    else:
        subscription = db.managers.find_one({'name': manager['company_name']})

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
            flash('An error occurred while logging in: ' + str(e))
            return render_template("authentication.html")

        # Set session data
        session.permanent = False
        session['logged_in'] = True
        session['user_id'] = str(manager["_id"])
        session['user_message1'] = manager['name']
        session['user_message2'] = remaining_days
        session['login_username'] = manager['username']
        session['phone_number'] = manager['phone_number']

        return redirect("/load-dashboard-page")
        
##ACCOUNT SETTING
@app.route('/account-setup-page')
def account_setup_page():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        dp = company.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        auth = company.get('auth', "no")
        return render_template("account setting.html", dp=dp_str, auth=auth)

##ACCOUNT SETTING
@app.route('/account-setup-initiated', methods=["POST"])
def account_setup_initiated():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        auth = request.form.get("switchState")
        name = request.form.get("name")
        phone_number = request.form.get("phone_number")
        address = request.form.get("address")
        dp = request.files['dp'].read() if 'dp' in request.files else None

        update_fields = {}

        if auth:
            update_fields['auth'] = auth
        if name:
            update_fields['name'] = name
        if phone_number:
            update_fields['phone_number'] = phone_number
        if address:
            update_fields['address'] = address
        if dp:
            # Open the image file with PIL
            img = Image.open(io.BytesIO(dp))
            # Convert the image to RGB mode
            rgb_img = img.convert('RGB')
            # Adjust the quality of the image
            output_io = io.BytesIO()
            rgb_img.save(output_io, format='JPEG', quality=10)  # Adjust the quality until you reach desired size
            # Convert the image data to base64
            dp_base64 = base64.b64encode(output_io.getvalue())
            update_fields['dp'] = dp_base64

        # Update the document with the non-empty fields
        db.registered_managers.update_one({'username': login_data}, {'$set': update_fields})
        flash("Your account was successfully set")
        return redirect('/account-setup-page')

#######TENANT REGISTER ACCOUNT###############          
@app.route('/tenant-register-account', methods=["POST"])
def tenant_register_account():
    email = request.form.get('email')
    username = request.form.get('username')
    propertyName = request.form.get('propertyName')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')

    if password != confirm_password:
        flash('Passwords do not match')
        return redirect('/tenant-register')
    else:
        tenant_exists = db.tenant_user_accounts.find_one({'tenantEmail': email, 'propertyName': propertyName})
        user = db.tenant_user_accounts.find_one({'username': username})
        used_username = db.registered_managers.find_one({'username': username})
        if used_username:
            flash('This username is already taken')
            return redirect('/')
        else:
            if tenant_exists is None and user is None:
                tenant = db.tenants.find_one({'propertyName': propertyName, 'tenantEmail': email})
                if tenant is None:
                    flash('Entered tenant is not attached to any property')
                    return redirect('/tenant-register')
                else:
                    hashed_password = bcrypt.hashpw(confirm_password.encode('utf-8'), bcrypt.gensalt())
                    tenant_data = {'account_manager': tenant['username'], 'tenantEmail': email, 'username': username, 'propertyName': propertyName,
                                'registered_on': datetime.now(), 'password': hashed_password}
                    db.tenant_user_accounts.insert_one(tenant_data)
                    flash('Tenant registered')
                    return redirect('/')
            else:
                flash('Tenant already registered')
                return redirect('/')
        
#######TENANT LOGIN##############
@app.route("/tenant-login", methods=["POST"])
def tenant_login():
    username = request.form.get('username')
    password = request.form.get('password')

    tenant = db.tenant_user_accounts.find_one({'username': username})
    if tenant is None:
        flash('Not a registered tenant')
        return redirect('/tenant-login-page')
    else:
        stored_password = tenant['password']
        if bcrypt.checkpw(password.encode('utf-8'), stored_password):
            session.permanent = False
            session['tenantID'] = str(tenant['_id'])
            session['tenantEmail'] = tenant['tenantEmail']
            session['propertyName'] = tenant['propertyName']
            return redirect('/tenant-data')
        else:
            flash('Wrong Password')
            return redirect('/tenant-login-page')

@app.route('/tenant-data')
def tenant_data():
    tenantEmail = session.get('tenantEmail')
    propertyName = session.get('propertyName')
    if tenantEmail is None or propertyName is None:
        flash('Login first')
        return redirect('/tenant-login-page')
    else:
        current_tenant_data = list(db.tenants.find({'tenantEmail': tenantEmail, 'propertyName': propertyName}))
        if len(current_tenant_data) == 0:
            flash('We found no amount demanded')
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
                        amount_demanded += (tenant['section_value'] - tenant['available_amount']) + amount_next_month

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
                        amount_demanded += (tenant['section_value'] - tenant['available_amount']) + amount_next_month

                        tenant_data.append({
                            'name': name,
                            'phone': phone,
                            'propertyName': propertyName,
                            'amount_demanded': amount_demanded,
                            'months_paid': f"From {months_paid} to {current_month}",
                            'date_paid': date_paid.strftime("%Y-%m-%d")
                        })
        
            session['tenant_data'] = tenant_data
            return render_template('tenant monitor account.html',tenant_data=tenant_data)

#############LOADING COMPLAINTS PAGE##########
@app.route('/complaint-form')
def complaint_form():
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first')
        return redirect('/tenant-login-page')
    else:
        return render_template('complaints template.html')
    
##########STORE COMPLAINTS##############
@app.route('/add-complaint', methods=["POST"])
def add_complaint():
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first')
        return redirect('/tenant-login-page')
    else:
        complaint_heading = request.form.get('complaint_heading')
        details = request.form.get('details')
        client_time = request.form.get('client_time')
        client_time = datetime.fromisoformat(client_time)
        time_zone_offset = int(request.form.get('time_zone_offset'))
        adjusted_time = client_time + timedelta(hours=time_zone_offset)
        tenant_user = db.tenant_user_accounts.find_one({'_id': ObjectId(tenant_login_data)})
        tenant = db.tenants.find_one({'tenantEmail': tenant_user['tenantEmail'], 'propertyName': tenant_user['propertyName']})
        manager = db.registered_managers.find_one({'username': tenant['username'], 'company_name': tenant['company_name']})
        manager_email = manager['email']
        compiled_complaint = {'tenantID': ObjectId(tenant_login_data), 'tenant_name': tenant['tenantName'], 'complaint_heading': complaint_heading,
                              'details': details, 'complained_on': adjusted_time}
        db.tenant_complaints.insert_one(compiled_complaint)
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
            <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com/login">Login</a></b></p>
            <p>Best Regards,</p>
            <p>Mich Manage</p>
            </body>
            </html>
            """
            mail.send(msg)
        flash('Complaint submitted, we will get back to you')
        return redirect('/complaint-form')
    
############SHOW MY COMPLAINTS######################
@app.route('/my-complaints')
def my_complaints():
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first')
        return redirect('/tenant-login-page')
    else:
        my_complaints = db.tenant_complaints.find({'tenantID': ObjectId(tenant_login_data)})
        if len(list(db.tenant_complaints.find({'tenantID': ObjectId(tenant_login_data)}))) == 0:
            flash('You have not placed any complaint(s) yet!')
            return redirect('/complaint-form')
        else:
            complaints = []
            for complaint in my_complaints:
                replies = list(db.tenant_complaints_replies.find({'complaintID': complaint['_id']}))
                if len(replies) == 0:
                    replies = [{'Reply': 'No reply', 'who': 'N/A', 'reply_date': 'N/A'}]
                else:
                    # Sort replies by date, most recent first
                    replies = sorted(replies, key=lambda r: r['reply_date'], reverse=True)
                complaint_copy = complaint.copy()  # create a copy of complaint to avoid overwriting
                complaint_copy['_id'] = str(complaint['_id'])
                complaint_copy['tenantID'] = str(complaint['tenantID'])
                complaint_copy['replies'] = [{'Reply': reply['Reply'], 'who': reply['who'], 'reply_date': reply['reply_date'].strftime('%Y-%m-%d %H:%M') if reply['reply_date'] != 'N/A' else 'N/A'} for reply in replies]
                complaints.append(complaint_copy)
            # Sort complaints by date, most recent first
            complaints = sorted(complaints, key=lambda c: c['complained_on'], reverse=True)
            # Remove duplicates
            complaints = list({v['_id']: v for v in complaints}.values())
            session['complaints'] = complaints
            return render_template('my complaints.html',complaints=complaints)

############REPLY TO COMPLAINTS BY TENANT###########
@app.route('/tenant-reply-to-complaint', methods=['POST'])
def tenant_reply_complaint():
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        tenant_name = db.tenant_user_accounts.find_one({'_id': ObjectId(tenant_login_data)})
        login_data = tenant_name['username']
        if 'complaints' in session:
            complaints = session.get('complaints')
            for complaint in complaints:
                if 'Reply_' + str(complaint['_id']) in request.form:
                    Reply = request.form.get('Reply_' + str(complaint['_id']))
                    client_time = request.form.get('client_time')
                    client_time = datetime.fromisoformat(client_time)
                    time_zone_offset = int(request.form.get('time_zone_offset'))
                    adjusted_time = client_time + timedelta(hours=time_zone_offset)
                    db.tenant_complaints_replies.insert_one({'complaintID': ObjectId(complaint['_id']),
                                                             'Reply': Reply,
                                                             'who': login_data,
                                                             'reply_date': adjusted_time})
                    tenant_managed = db.tenants.find_one({'tenantEmail': tenant_name['tenantEmail'], 'propertyName': tenant_name['propertyName']})
                    manager = db.registered_managers.find_one({'username': tenant_managed['username'], 'company_name': tenant_managed['company_name']})
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
                        <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com">Login</a></b></p>
                        <p>Best Regards,</p>
                        <p>Mich Manage</p>
                        </body>
                        </html>
                        """
                        mail.send(msg)
            
            found_complaints = db.tenant_complaints.find({'tenantID': ObjectId(tenant_login_data)})
            complaints = []
            for complaint in found_complaints:
                replies = list(db.tenant_complaints_replies.find({'complaintID': complaint['_id']}))
                if len(replies) == 0:
                    replies = [{'Reply': 'No reply', 'who': 'N/A', 'reply_date': 'N/A'}]
                else:
                    # Sort replies by date, most recent first
                    replies = sorted(replies, key=lambda r: r['reply_date'], reverse=True)
                complaint_copy = complaint.copy()  # create a copy of complaint to avoid overwriting
                complaint_copy['_id'] = str(complaint['_id'])
                complaint_copy['tenantID'] = str(complaint['tenantID'])
                complaint_copy['replies'] = [{'Reply': reply['Reply'], 'who': reply['who'], 'reply_date': reply['reply_date'].strftime('%Y-%m-%d %H:%M') if reply['reply_date'] != 'N/A' else 'N/A'} for reply in replies]
                complaints.append(complaint_copy)
            # Sort complaints by date, most recent first
            complaints = sorted(complaints, key=lambda c: c['complained_on'], reverse=True)
            # Remove duplicates
            complaints = list({v['_id']: v for v in complaints}.values())
            session['complaints'] = complaints
            return render_template('my complaints.html',complaints=complaints)
        else:
            flash('Login first')
            return redirect('/')
  
############LOAD COMPLAINTS TO MANAGER######################
@app.route('/resolve-complaints')
def resolve_complaints():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        is_manager = db.managers.find_one({'manager_email': company['email']})
        ####CHECK IS LOGEDIN MANAGER HAS FULL RIGHTS
        if is_manager is None:
            property_assigned = db.registered_managers.find({'username': login_data})
            property_assigned_dict = {property for doc in property_assigned if 'properties' in doc for property in doc['properties']}
            if not property_assigned_dict:
                flash('You are not managing any property!')
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
                flash('You are not managing any property!')
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
                if len(replies) == 0:
                    replies = [{'Reply': 'No reply', 'who': 'N/A', 'reply_date': 'N/A'}]
                else:
                    # Sort replies by date, most recent first
                    replies = sorted(replies, key=lambda r: r['reply_date'], reverse=True)
                complaint_copy = complaint.copy()  # create a copy of complaint to avoid overwriting
                complaint_copy['_id'] = str(complaint['_id'])
                complaint_copy['tenantID'] = str(complaint['tenantID'])
                complaint_copy['replies'] = [{'Reply': reply['Reply'], 'who': reply['who'], 'reply_date': reply['reply_date'].strftime('%Y-%m-%d %H:%M') if reply['reply_date'] != 'N/A' else 'N/A'} for reply in replies]
                complaints.append(complaint_copy)
        # Sort complaints by date, most recent first
        complaints = sorted(complaints, key=lambda c: c['complained_on'], reverse=True)
        # Remove duplicates
        complaints = list({v['_id']: v for v in complaints}.values())
        session['complaints'] = complaints
        return render_template('resolve complaints.html',complaints=complaints,resolved_complaints=resolved_complaints, dp=dp_str)
            
############RESOLVE COMPLAINTS BY MANAGER###########
@app.route('/update-complaint', methods=['POST'])
def update_complaint():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        if 'complaints' in session:
            complaints = session.get('complaints')
            for complaint in complaints:
                if 'Reply_' + str(complaint['_id']) in request.form:
                    Reply = request.form.get('Reply_' + str(complaint['_id']))
                    client_time = request.form.get('client_time')
                    client_time = datetime.fromisoformat(client_time)
                    time_zone_offset = int(request.form.get('time_zone_offset'))
                    adjusted_time = client_time + timedelta(hours=time_zone_offset)
                    db.tenant_complaints_replies.insert_one({'complaintID': ObjectId(complaint['_id']),
                                                             'Reply': Reply,
                                                             'who': login_data,
                                                             'reply_date': adjusted_time})
                    
                    tenant_complaint_id = db.tenant_complaints.find_one({'_id': ObjectId(complaint['_id'])})
                    tenant_object_id = db.tenant_user_accounts.find_one({'_id': tenant_complaint_id['tenantID']})
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
                        <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com">Login</a></b></p>
                        <p>Best Regards,</p>
                        <p>Mich Manage</p>
                        </body>
                        </html>
                        """
                        mail.send(msg)

            company = db.registered_managers.find_one({'username': login_data})
            if 'dp' in company:
                # Convert the base64 data back to bytes
                dp = base64.b64decode(company['dp'])
                # Convert bytes to string for HTML rendering
                dp_str = base64.b64encode(dp).decode()
            else:
                dp_str = None
            is_manager = db.managers.find_one({'manager_email': company['email']})
            if is_manager is None:
                query = {'username': login_data, 'company_name': company['company_name']}
            else:
                query = {'company_name': company['company_name']}
            properties = db.property_managed.find(query)
            if len(list(db.property_managed.find(query))) == 0:
                flash('You are not managing any property!')
                return redirect('/register')
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
                        if len(replies) == 0:
                            replies = [{'Reply': 'No reply', 'who': 'N/A', 'reply_date': 'N/A'}]
                        else:
                            # Sort replies by date, most recent first
                            replies = sorted(replies, key=lambda r: r['reply_date'], reverse=True)
                        complaint_copy = complaint.copy()  # create a copy of complaint to avoid overwriting
                        complaint_copy['_id'] = str(complaint['_id'])
                        complaint_copy['tenantID'] = str(complaint['tenantID'])
                        complaint_copy['replies'] = [{'Reply': reply['Reply'], 'who': reply['who'], 'reply_date': reply['reply_date'].strftime('%Y-%m-%d %H:%M') if reply['reply_date'] != 'N/A' else 'N/A'} for reply in replies]
                        complaints.append(complaint_copy)
                # Sort complaints by date, most recent first
                complaints = sorted(complaints, key=lambda c: c['complained_on'], reverse=True)
                # Remove duplicates
                complaints = list({v['_id']: v for v in complaints}.values())
                session['complaints'] = complaints
                return render_template('resolve complaints.html',complaints=complaints, resolved_complaints=resolved_complaints, dp=dp_str)
        else:
            flash('Login first')
            return redirect('/')
        
##########RESOLVING COMPLAINTS AFTER SOLVING THEM#########
@app.route('/resolved-complaints/<complaint_id>', methods=["GET", "POST"])
def resolved_complaints(complaint_id):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
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
            mail.send(msg)
        flash('Complaint was resolved')
        return redirect('/resolve-complaints')
       
#############ADD PROPERTY####################
@app.route('/add-property', methods=["POST"])
def add_property():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
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
            flash('Maximum number of properties is reached')
            return redirect('/load-dashboard-page')
        elif is_manager['amount_per_month'] == 150000 and properties>=30:
            flash('Maximum number of properties is reached')
            return redirect('/load-dashboard-page')
        elif is_manager['amount_per_month'] == 200000 and properties>=50:
            flash('Maximum number of properties is reached')
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
                flash('Property was added successfully')
                return redirect('/load-dashboard-page')
            else:
                flash('This Property is in the database')
                return redirect('/load-dashboard-page')

########LOAD TENANT INFO################
@app.route('/update-tenant-info')
def update_tenant_info():
    login_data = session.get('login_username')
    current_year = datetime.now().year
    if login_data is None:
        flash('Login first')
        return redirect('/')
    
    company = db.registered_managers.find_one({'username': login_data})
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
        flash('No tenant data found')
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
                    amount_demanded += (tenant['section_value'] - tenant['available_amount']) + amount_next_month                    
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

@app.route('/get_receipt', methods=['GET'])
def get_receipt():
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

###########UPDATE TENANT INFO################
@app.route('/update', methods=['POST'])
def update():
    login_data = session.get('login_username')
    current_year = datetime.now().year
    if login_data is None:
        flash('Login first') 
        return redirect('/')
    else:
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

        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
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
                flash('Selected period was fully paid')
            else:
                if old_data['available_amount'] < section_value:
                    flash('First fully update current/previous period')
                else:
                    available_amount = new_amount

                    balance = section_value - available_amount
                    # Create a payment receipt PDF file
                    buffer = BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=letter)

                    # QR Code Generation
                    url = f'https://michmanager.onrender.com/get_receipt?tenantEmail={tenantEmail}&propertyName={propertyName}&selected_section={selected_section}&months_paid={months_paid}&year={date.year}'
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
                                    <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                                    <p>Best Regards,</p>
                                    <p>Mich Manage</p>
                                    </body>
                                    </html>
                                    """

                                    # Attach the PDF receipt to the email
                                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                    # Send the email
                                    mail.send(msg)
                                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                flash(f"Updates for {old_data['tenantName']} were successful")
                            else:
                                db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
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
                                    <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                                    <p>Best Regards,</p>
                                    <p>Mich Manage</p>
                                    </body>
                                    </html>
                                    """

                                    # Attach the PDF receipt to the email
                                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                    # Send the email
                                    mail.send(msg)

                                if '_id' in old_data:
                                    del old_data['_id']
                                db.old_tenant_data.insert_one(old_data)
                                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                flash(f"Updates for {old_data['tenantName']} were successful")
                        elif date.year < old_date.year:
                            db.old_tenant_data.insert_one(new_data)
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
                                <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                mail.send(msg)
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful")
                        else:
                            db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
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
                                <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                mail.send(msg)
                            if '_id' in old_data:
                                del old_data['_id']
                            db.old_tenant_data.insert_one(old_data)
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful")
                    elif available_amount > section_value:  
                        flash("Enter amount that does not exceed section value")

                    else:
                        payment_completion = 'Full'
                        new_data['payment_completion'] = payment_completion

                        if date.year == old_date.year:
                            if field_month > months_paid_selected:
                                db.old_tenant_data.insert_one(new_data)
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
                                    <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                                    <p>Best Regards,</p>
                                    <p>Mich Manage</p>
                                    </body>
                                    </html>
                                    """

                                    # Attach the PDF receipt to the email
                                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                    # Send the email
                                    mail.send(msg)
                                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                flash(f"Updates for {old_data['tenantName']} were successful")
                            else:
                                db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
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
                                    <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                                    <p>Best Regards,</p>
                                    <p>Mich Manage</p>
                                    </body>
                                    </html>
                                    """

                                    # Attach the PDF receipt to the email
                                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                    # Send the email
                                    mail.send(msg)
                                if '_id' in old_data:
                                    del old_data['_id']
                                db.old_tenant_data.insert_one(old_data)
                                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                                flash(f"Updates for {old_data['tenantName']} were successful")
                        elif date.year < old_date.year:
                            db.old_tenant_data.insert_one(new_data)
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
                                <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                mail.send(msg)
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful")
                        else:
                            db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
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
                                <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                                <p>Best Regards,</p>
                                <p>Mich Manage</p>
                                </body>
                                </html>
                                """

                                # Attach the PDF receipt to the email
                                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                                # Send the email
                                mail.send(msg)
                            if '_id' in old_data:
                                del old_data['_id']
                            db.old_tenant_data.insert_one(old_data)
                            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantName': old_data['tenantName'], 'timestamp': datetime.now()})
                            flash(f"Updates for {old_data['tenantName']} were successful")

        elif field_month == months_paid_selected:
            if old_data['available_amount'] == section_value:
                flash('Period selected is fully paid')
            else:
                available_amount = new_amount + old_amount

                balance = section_value - available_amount

                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)

                # QR Code Generation
                url = f'https://michmanager.onrender.com/get_receipt?tenantEmail={tenantEmail}&propertyName={propertyName}&selected_section={selected_section}&months_paid={months_paid}&year={date.year}'
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
                            <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                            <p>Best Regards,</p>
                            <p>Mich Manage</p>
                            </body>
                            </html>
                            """

                            # Attach the PDF receipt to the email
                            msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                            # Send the email
                            mail.send(msg)
                        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                        flash(f"Updates for {old_data['tenantName']} were successful")
                    elif date.year < old_date.year:
                        db.old_tenant_data.insert_one(new_data)
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
                            <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                            <p>Best Regards,</p>
                            <p>Mich Manage</p>
                            </body>
                            </html>
                            """

                            # Attach the PDF receipt to the email
                            msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                            # Send the email
                            mail.send(msg)
                        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                        flash(f"Updates for {old_data['tenantName']} were successful")
                    else:
                        db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
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
                            <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                            <p>Best Regards,</p>
                            <p>Mich Manage</p>
                            </body>
                            </html>
                            """

                            # Attach the PDF receipt to the email
                            msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                            # Send the email
                            mail.send(msg)
                        if '_id' in old_data:
                            del old_data['_id']
                        db.old_tenant_data.insert_one(old_data)
                        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                        flash(f"Updates for {old_data['tenantName']} were successful")
                elif available_amount > section_value:        
                    flash("Enter amount that does not exceed section value")
                else:
                    payment_completion = 'Full'
                    new_data['payment_completion'] = payment_completion
                    if date.year == old_date.year:
                        db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
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
                            <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                            <p>Best Regards,</p>
                            <p>Mich Manage</p>
                            </body>
                            </html>
                            """

                            # Attach the PDF receipt to the email
                            msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                            # Send the email
                            mail.send(msg)
                        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                        flash(f"Updates for {old_data['tenantName']} were successful")
                    elif date.year < old_date.year:
                        db.old_tenant_data.insert_one(new_data)
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
                            <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                            <p>Best Regards,</p>
                            <p>Mich Manage</p>
                            </body>
                            </html>
                            """

                            # Attach the PDF receipt to the email
                            msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                            # Send the email
                            mail.send(msg)
                        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                        flash(f"Updates for {old_data['tenantName']} were successful")
                    else:
                        db.tenants.update_one({'_id': ObjectId(old_data['_id'])}, {'$set': new_data})
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
                            <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                            <p>Best Regards,</p>
                            <p>Mich Manage</p>
                            </body>
                            </html>
                            """

                            # Attach the PDF receipt to the email
                            msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                            # Send the email
                            mail.send(msg)
                        if '_id' in old_data:
                            del old_data['_id']
                        db.old_tenant_data.insert_one(old_data)
                        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
                        flash(f"Updates for {old_data['tenantName']} were successful")
                
        tenant_data = []
        is_manager = db.managers.find_one({'manager_email': company['email']}) is not None

        if not is_manager:
            property_assigned = db.registered_managers.find({'username': login_data})
            property_assigned_dict = {property for doc in property_assigned if 'properties' in doc for property in doc['properties']}
            new_tenants = []
            for property in property_assigned_dict:
                properties_query = {"propertyName": property}
                new_tenants_data = list(db.tenants.find(properties_query))
                if new_tenants_data:
                    for new_tenant in new_tenants_data:
                        new_tenants.append(new_tenant)
            property_managed = []
            for property in property_assigned_dict:
                properties_query = {"propertyName": property}
                property_data = list(db.property_managed.find(properties_query))
                if property_data:
                    for property in property_data:
                        property_managed.append(property)
        else:
            new_tenants = list(db.tenants.find(query))
            property_managed = list(db.property_managed.find(query))
        for tenant in new_tenants:
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
                        amount_demanded += (tenant['section_value'] - tenant['available_amount']) + amount_next_month
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
                
        return render_template("tenant information.html", tenant_data=tenant_data, dp=dp_str, current_year=current_year)

########LOAD PROPERTY DATA ################
def get_property_data(properties):
    property_data = []
    for property in properties:
        property_data.append((property['propertyName'], property['type'], property['property_value'],
                              property['address'], property['owner_name'], property['owner_phone']))
    return property_data

@app.route('/view-property-info')
def view_property_info():
    username = session.get('login_username')
    if username is None:
        flash('Login first')
        return redirect('/')
    else:
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
                flash('We did not find property data')
                return redirect('/load-dashboard-page')
            
            property_data = get_property_data(properties)
            return render_template('property information.html', property_data=property_data, dp=dp_str)

#####UPDATE PROPERTY INFO#############
@app.route('/update-property/<propertyName>')
def selected_property(propertyName):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
    return render_template('update property information.html',propertyName=propertyName, dp=dp_str)

##POSTING NEW PROPERTY INFORMATION
@app.route('/update-property', methods=["POST"])
def update_property():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
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
        flash(f"{propertyName} was successfully updated")
        return redirect('/view-property-info')

##VIEW MANAGER ACCOUNTS
def get_managers_data(registered_managers):
    managers = []
    for manager in registered_managers:
        managers.append((manager['name'], manager['email'], manager['phone_number'], manager['company_name']))
    return managers

@app.route('/view-user-accounts')
def view_user_accounts():
    # Get session data
    username = session.get('login_username')
    if username is None:
        flash('Login first')
        return redirect('/')

    # Get company data
    company = db.registered_managers.find_one({'username': username})
    dp_str = base64.b64encode(base64.b64decode(company.get('dp', ''))).decode() if 'dp' in company else None

    # Check if user is a manager
    is_manager = db.managers.find_one({'manager_email': company['email']}) is not None
    if not is_manager:
        flash("You do not have rights to view other users")
        return redirect('/load-dashboard-page')

    # Get registered managers data
    registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': username}}))
    if not registered_managers:
        flash("We did not find other registered users")
        return redirect('/load-dashboard-page')

    # Prepare managers data
    managers = get_managers_data(registered_managers)
    return render_template("view registered managers.html", managers=managers, dp=dp_str)


########DELETE PROPERTY################
@app.route('/delete_manager/<company_name>/<email>', methods=['POST'])
def delete_manager(company_name,email):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        manager = db.registered_managers.find_one({'company_name': company_name, 'email': email})
        company = db.managers.find_one({'name':company_name})
        managers = company['managers']
        for manager in managers:
            if email == manager:
                db.managers.update_one({'name': company_name}, {'$pull': {'managers': email}})
                db.registered_managers.delete_one({'company_name': company_name, 'email': email})
                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Delete manager', 'email':email, 'timestamp': datetime.now()})
        return redirect('/view-user-accounts')
    
########ADD NEW MANAGER EMAIL################
@app.route('/add-new-manager-email')
def add_new_manager_email():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        is_manager = db.managers.find_one({'manager_email': company['email']})
        if is_manager:
            return render_template('add new manager email.html', dp=dp_str)
        else:
            flash("You do not have rights to add managers")
            return redirect('/load-dashboard-page')

@app.route('/update-new-manager-email', methods=['POST'])
def update_new_manager_email():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        email = request.form.get('email')
        manager_found = db.registered_managers.find_one({'username': login_data})
        company = db.managers.find_one({'name':manager_found['company_name']})
        managers = company['managers']
        for manager in managers:
            if email == manager:
                flash('This email already exists')
                return redirect('/add-new-manager-email')
        db.managers.update_one({'name': manager_found['company_name']}, {'$push': {'managers': email}})
        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add new manager', 'email':email, 'timestamp': datetime.now()})
        flash('New manager email was successfully added')
        return redirect('/add-new-manager-email')

#######CLICK TO UPDATE TENANT#############
@app.route('/selected-tenant/<tenantName>/<tenantEmail>/<propertyName>/<selected_section>/<payment_type>/<amount>/<months_paid>/<date_last_paid>')
def selected_tenant(tenantName, tenantEmail, propertyName, selected_section, payment_type, amount, months_paid,date_last_paid):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first') 
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
    date_last_paid = datetime.strptime(date_last_paid, '%Y-%m-%d')
    return render_template('update tenant information.html',tenantName=tenantName,tenantEmail=tenantEmail,propertyName=propertyName,selected_section=selected_section,payment_type=payment_type,amount=amount,months_paid=months_paid,year=date_last_paid.year,dp=dp_str)
        
##########EDIT TENANT INFO###################
@app.route('/edit/<tenantName>/<email>/<property_name>/<selected_section>/<payment_type>')
def edit(tenantName, email, property_name, selected_section, payment_type):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        # Retrieve the tenant's info using the email
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        tenant = db.tenants.find_one({'propertyName': property_name, 'selected_section': selected_section, 'tenantName': tenantName, 'company_name': company['company_name']})
        if tenant is None:
            return "Tenant not found", 404
        # Pass the tenant's info to the template
        return render_template('edit.html',tenantName=tenantName, tenant=tenant, payment_type=payment_type, dp=dp_str)

############APPLY EDITS##############
@app.route('/make-edits', methods=["POST"])
def make_edits():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        tenantEmail = request.form.get('tenantEmail')
        propertyName = request.form.get('propertyName')
        selected_section = request.form.get('selected_section')
        company = db.registered_managers.find_one({'username': login_data})
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
            url = f'https://michmanager.onrender.com/get_receipt?tenantEmail={tenantEmail}&propertyName={propertyName}&selected_section={selected_section}&months_paid={{{tenant["months_paid"]}}}&year={date_last_paid.year}'
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
                <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """

                # Attach the PDF receipt to the email
                msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                # Send the email
                mail.send(msg)

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
                flash('Amount entered should not exceed section value')
                return redirect(url_for('edit', email=tenantEmail))
            else:
                payment_completion = 'Full'
            fields_to_update['payment_completion'] = payment_completion

        db.tenants.update_one({'propertyName': propertyName, 'selected_section': selected_section, 'tenantEmail':tenantEmail, 'company_name': company['company_name']},
                                {'$set': fields_to_update})

        flash('Tenant was successfully edited')
        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Edit tenant data', 'tenantEmail':tenantEmail, 'timestamp': datetime.now()})
        return redirect('/update-tenant-info')
        
###########VIEW TENANT RECEIPT###############
@app.route('/view-receipt/<tenant_email>/<property_name>/<selected_section>', methods=["GET"])
def view_receipt(tenant_email, property_name, selected_section):
    login_data = session.get('login_username')
    # Retrieve the tenant document using tenant_id
    tenant = db.tenants.find_one({'username': login_data, 'propertyName': property_name, 'selected_section': selected_section, 'tenantEmail': tenant_email})

    if tenant is not None and 'payment_receipt' in tenant:
        # Convert the base64 string back to bytes
        payment_receipt = base64.b64decode(tenant['payment_receipt'])

        # Create a BytesIO object from the PDF data
        pdf_io = io.BytesIO(payment_receipt)

        # Create the file name
        file_name = f"{property_name}_{selected_section}_{tenant["months_paid"]}_{tenant["year"]}.pdf"

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
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
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

        company = db.registered_managers.find_one({'username': login_data})

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
        url = f'https://michmanager.onrender.com/get_receipt?tenantEmail={tenantEmail}&propertyName={propertyName}&selected_section={selected_section}&months_paid={months_paid}&year={date_last_paid.year}'
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
            flash('Maximum number of tenants is reached')
            return redirect('/load-dashboard-page')
        elif is_manager['amount_per_month'] == 150000 and num_tenants>=100:
            flash('Maximum number of tenants is reached')
            return redirect('/load-dashboard-page')
        elif is_manager['amount_per_month'] == 200000 and num_tenants>=200:
            flash('Maximum number of tenants is reached')
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
                    <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                    <p>Best Regards,</p>
                    <p>Mich Manage</p>
                    </body>
                    </html>
                    """

                    # Attach the PDF receipt to the email
                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                    # Send the email
                    mail.send(msg)
                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add tenant data', 'tenantName': tenantName, 'timestamp': datetime.now()})
                flash('Tenant was successfully added')
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
                    <p><b><a href="https://michmanage.onrender.com">Visit us on</a></b></p>
                    <p>Best Regards,</p>
                    <p>Mich Manage</p>
                    </body>
                    </html>
                    """

                    # Attach the PDF receipt to the email
                    msg.attach("Rent Payment Receipt.pdf", "application/pdf", pdf_data)

                    # Send the email
                    mail.send(msg)
                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add tenant data', 'tenantName':tenantName, 'timestamp': datetime.now()})
                flash('Tenant was successfully added')
                return redirect('/load-dashboard-page')
            else:
                flash('Section is already assigned')
                return redirect('/load-dashboard-page')

########DELETE TENANT################
@app.route('/delete_tenant/<tenantEmail>/<propertyName>/<selected_section>')
def delete_tenant(tenantEmail, propertyName, selected_section):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        tenants = db.tenants.find_one({'company_name': company['company_name'], 'tenantEmail': tenantEmail, 'propertyName': propertyName, 'selected_section': selected_section})
        # Remove the _id field
        if '_id' in tenants:
            del tenants['_id']
        db.old_tenant_data.insert_one(tenants)
        db.old_tenant_data.update_one({'company_name': company['company_name'], 'tenantEmail': tenantEmail, 'propertyName': propertyName, 'selected_section': selected_section}, {'$set': {'status': 'deleted'}})
        db.tenants.delete_one({'company_name': company['company_name'], 'tenantEmail': tenantEmail, 'propertyName': propertyName, 'selected_section': selected_section})
        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Delete tenant', 'tenantName': tenants['tenantName'], 'timestamp': datetime.now()})
        return redirect('/update-tenant-info')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/admin-login', methods=["POST"])
def adminlogin():
    email = request.form.get('email')
    entered_password = request.form.get('password')
    password = entered_password.encode('utf-8')
    
    user = db.admin.find_one({'email':email})
    if user is None:
        flash('Not an admin')
        return redirect('/admin')
    else:
        stored_password = user['password'].encode('utf-8')
        if bcrypt.checkpw(password, stored_password):
            session.permanent = False
            session['admin_email'] = user['email']
            session['logged_in'] = True
            send_emails = db.send_emails.find_one({'emails': "yes"})
            if send_emails is not None:
                session['send_emails'] = "yes"
            else:
                session['send_emails'] = "no"
            return render_template("managers accounts.html")
        else:
            flash('Wrong Password')
            return redirect('/admin')
        
@app.route('/add-property-manager-page')
def add_property_manager_page():
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first')
        return redirect('/admin')
    else:
        return render_template("managers accounts.html")

##########ADD PROPERTY MANAGER COMPANY#############
@app.route('/add-property-manager', methods=["POST"])
def add_property_manager():
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first')
        return redirect('/admin')
    else:
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
        managers = db.managers.find_one({'name': name})
        if managers is None:
            manager = {'email': email, 'name': name, 'managers': allowed_managers,
                    'manager_email': manager_email, 'last_subscribed_on': datetime.now(),
                    'subscribed_days': subscribed_days, 'amount_per_month': amount_per_month}
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
                <p><b style="font-size: 20px;"><a href="https://michmanage.onrender.com/register">Register Here</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                mail.send(msg)

            flash('Company managers can now create accounts')
            return render_template("managers accounts.html", user_data=user_data)
        else:
            flash('Company already registered')
            return render_template("managers accounts.html")

#######NEW SUBSCRIPTION PAGE###############
@app.route("/new-subscription")
def new_subscription():
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first')
        return redirect('/admin')
    else:
        companies = db.managers.find()
        cursor = list(companies)
        if len(cursor) == 0:
            flash('We found no companies')
            return render_template("managers accounts.html")
        else:
            df = pd.DataFrame(cursor)
            company_names = df['name']
        return render_template("new_subscription.html", company_names=company_names)
    
#######STORING NEW SUBSCRIPTION###############
@app.route("/new-subscription-initiated", methods=["POST"])
def new_subscription_initiated():
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first')
        return redirect('/admin')
    else:
        company_name = request.form.get('company_name')
        last_subscribed_on_str = request.form.get('last_subscribed_on')
        # Convert the string to a datetime object
        last_subscribed_on = datetime.strptime(last_subscribed_on_str, '%Y-%m-%d')
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
        company = db.managers.find_one({'name': company_name})
        remaining_days = (company['last_subscribed_on'] + timedelta(days=company['subscribed_days']) - datetime.now()).days
        if remaining_days <= 0:
            subscribed_days = subscribed_days + 0
            db.managers.update_one({'name': company_name},{'$set': {'last_subscribed_on': last_subscribed_on, 'subscribed_days': subscribed_days, 'amount_per_month': amount_per_month}})
            flash('New Subscription was added')
            return render_template("managers accounts.html")
        else:
            if last_subscribed_on <= company['last_subscribed_on']:
                companies = db.managers.find()
                cursor = list(companies)
                df = pd.DataFrame(cursor)
                company_names = df['name']
                flash('Enter a newer date')
                return render_template("new_subscription.html", company_names=company_names)
            else:
                subscribed_days = subscribed_days + remaining_days
                db.managers.update_one({'name': company_name},{'$set': {'last_subscribed_on': last_subscribed_on, 'subscribed_days': subscribed_days, 'amount_per_month': amount_per_month}})
                flash('New Subscription was added')
                return render_template("managers accounts.html")
                

#########FUNCTION TO CREATE A BAR CHART################
def create_bar_chart(df, variable_name, title, xaxis_title, yaxis_title):
    unique_values = df[variable_name].unique()
    value_counts = df[variable_name].value_counts()

    fig = go.Figure(data=[go.Bar(x=unique_values, 
                                  y=value_counts, 
                                  text=value_counts, 
                                  textposition='auto')],
                    layout=go.Layout(title=title,
                                     xaxis=dict(title=xaxis_title),
                                     yaxis=dict(title=yaxis_title)))
    
    bar_chart = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return bar_chart

#########FUNCTION TO CREATE A STACKED BAR CHART################
def create_stacked_bar_chart(df, variable_name, title, xaxis_title, yaxis_title):
    # Pre-calculate grouped data and unique values
    df_grouped = df.groupby(variable_name)['available_amount'].sum().reset_index()
    df_unique = df.drop_duplicates(variable_name)[[variable_name, 'total_property_value']]

    # Calculate demanded amount
    df_unique['demanded_amount'] = df_unique['total_property_value'] - df_grouped['available_amount']

    # Create traces
    trace1 = go.Bar(x=df_grouped[variable_name], 
                    y=df_grouped['available_amount'], 
                    name='Collected',
                    text=df_grouped['available_amount'], 
                    textposition='auto',
                    marker_color='purple')

    # Only include cases where demanded amount is greater than 0
    df_demanded = df_unique[df_unique['demanded_amount'] > 0]
    trace2 = go.Bar(x=df_demanded[variable_name], 
                    y=df_demanded['demanded_amount'], 
                    name='Demanded',
                    text=df_demanded['demanded_amount'], 
                    textposition='auto',
                    marker_color='red')

    # Create a figure with layout
    fig = go.Figure(data=[trace1, trace2],
                    layout=go.Layout(
                        title={
                            'text': title,
                            'y':0.9,
                            'x':0.5,
                            'xanchor': 'center',
                            'yanchor': 'top',
                            'font': dict(size=12)
                        },
                        xaxis_title=xaxis_title,
                        yaxis_title=yaxis_title,
                        legend=dict(
                            yanchor="bottom",
                            y=0.99,
                            xanchor="left",
                            x=0.01
                        ),
                        barmode='stack'
                    ))

    # Convert the figure to JSON
    stacked_bar_chart = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return stacked_bar_chart

##LINE CHART
def create_line_chart(df, title, xaxis_title, yaxis_title):
    # Filter rows to only include dates in the current year
    most_recent_year = df['date_last_paid'].dt.year.max()
    df = df[df['date_last_paid'].dt.year == most_recent_year]

    # Ensure 'months_paid' is of type 'category' and ordered
    df['months_paid'] = pd.Categorical(df['months_paid'], categories=calendar.month_name[1:], ordered=True)

    # Group by property name and month, and calculate the sum of amount paid
    df_grouped = df.groupby(['propertyName', 'months_paid'])['available_amount'].sum().reset_index()

    # Create the line chart
    fig = px.line(df_grouped, x='months_paid', y='available_amount', color='propertyName', title=title)
    # Customize hover data
    fig.update_traces(
        hovertemplate='Property: %{data.name}<br>Month: %{x}<br>Amount: %{y}',
        hoverinfo='skip'
    )

    # Set the axis titles
    fig.update_xaxes(title_text=xaxis_title)
    fig.update_yaxes(title_text=yaxis_title)

    # Set the title with reduced font size
    fig.update_layout(
        title={
            'text': title,
            'y':0.9,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': dict(
                size=15
            )
        },
        legend=dict(
            yanchor="top",
            y=-0.2,  # Adjusts the y position
            xanchor="center",
            x=0.5,  # Adjusts the x position
            orientation="v"  # Makes the legend horizontal
        )
    )

    # Convert the figure to JSON
    line_chart = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return line_chart

#############DASHBOARD PAGE#######################
@app.route('/load-dashboard-page', methods=["GET", "POST"])
def load_dashboard_page():
    login_data = session.get('login_username')
    # get the current month number
    current_month = datetime.now().month
    # convert the month number to its name
    month_name = calendar.month_name[current_month]
    # capitalize the first letter
    month_name = month_name.capitalize()

    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
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

        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        is_manager = db.managers.find_one({'manager_email': company['email']})        

        if is_manager is None:
            user_query  = {'username': login_data, 'company_name': company['company_name']}
            special_user_query = {'username': login_data, 'company_name': company['company_name'],'status': {'$ne': 'deleted'}}
        else:
            user_query  = {'company_name': company['company_name']}
            special_user_query = {'company_name': company['company_name'],'status': {'$ne': 'deleted'}}
        projection = {'payment_receipt': 0, 'username': 0, 'company_name': 0, 'tenantEmail': 0, 'tenantPhone': 0, 'payment_mode': 0}
        if startdate_on_str and enddate_on_str:
            startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
            enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
            latest_year = enddate.year

            date_query = {'date_last_paid': {'$gte': startdate, '$lte': enddate}, 'status': {'$ne': 'deleted'}}
            date_query.update(user_query)

            current_tenant_data = list(db.tenants.find(date_query, projection))

            old_tenant_data = list(db.old_tenant_data.find(date_query, projection))

            month_name = f"{startdate_on_str} to {enddate_on_str}"
        else:
            latest_document = db.tenants.find_one(sort=[('date_last_paid', -1)])
            if latest_document is None:
                latest_document = db.old_tenant_data.find_one(sort=[('date_last_paid', -1)])

            if latest_document is None:
                property_data = list(db.property_managed.find(user_query))
                if len(property_data) == 0:
                    flash('No property data found')
                    return render_template('dashboard.html',dp=dp_str)
                else:
                    property_data_list = list(db.property_managed.find(user_query))
                    tenant_data_cursor = db.tenants.find(user_query)
                    
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

                    flash('No tenant data found')
                    return render_template('dashboard.html',property_data=property_data_dict, property_occupancy=property_occupancy, dp=dp_str)
            latest_year = latest_document['date_last_paid'].year

            startdate = datetime(latest_year, 1, 1)
            enddate = datetime(latest_year, 12, 31, 23, 59, 59)

            date_query = {'date_last_paid': {'$gte': startdate, '$lte': enddate}, 'status': {'$ne': 'deleted'}}
            date_query.update(user_query)

            current_tenant_data = list(db.tenants.find(date_query, projection))

            old_tenant_data = list(db.old_tenant_data.find(date_query, projection))

            month_name = f"{startdate.strftime('%Y-%m-%d')} to {enddate.strftime('%Y-%m-%d')}"
        
        overdue_tenants = []
        count_current_tenants = db.tenants.count_documents(special_user_query)
        overdue_current_tenant_data = list(db.tenants.find(special_user_query))
        if overdue_current_tenant_data:
            for tenant in overdue_current_tenant_data:
                last_payment_month = month_mapping.get(tenant['months_paid'], 0)
                last_payment_date = datetime(year=tenant['year'], month=last_payment_month, day=1)
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
                    overdue_tenants.append((tenant['tenantName'], tenant['propertyName'],tenant['selected_section'], remaining_days, time_unit, overdue_status))
        else:
            overdue_tenants = []
        overdue_tenants = sorted(overdue_tenants, key=lambda x: x[3], reverse=True)

        property_data = list(db.property_managed.find(user_query))
        if len(property_data) == 0:
            flash('No property data found')
            return render_template('dashboard.html',dp=dp_str)
        else:
            property_data_list = list(db.property_managed.find(user_query))
            tenant_data_cursor = db.tenants.find(user_query)
            
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
                current_data = pd.DataFrame(current_tenant_data)
                old_data = pd.DataFrame(old_tenant_data)

                startdate = datetime(enddate.year, 1, 1)
                enddate = datetime(enddate.year, 12, 31, 23, 59, 59)

                date_query = {'date_last_paid': {'$gte': startdate, '$lte': enddate}, 'status': {'$ne': 'deleted'}}
                date_query.update(user_query)

                current_line = pd.DataFrame(list(db.tenants.find(date_query, projection)))
                old_line = pd.DataFrame(list(db.old_tenant_data.find(date_query, projection)))

                df2_line = pd.concat([current_line, old_line], ignore_index=True)
                df2 = pd.concat([current_data, old_data], ignore_index=True)
                df3 = pd.DataFrame(property_data)

                # Create a new DataFrame with 'propertyName' and 'amount' from df_combined_tenants
                property_performance = df2[['propertyName', 'available_amount', 'months_paid', 'date_last_paid']].copy()
                property_performance_line = df2_line[['propertyName', 'available_amount', 'months_paid', 'date_last_paid']].copy()
                # Create a dictionary mapping propertyName to property_value from df3
                property_value_dict = df3.set_index('propertyName')['property_value'].to_dict()
                # Create a new column in df_new based on the propertyName column
                property_performance['property_value'] = property_performance['propertyName'].map(property_value_dict)
                # Calculate the number of months paid for each property
                property_performance['months_paid_count'] = property_performance.groupby('propertyName')['months_paid'].transform('nunique')
                # Calculate the total property value
                property_performance['total_property_value'] = property_performance['months_paid_count'] * property_performance['property_value']

                ###total number of property managed
                count_property = len(df3.index)
                available_amount = df2['available_amount'].sum()

                ###CHARTS
                ###bar charts from property type
                property_type_bar_chart = create_bar_chart(df3, 'type', 'Property Type', 'Property type', 'Count')
                ######bar chart for property value and amount from tenants
                property_performance_bar_chart = create_stacked_bar_chart(property_performance, 'propertyName', f'Property Performance', 'Property Name', 'Value')
                line_chart = create_line_chart(property_performance_line, f'Rent Payments {enddate.year}', 'Month', 'Amount Paid')

                return render_template('dashboard.html',count_property=count_property,available_amount=available_amount,
                                    count_current_tenants=count_current_tenants, property_data=property_data_dict, property_occupancy=property_occupancy,
                                    property_type_bar_chart=property_type_bar_chart,property_performance_bar_chart=property_performance_bar_chart,
                                    line_chart=line_chart, month_name=month_name,overdue_tenants=overdue_tenants, dp=dp_str)
            else:
                flash('No tenant data found')
                return render_template('dashboard.html', property_data=property_data_dict, property_occupancy=property_occupancy, dp=dp_str)
        
#############MANAGER DOWNLOAD DATA######################
@app.route('/download', methods=["POST"])
def download():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})
        is_manager = db.managers.find_one({'manager_email': company['email']})
        if is_manager is None:
            user_query  = {'username': login_data, 'company_name': company['company_name'], 'date_last_paid': {'$gte': startdate, '$lte': enddate}}
        else:
            user_query  = {'company_name': company['company_name'], 'date_last_paid': {'$gte': startdate, '$lte': enddate}}
        projection = {'payment_receipt': 0, '_id': 0, 'marital_status': 0, 'age': 0, 'available_amount': 0, 'payment_completion': 0,
                      'currency': 0, 'payment_status': 0,	'status': 0,	'household_size': 0}
    
        current_tenant_data = list(db.tenants.find(user_query, projection))

        old_tenant_data = list(db.old_tenant_data.find(user_query, projection))

        if len(current_tenant_data) > 0 or len(old_tenant_data) > 0:                
            # property_data = list(db.property_managed.find(company_query, projection2))

            df1 = pd.DataFrame(old_tenant_data)
            df2 = pd.DataFrame(current_tenant_data)
            # df3 = pd.DataFrame(property_data)

            df_combined_tenants = pd.concat([df1, df2], ignore_index=True)

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
                'available_amount': 'Available amount',
                'payment_completion': 'Payment completion',
                'currency': 'Currency',
                'payment_status': 'Payment status',
                'status': 'Status',
                'household_size': 'Household size'
            }

            df_combined_tenants.rename(columns=new_column_names, inplace=True)

            # Set the multi-level index and sort the DataFrame
            month_order = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6, 'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12}
            df_combined_tenants['Month paid'] = pd.Categorical(df_combined_tenants['Month paid'], categories=month_order.keys(), ordered=True)
            df_combined_tenants.sort_values(by=['Year', 'Month paid'], inplace=True)

            # Create a BytesIO buffer to write the Excel file
            output = BytesIO()

            # Write the DataFrame to the Excel file using openpyxl
            wb = Workbook()

            # Create a worksheet
            ws = wb.active
            ws.title = "Tenants"

            # Write column names
            for col_idx, col_name in enumerate(df_combined_tenants.columns, start=2):
                ws.cell(row=1, column=col_idx, value=col_name)

            # Write data rows
            for r_idx, row in enumerate(dataframe_to_rows(df_combined_tenants, index=False), start=2):
                for c_idx, value in enumerate(row, start=1):
                    ws.cell(row=r_idx, column=c_idx, value=value)

            # Set a password
            file_password = generate_file_password()
            ws.protection.set_password(file_password)

            existing_password = db.file_passwords.find_one({'username':login_data})
            if existing_password:
                db.file_passwords.delete_one({'username':login_data})
            db.file_passwords.insert_one({'username':login_data, 'password': file_password, 'detail': 'Tenant data file'})

            # Save the workbook with encryption
            protected_file_path = tempfile.NamedTemporaryFile(delete=False, suffix="_protected.xlsx").name
            wb.save(filename=protected_file_path)

            # Clean up temporary file
            wb.close()

            # Load the workbook again to delete the first row
            wb = load_workbook(protected_file_path)
            ws = wb.active
            ws.delete_rows(1)

            # Save the workbook
            wb.save(protected_file_path)

            # Clean up temporary file
            wb.close()

            # Read the password-protected file
            with open(protected_file_path, 'rb') as f:
                protected_data = f.read()

            # Clean up protected file
            os.remove(protected_file_path)

            # Create the response
            response = make_response(protected_data)
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_{startdate_on_str}_{enddate_on_str}.xlsx"
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

            return response
        else:
            flash('No tenant data found')
            return redirect('/load-dashboard-page')
        
#####FILE PASSWORDS
@app.route('/view-file-passwords')
def view_file_passwords():
    username = session.get('login_username')
    if username is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': username})
        dp_str = base64.b64encode(base64.b64decode(company.get('dp', ''))).decode() if 'dp' in company else None
        
        file_passwords = list(db.file_passwords.find({'username': username}))
        if len(file_passwords)==0:
            flash('No encryption keys found')
            return redirect('/load-dashboard-page')
        else:
            found_passwords = []
            for password in file_passwords:
                found_passwords.append(password)
        return render_template('file passwords.html', found_passwords=found_passwords, dp=dp_str)

####MANAGE CONTRACTS
@app.route('/manage-contracts')
def manage_contracts():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
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
            flash('You are not managing any contracts!')
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
        
@app.route('/upload-contract-page')
def upload_contract_page():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
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
            flash('No tenant data found')
            return redirect('/load-dashboard-page')
        else:
            tenant_names = []
            for tenant in tenants:
                tenant_names.append(tenant['tenantName'])
        return render_template('add contracts.html',tenant_names=tenant_names, dp=dp_str)

@app.route('/upload-contract', methods=['POST'])
def upload_contract():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        if 'contract_document' not in request.files:
            flash("No file part")
            return redirect('/upload-contract-page')
        file = request.files['contract_document']
        if file.filename == '':
            flash("No file selected")
            return redirect('/upload-contract-page')
        if file:
            filename = secure_filename(file.filename)
            file_id = fs.put(file.read(), filename=filename)
            company = db.registered_managers.find_one({'username': login_data})
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
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add new contract', 'file_id':file_id, 'timestamp': datetime.now()})
            flash("Contract was uploaded successfully")
            return redirect('/upload-contract-page')

########DELETE CONTRACTS################
@app.route('/delete-contract/<contractID>')
def delete_contract(contractID):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        contract = db.contracts.find_one({'_id': ObjectId(contractID)})
        # Remove the _id field
        if '_id' in contract:
            del contract['_id']
        db.old_contracts.insert_one(contract)
        db.contracts.delete_one({'_id': ObjectId(contractID)})
        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Delete contract', 'contractID':contractID, 'timestamp': datetime.now()})
        return redirect('/manage-contracts')

##UPDATE CONTRACTS
@app.route('/update-contract/<contractID>/<company_name>/<receiver>')
def selected_contract(contractID, company_name, receiver):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
    return render_template('update contract.html',contractID=contractID,company_name=company_name,receiver=receiver,dp=dp_str)

@app.route('/updated-contract', methods=['POST'])
def updated_contract():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        if 'contract_document' not in request.files:
            flash("No file part")
            return redirect('/manage-contracts')
        file = request.files['contract_document']
        if file.filename == '':
            flash("No file selected")
            return redirect('/manage-contracts')
        if file:
            filename = secure_filename(file.filename)
            file_id = fs.put(file.read(), filename=filename)
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
                db.audit_logs.insert_one({'user': login_data, 'Activity': 'Update contract', 'file_id':file_id, 'timestamp': datetime.now()})
                flash("Contract was updated successfully")
                return redirect('/manage-contracts')
            else:
                flash("Contract was not found")
                return redirect('/manage-contracts')
            
@app.route('/download-contract/<fileID>')
def download_contract(fileID):
    file = fs.get(ObjectId(fileID))
    response = make_response(file.read())
    response.mimetype = 'application/octet-stream'
    response.headers.set('Content-Disposition', 'attachment', filename=file.filename)
    return response

####MANAGE USER RIGHTS
@app.route('/manage-user-rights')
def manage_user_rights():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        
        # Get registered managers data
        registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': login_data}}))
        if not registered_managers:
            flash("We did not find other registered users")
            return redirect('/load-dashboard-page')

        # Prepare managers data
        managers = get_managers_data(registered_managers)

        return render_template('user rights.html',managers=managers,dp=dp_str)
    
@app.route('/manage-user-rights-page/<email>/<company_name>')
def manage_user_rights_page(email,company_name):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        manager = db.registered_managers.find_one({'email': email, 'company_name': company_name})
        add_properties = manager.get('add_properties', "no")
        add_tenants = manager.get('add_tenants', "no")
        update_tenant = manager.get('update_tenant', "no")
        edit_tenant = manager.get('edit_tenant', "no")
        
        return render_template('user rights page.html', email=email,company_name=company_name,
                               add_properties=add_properties,add_tenants=add_tenants,
                               update_tenant=update_tenant,edit_tenant=edit_tenant,dp=dp_str)

@app.route('/user-rights-initiated', methods=["POST"])
def user_rights_initiated():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        email = request.form.get('email')
        company_name = request.form.get('company_name')
        add_properties = request.form.get("add_properties")
        add_tenants = request.form.get("add_tenants")
        update_tenant = request.form.get("update_tenant")
        edit_tenant = request.form.get("edit_tenant")
        manage_contracts = request.form.get('manage_contracts')

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

        # Update the document with the non-empty fields
        db.registered_managers.update_one({'email': email, 'company_name': company_name}, {'$set': update_fields})
        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Change of user rights', 'email':email, 'timestamp': datetime.now()})
        flash("User rights were set successfully")
        return redirect('/manage-user-rights')
    
####ASSIGN PROPERTIES TO MANAGERS
@app.route('/assign-properties')
def assign_properties():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        
        # Get registered managers data
        registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': login_data}}))
        if not registered_managers:
            flash("We did not find other registered users")
            return redirect('/load-dashboard-page')

        # Prepare managers data
        managers = get_managers_data(registered_managers)

        return render_template('assign properties.html',managers=managers,dp=dp_str)
    
@app.route('/assign-properties-page/<name>/<email>/<company_name>')
def assign_properties_page(name,email,company_name):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        properties = db.property_managed.find({'company_name': company['company_name']}, {"propertyName": 1})
        property_names = [property['propertyName'] for property in properties]
        
        return render_template('assign properties page.html', property_names=property_names,name=name,email=email,company_name=company_name,dp=dp_str)
    
@app.route('/assign-properties-initiated', methods=["POST"])
def assign_properties_initiated():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
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
        flash(f"{propertyName} was assigned to {name}")
        return redirect('/assign-properties')

####UNASSIGN PROPERTIES FROM MANAGERS
@app.route('/unassign-properties')
def unassign_properties():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        
        # Get registered managers data
        registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': login_data}}))
        if not registered_managers:
            flash("We did not find other registered users")
            return redirect('/load-dashboard-page')

        # Prepare managers data
        managers = get_managers_data(registered_managers)

        return render_template('unassign properties.html',managers=managers,dp=dp_str)
    
@app.route('/unassign-properties-page/<name>/<email>/<company_name>')
def unassign_properties_page(name,email,company_name):
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            # Convert the base64 data back to bytes
            dp = base64.b64decode(company['dp'])
            # Convert bytes to string for HTML rendering
            dp_str = base64.b64encode(dp).decode()
        else:
            dp_str = None
        property_assigned = db.registered_managers.find({'email': email, 'company_name': company_name})
        property_assigned_dict = {property for doc in property_assigned if 'properties' in doc for property in doc['properties']}
        
        return render_template('unassign properties page.html', property_names=property_assigned_dict,name=name,email=email,company_name=company_name,dp=dp_str)
    
@app.route('/unassign-properties-initiated', methods=["POST"])
def unassign_properties_initiated():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        name = request.form.get('name')
        email = request.form.get('email')
        company_name = request.form.get('company_name')
        propertyName = request.form.get("propertyName")

        db.registered_managers.update_one(
            {'email': email, 'company_name': company_name}, 
            {'$pull': {'properties': propertyName}}
        )
        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Unassign property', 'email':email, 'timestamp': datetime.now()})
        flash(f"{propertyName} was unassigned from {name}")
        return redirect('/unassign-properties')

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
    username = session.get('login_username')
    if username is None:
        flash('Login first')
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
    username = session.get('login_username')
    if username is None:
        flash('Login first')
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
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})

        usernames = db.registered_managers.find({'company_name': company['company_name']}, {'username': 1})
        renamed_logs = []
        for user in usernames:
            audit_logs = db.audit_logs.find({
                'user': user['username'],
                'timestamp': {'$gte': startdate, '$lte': enddate}
            })
            for log in audit_logs:
                renamed_log = rename_fourth_field(log)
                timestamp = log.get('timestamp')
                log['timestamp'] = convert_to_eat(timestamp)
                renamed_logs.append(renamed_log)
        sorted_logs = sorted(renamed_logs, key=lambda x: x["timestamp"], reverse=True)
        df = pd.DataFrame(sorted_logs)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Audit logs', index=False)
        output.seek(0)

        # Create the response
        response = make_response(output.read())
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_audit logs_{startdate_on_str}_{enddate_on_str}.xlsx"
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        return response

###DOANLOAD LOGIN DATA   
@app.route('/download-login-data', methods=["POST"])
def download_login_data():
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})

        usernames = db.registered_managers.find({'company_name': company['company_name']}, {'username': 1})
        logindata = []
        for user in usernames:
            login_info = db.logged_in_data.find({'username': user['username'], 'timestamp': {'$gte': startdate, '$lte': enddate}})
            for login in login_info:
                formated_time = format_time(login)
                timestamp = login.get('timestamp')
                login['timestamp'] = convert_to_eat(timestamp)
                logindata.append(formated_time)
        sorted_logins = sorted(logindata, key=lambda x: x["timestamp"], reverse=True)
        df = pd.DataFrame(sorted_logins)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Audit logs', index=False)
        output.seek(0)

        # Create the response
        response = make_response(output.read())
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_audit logs_{startdate_on_str}_{enddate_on_str}.xlsx"
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        return response

#####ACTIVATE SENDING EMAILS
@app.route('/activate sending emails/<send_emails>')
def activate_send_emails(send_emails):
    send_emails_state = db.send_emails.find_one()
    if send_emails_state is None:
        db.send_emails.insert_one({'emails': send_emails})
        if send_emails == "yes":
            flash(f"Emails have been activated")
        else:
            flash(f"Emails have been deactivated")
    else:
        if send_emails == "yes":
            db.send_emails.update_one({'emails': "no"}, {'$set': {'emails': send_emails}})
            flash(f"Emails have been activated")
        else:
            db.send_emails.update_one({'emails': "yes"}, {'$set': {'emails': send_emails}})
            flash(f"Emails have been deactivated")
    session['send_emails'] = send_emails
    return render_template("managers accounts.html")

if __name__ == '__main__':
    scheduler.start()
    app.run(debug=True)
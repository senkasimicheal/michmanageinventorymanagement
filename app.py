from flask import Flask, render_template, url_for, send_from_directory, request, flash, redirect, session, make_response, send_file, jsonify
from flask_mail import Mail, Message
from docx import Document
from pymongo import MongoClient, ASCENDING, DESCENDING
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
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
import cv2
import numpy as np
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
from zipfile import ZipFile
import tempfile
import string
import qrcode
import threading
from docx2pdf import convert
import PyPDF2

app = Flask(__name__, static_folder='static')
app.secret_key = secrets.token_hex(16)

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

@app.route("/")
def index():
    return render_template('index.html')

@app.route('/download-apk')
def download_apk():
    return send_from_directory(directory='.', path='michmanage.apk', as_attachment=True)
    
###########SEND US A MESSAGE###############
@app.route('/send-message', methods=["POST"])
def send_message():
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"})
        
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
        <p><b style="font-size: 20px;"><a href="https://michmanager.onrender.com">Visit Our Platform</a></b></p>
        </body>
        </html>
        """
        thread = threading.Thread(target=send_async_email, args=[app, msg])
        thread.start()
    flash('Your inquiry was sent', 'success')
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

@app.route('/manager login page')
def manager_login_page():
    return render_template('manager login.html')

@app.route('/documentation')
def documentation():
    return render_template('documentation.html')

@app.route('/tenant login page')
def tenant_login_page():
    return render_template('tenant login.html')

@app.route('/manager register')
def manager_register_page():
    db, fs = get_db_and_fs()
    companies = db.managers.find({}, {"name": 1})
    company_names = [company['name'] for company in companies]
    
    cursor = list(db.property_managed.find())
    df = pd.DataFrame(cursor)
    if 'propertyName' in df.columns:
        property_data = df['propertyName'].tolist()
    else:
        property_data = []

    resp = make_response(render_template("manager register.html", property_data=property_data, company_names=company_names))
    return resp

@app.route('/tenant register')
def tenant_register_page():
    db, fs = get_db_and_fs()
    companies = db.managers.find({}, {"name": 1})
    company_names = [company['name'] for company in companies]
    
    cursor = list(db.property_managed.find())
    df = pd.DataFrame(cursor)
    if 'propertyName' in df.columns:
        property_data = df['propertyName'].tolist()
    else:
        property_data = []

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
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
    return render_template('add property page.html', dp=dp_str)

@app.route('/add tenants')
def add_tenants():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
        is_manager = db.managers.find_one({'manager_email': company['email']})        

        if is_manager is None:
            user_query  = {'username': login_data, 'company_name': company['company_name']}
        else:
            user_query  = {'company_name': company['company_name']}

        property_data_list = list(db.property_managed.find(user_query))
        tenant_data_cursor = db.tenants.find(user_query)
                
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

@app.route('/export tenant data')
def export_tenant_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
    return render_template('export tenant data.html', dp=dp_str)

@app.route('/add new stock page')
def add_new_stock_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
    return render_template('add new stock.html', dp=dp_str)

@app.route('/update existing stock')
def update_existing_stock():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    
    company = db.registered_managers.find_one({'username': login_data})
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

    return render_template('update existing stock.html', dp=dp_str, items_to_update=items_to_update)

@app.route('/update sales page')
def update_sales_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    
    company = db.registered_managers.find_one({'username': login_data})
    if not company:
        flash('Company not found', 'error')
        return redirect('/')
    
    dp_str = company.get('dp')
    available_itemNames = []
    available_items = db.inventories.find({'company_name': company['company_name']})
    for item in available_items:
        if item.get('available_quantity', 0) > 0:
            available_itemNames.append({
                'itemName': item['itemName'],
                'available_quantity': item['available_quantity'],
                'unitOfMeasurement': item['unitOfMeasurement']
            })

    return render_template('update sales page.html', dp=dp_str, available_itemNames=available_itemNames)

@app.route('/update production activity')
def update_production_activity():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
        
        available_itemNames = []
        available_items = db.inventories.find({'company_name': company['company_name']})
        for item in available_items:
            if item.get('available_quantity', 0) > 0:
                available_itemNames.append({
                    'itemName': item['itemName'],
                    'available_quantity': item['available_quantity'],
                    'unitOfMeasurement': item['unitOfMeasurement']
                })

    return render_template('update production.html', dp=dp_str, available_itemNames=available_itemNames)

@app.route('/update inhouse use page')
def update_inhouse_use_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None

        available_itemNames = []
        available_items = db.inventories.find({'company_name': company['company_name']})
        for item in available_items:
            if item.get('available_quantity', 0) > 0:
                available_itemNames.append({
                    'itemName': item['itemName'],
                    'available_quantity': item['available_quantity'],
                    'unitOfMeasurement': item['unitOfMeasurement']
                })

    return render_template('update inhouse use.html', dp=dp_str, available_itemNames=available_itemNames)

@app.route('/logout-admin')
def logout_admin():
    session.clear()
    return redirect('/admin', code=303)

@app.before_request
def before_request():
    if 'logged_in' not in session and request.endpoint not in ('send_message', 'tenant_register_account', 'register_account','load_verification_page', 'verifying_your_account', 'terms_of_service', 'privacy_policy', 'admin', 'adminlogin', 'add_property_manager', 'complaint_form', 'tenant_data', 'tenant_download', 'get_receipt',
                                                               'google_verification', 'contact', 'sitemap', 'about', 'tenant_login_page', 'tenant_login', 'tenant_register', 'register', 'login', 'userlogin', 'index', 'static', 'verify_username', 'send_verification_code', 'password_reset_verifying_user', 'add_property_manager_page',
                                                               'add_complaint', 'my_complaints', 'tenant_reply_complaint', 'resolve_complaints' , 'update_complaint', 'new_subscription', 'new_subscription_initiated', 'export', 'apply_for_advert', 'submit_advert_application', 'authentication','tenant_account_setup_page', 'resend_auth_code',
                                                               'tenant_account_setup_initiated', 'tenant_authentication', 'download_apk', 'manager_login_page', 'manager_register_page', 'tenant_register_page', 'tenant_login_page', 'add_properties', 'add_tenants', 'export_tenant_data', 'add_new_stock_page','documentation','manager_notifications',
                                                               'tenant_notifications', 'tenant_popup_notifications'):
        return redirect('/')
    
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
    send_emails = db.send_emails.find_one({'emails': "yes"})
        
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
        flash('Passwords do not match', 'error')
        return redirect('/manager register')

    # Check if user is a manager
    company = db.managers.find_one({'name': company_name})
    if email not in company.get('managers', []):
        flash('Not a manager in the registered companies', 'error')
        return redirect('/manager register')

    # Check if username or email already exists
    if db.registered_managers.find_one({'username': username}):
        flash('Username already taken', 'error')
        return redirect('/manager register')
    if db.registered_managers.find_one({'email': email, 'company_name': company_name}):
        flash('User already registered', 'error')
        return redirect('/manager register')

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
            'manage_contracts': 'no',
            'add_stock': 'no',
            'update_stock': 'no',
            'update_sales': 'no',
            'inhouse': 'no',
            'view_stock_info': 'no',
            'view_revenue': 'no',
            'view_sales': 'no'
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
        <p><b style="font-size: 20px;"><a href="https://michmanager.onrender.com/load-verification-page">Verify</a></b></p>
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
    send_emails = db.send_emails.find_one({'emails': "yes"})

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

    send_emails = db.send_emails.find_one({'emails': "yes"})

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
         
#######PROPERTY MANAGER LOGIN##############
@app.route("/userlogin", methods=["POST"])
def userlogin():
    db, fs = get_db_and_fs()
    session.clear()
    send_emails = db.send_emails.find_one({'emails': "yes"})
    if send_emails is not None:
        app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
        app.config['MAIL_PORT'] = 587
        app.config['MAIL_USERNAME'] = 'apikey'
        app.config['MAIL_PASSWORD'] = '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'
        app.config['MAIL_USE_TLS'] = True
        app.config['MAIL_USE_SSL'] = False
        mail.init_app(app)

    username = request.form.get('username')
    password = request.form.get('password')

    session.permanent = False
    
    manager = db.registered_managers.find_one({'username':username})
    if 'dark_mode' in manager:
        if manager['dark_mode'] == 'yes':
            session['dark_mode'] = 'yes'
        else:
            session['dark_mode'] = 'no'
    else:
        session['dark_mode'] = 'no'

    if manager is None:
        flash('Not a manager', 'error')
        return redirect('/manager login page')
    else:
        subscription = db.managers.find_one({'name': manager['company_name']})

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

            fields = ['add_properties', 'add_tenants', 'update_tenant', 'edit_tenant', 'manage_contracts', 'add_stock', 'update_stock','update_sales','inhouse','view_stock_info','view_revenue','view_sales']
            for field in fields:
                value = manager.get(field)
                if value is not None:
                    session[field] = value
            
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
            elif 'Enterprise Resource Planning' in account_type and 'Property Management' in account_type:
                # If both are present
                session['account_type'] = 'all_accounts'
                return redirect('/all-accounts-overview')
            
#RESEND CODE
@app.route("/resend auth code/<username>")
def resend_auth_code(username):
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"})

    code = generate_code()
    user_auth = {"username": username, "code": code}
    db.login_auth.delete_one({"username": username})

    no_send_emails_code = 0
    manager = db.registered_managers.find_one({'username':username})
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
        subscription = db.managers.find_one({'name': manager['company_name']})

        # Calculate remaining days
        remaining_days = (subscription['last_subscribed_on'] + timedelta(days=subscription['subscribed_days']) - datetime.now()).days

        last_logged_in_data = db.logged_in_data.find_one({'username': manager['username']}, sort=[('timestamp', -1)])

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
        session['user_id'] = str(manager["_id"])
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
        elif 'Enterprise Resource Planning' in account_type and 'Property Management' in account_type:
            # If both are present
            session['account_type'] = 'all_accounts'
            return redirect('/all-accounts-overview')
        
##ACCOUNT SETTING
@app.route('/account-setup-page')
def account_setup_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})

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
        auth = request.form.get("switchState")
        dark_mode = request.form.get("switchState1")
        name = request.form.get("name")
        phone_number = request.form.get("phone_number")
        address = request.form.get("address")
        dp = request.files['dp'] if 'dp' in request.files else None

        update_fields = {}

        if auth:
            update_fields['auth'] = auth
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
    send_emails = db.send_emails.find_one({'emails': "yes"})

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
                send_emails = db.send_emails.find_one({'emails': "yes"})

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
        
            # session['tenant_data'] = tenant_data
            return render_template('tenant monitor account.html',tenant_data=tenant_data, dp=dp_str, auth=auth)

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
        send_emails = db.send_emails.find_one({'emails': "yes"})
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
            <p><b style="font-size: 20px;"><a href="https://michmanager.onrender.com/manager%20login%20page">Login</a></b></p>
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
        send_emails = db.send_emails.find_one({'emails': "yes"})
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
            <p><b style="font-size: 20px;"><a href="https://michmanager.onrender.com/manager%20login%20page">Login</a></b></p>
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
        company = db.registered_managers.find_one({'username': login_data})
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
                        if reply['who'] != login_data:
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
                    complaint_copy['replies'] = [{'Reply': reply['Reply'], 'who': reply['who'], 'other': login_data, 'status': reply.get('status', ''), 'reply_date': reply['reply_date'].strftime('%Y-%m-%d %H:%M') if reply['reply_date'] != 'N/A' else 'N/A'} for reply in replies]
                complaints.append(complaint_copy)
        # Sort complaints by date, most recent first
        complaints = sorted(complaints, key=lambda c: c['complained_on'], reverse=True)
        # Remove duplicates
        complaints = list({v['_id']: v for v in complaints}.values())
        return render_template('resolve complaints.html',complaints=complaints,resolved_complaints=resolved_complaints, dp=dp_str)
            
############RESOLVE COMPLAINTS BY MANAGER###########
@app.route('/update-complaint', methods=['POST'])
def update_complaint():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        manager = db.registered_managers.find_one({'username': login_data})
        send_emails = db.send_emails.find_one({'emails': "yes"})
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
            <p><b style="font-size: 20px;"><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
            <p>Best Regards,</p>
            <p>Mich Manage</p>
            </body>
            </html>
            """
            thread = threading.Thread(target=send_async_email, args=[app, msg])
            thread.start()

        return redirect('/resolve-complaints')
        
##########RESOLVING COMPLAINTS AFTER SOLVING THEM#########
@app.route('/resolved-complaints/<complaint_id>', methods=["GET", "POST"])
def resolved_complaints(complaint_id):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        send_emails = db.send_emails.find_one({'emails': "yes"})
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
       
#############ADD PROPERTY####################
@app.route('/add-property', methods=["POST"])
def add_property():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
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

########LOAD TENANT INFO################
@app.route('/update-tenant-info')
def update_tenant_info():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    current_year = datetime.now().year
    if login_data is None:
        flash('Login first', 'error')
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
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    current_year = datetime.now().year
    if login_data is None:
        flash('Login first', 'error') 
        return redirect('/')
    else:
        
        send_emails = db.send_emails.find_one({'emails': "yes"})
        if send_emails is not None:
            app.config['MAIL_SERVER']='smtp.sendgrid.net'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USERNAME'] = 'apikey'
            app.config['MAIL_PASSWORD'] = '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'
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USE_SSL'] = False
            mail.init_app(app)

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
                                    <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                                    <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                                <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                                <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                                    <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                                    <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                                <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                                <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                            <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                            <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                            <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                            <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                            <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                            <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
    db, fs = get_db_and_fs()
    username = session.get('login_username')
    if username is None:
        flash('Login first', 'error')
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
                flash('We did not find property data', 'error')
                return redirect('/load-dashboard-page')
            
            property_data = get_property_data(properties)
            return render_template('property information.html', property_data=property_data, dp=dp_str)

#####UPDATE PROPERTY INFO#############
@app.route('/update-property/<propertyName>')
def selected_property(propertyName):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
    return render_template('update property information.html',propertyName=propertyName, dp=dp_str)

##POSTING NEW PROPERTY INFORMATION
@app.route('/update-property', methods=["POST"])
def update_property():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
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
        flash(f"{propertyName} was successfully updated", 'success')
        return redirect('/view-property-info')

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
        company = db.registered_managers.find_one({'username': login_data})
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
        manager_found = db.registered_managers.find_one({'username': login_data})
        company = db.managers.find_one({'name':manager_found['company_name']})
        managers = company['managers']
        for manager in managers:
            if email == manager:
                flash('This email already exists', 'error')
                return redirect('/add-new-manager-email')
        db.managers.update_one({'name': manager_found['company_name']}, {'$push': {'managers': email}})
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
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
    date_last_paid = datetime.strptime(date_last_paid, '%Y-%m-%d')
    return render_template('update tenant information.html',tenantName=tenantName,tenantEmail=tenantEmail,propertyName=propertyName,selected_section=selected_section,payment_type=payment_type,amount=amount,months_paid=months_paid,year=date_last_paid.year,dp=dp_str)
        
##########EDIT TENANT INFO###################
@app.route('/edit/<tenantName>/<email>/<property_name>/<selected_section>/<payment_type>')
def edit(tenantName, email, property_name, selected_section, payment_type):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        # Retrieve the tenant's info using the email
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
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
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        
        send_emails = db.send_emails.find_one({'emails': "yes"})
        if send_emails is not None:
            app.config['MAIL_SERVER']='smtp.sendgrid.net'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USERNAME'] = 'apikey'
            app.config['MAIL_PASSWORD'] = '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'
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USE_SSL'] = False
            mail.init_app(app)

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
                <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
        
        send_emails = db.send_emails.find_one({'emails': "yes"})
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
                    <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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
                    <p><b><a href="https://michmanager.onrender.com/tenant%20login%20page">Login</a></b></p>
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

########DELETE TENANT################
@app.route('/delete_tenant/<tenantEmail>/<propertyName>/<selected_section>')
def delete_tenant(tenantEmail, propertyName, selected_section):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
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
            send_emails = db.send_emails.find_one({'emails': "yes"})
            if send_emails is not None:
                session['send_emails'] = "yes"
            else:
                session['send_emails'] = "no"
            return render_template("managers accounts.html")
        else:
            flash('Wrong Password', 'error')
            return redirect('/admin')
        
@app.route('/add-property-manager-page')
def add_property_manager_page():
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else:
        return render_template("managers accounts.html")

##########ADD PROPERTY MANAGER COMPANY#############
@app.route('/add-property-manager', methods=["POST"])
def add_property_manager():
    db, fs = get_db_and_fs()
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else:   
        send_emails = db.send_emails.find_one({'emails': "yes"})
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
                <p><b style="font-size: 20px;"><a href="https://michmanager.onrender.com/manager%20register">Register Now</a></b></p>
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
        companies = db.managers.find()
        cursor = list(companies)
        if len(cursor) == 0:
            flash('We found no companies', 'error')
            return render_template("managers accounts.html")
        else:
            df = pd.DataFrame(cursor)
            company_names = df['name']
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
        send_emails = db.send_emails.find_one({'emails': "yes"})
        if send_emails is not None:
            app.config['MAIL_SERVER']='smtp.sendgrid.net'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USERNAME'] = 'apikey'
            app.config['MAIL_PASSWORD'] = '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'
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USE_SSL'] = False
            mail.init_app(app)

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
        
        subscription = db.managers.find_one({'name': company['company_name']})
        account_type = subscription['account_type']
        # Remove any empty strings from the list
        account_type = [atype for atype in account_type if atype]

        if 'dp' in company:
            dp_str = company['dp']
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
                    flash('No property data found', 'error')
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

                    flash('No tenant data found', 'error')
                    return render_template('dashboard.html',property_occupancy=property_occupancy, dp=dp_str)
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
            flash('No property data found', 'error')
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
                                    count_current_tenants=count_current_tenants, property_occupancy=property_occupancy,
                                    property_type_bar_chart=property_type_bar_chart,property_performance_bar_chart=property_performance_bar_chart,
                                    line_chart=line_chart, month_name=month_name,overdue_tenants=overdue_tenants, dp=dp_str)
            else:
                flash('No tenant data found', 'error')
                return render_template('dashboard.html', property_occupancy=property_occupancy, dp=dp_str)
        
#############MANAGER DOWNLOAD DATA######################
@app.route('/download', methods=["POST"])
def download():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})
        is_manager = db.managers.find_one({'manager_email': company['email']})
        if is_manager is None:
            user_query = {'username': login_data, 'company_name': company['company_name'], 'date_last_paid': {'$gte': startdate, '$lte': enddate}}
        else:
            user_query = {'company_name': company['company_name'], 'date_last_paid': {'$gte': startdate, '$lte': enddate}}
        projection = {'payment_receipt': 0, '_id': 0, 'marital_status': 0, 'age': 0, 'available_amount': 0, 'payment_completion': 0,
                      'currency': 0, 'payment_status': 0, 'status': 0, 'household_size': 0}
    
        current_tenant_data = list(db.tenants.find(user_query, projection))
        old_tenant_data = list(db.old_tenant_data.find(user_query, projection))
    
        if len(current_tenant_data) > 0 or len(old_tenant_data) > 0:
            df1 = pd.DataFrame(old_tenant_data)
            df2 = pd.DataFrame(current_tenant_data)
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

            month_order = {'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6, 'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12}
            df_combined_tenants['Month paid'] = pd.Categorical(df_combined_tenants['Month paid'], categories=month_order.keys(), ordered=True)
            df_combined_tenants.sort_values(by=['Year', 'Month paid'], inplace=True)

            # Create a BytesIO buffer to write the Excel file
            output = BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = "Tenants"

            for col_idx, col_name in enumerate(df_combined_tenants.columns, start=2):
                ws.cell(row=1, column=col_idx, value=col_name)

            for r_idx, row in enumerate(dataframe_to_rows(df_combined_tenants, index=False), start=2):
                for c_idx, value in enumerate(row, start=1):
                    ws.cell(row=r_idx, column=c_idx, value=value)

            file_password = generate_file_password()
            ws.protection.set_password(file_password)

            existing_password = db.file_passwords.find_one({'username': login_data, 'detail': 'Tenant data file'})
            if existing_password:
                db.file_passwords.delete_one({'username': login_data, 'detail': 'Tenant data file'})
            db.file_passwords.insert_one({'username': login_data, 'password': file_password, 'detail': 'Tenant data file'})

            protected_file_path = tempfile.NamedTemporaryFile(delete=False, suffix="_protected.xlsx").name
            wb.save(filename=protected_file_path)
            wb.close()

            wb = load_workbook(protected_file_path)
            ws = wb.active
            ws.delete_rows(1)
            wb.save(protected_file_path)
            wb.close()

            with open(protected_file_path, 'rb') as f:
                protected_data = f.read()

            os.remove(protected_file_path)

            # Create a zip file containing the password-protected Excel file
            zip_buffer = BytesIO()
            with ZipFile(zip_buffer, 'w') as zip_file:
                zip_file.writestr(f"{company['company_name']}_{startdate_on_str}_{enddate_on_str}.xlsx", protected_data)

            zip_buffer.seek(0)
            zip_data = zip_buffer.getvalue()

            response = make_response(zip_data)
            response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_{startdate_on_str}_{enddate_on_str}.zip"
            response.headers['Content-Type'] = 'application/zip'

            return response
        else:
            flash('No tenant data found', 'error')
            return redirect('/load-dashboard-page')
        
#####FILE PASSWORDS
@app.route('/view-file-passwords')
def view_file_passwords():
    db, fs = get_db_and_fs()
    username = session.get('login_username')
    if username is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
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

####MANAGE CONTRACTS
@app.route('/manage-contracts')
def manage_contracts():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
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
        
@app.route('/upload-contract-page')
def upload_contract_page():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
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

@app.route('/upload-contract', methods=['POST'])
def upload_contract():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
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
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add new contract', 'file_id': file_id, 'timestamp': datetime.now()})
            flash("Contract was uploaded successfully", 'success')
            return redirect('/upload-contract-page')

########DELETE CONTRACTS################
@app.route('/delete-contract/<contractID>')
def delete_contract(contractID):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
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
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
    return render_template('update contract.html',contractID=contractID,company_name=company_name,receiver=receiver,dp=dp_str)

@app.route('/updated-contract', methods=['POST'])
def updated_contract():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
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
        company = db.registered_managers.find_one({'username': login_data})
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
        company = db.registered_managers.find_one({'username': login_data})
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
        
        return render_template('user rights page.html', email=email,company_name=company_name,
                               add_properties=add_properties,add_tenants=add_tenants,
                               update_tenant=update_tenant,edit_tenant=edit_tenant,
                               manage_contracts=manage_contracts,add_stock=add_stock,
                               update_stock=update_stock,update_sales=update_sales,inhouse=inhouse,
                               view_stock_info=view_stock_info,view_revenue=view_revenue,dp=dp_str)

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
        company = db.registered_managers.find_one({'username': login_data})
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
    
@app.route('/assign-properties-page/<name>/<email>/<company_name>')
def assign_properties_page(name,email,company_name):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
        properties = db.property_managed.find({'company_name': company['company_name']}, {"propertyName": 1})
        property_names = [property['propertyName'] for property in properties]
        
        return render_template('assign properties page.html', property_names=property_names,name=name,email=email,company_name=company_name,dp=dp_str)
    
@app.route('/assign-properties-initiated', methods=["POST"])
def assign_properties_initiated():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
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
        flash(f"{propertyName} was assigned to {name}", 'success')
        return redirect('/assign-properties')

####UNASSIGN PROPERTIES FROM MANAGERS
@app.route('/unassign-properties')
def unassign_properties():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
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
    
@app.route('/unassign-properties-page/<name>/<email>/<company_name>')
def unassign_properties_page(name,email,company_name):
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        if 'dp' in company:
            dp_str = company['dp']
        else:
            dp_str = None
        property_assigned = db.registered_managers.find({'email': email, 'company_name': company_name})
        property_assigned_dict = {property for doc in property_assigned if 'properties' in doc for property in doc['properties']}
        
        return render_template('unassign properties page.html', property_names=property_assigned_dict,name=name,email=email,company_name=company_name,dp=dp_str)
    
@app.route('/unassign-properties-initiated', methods=["POST"])
def unassign_properties_initiated():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
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
        flash(f"{propertyName} was unassigned from {name}", 'success')
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

        # Create an in-memory buffer for the Excel file
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Audit logs', index=False)
        excel_buffer.seek(0)
        
        # Create a zip file containing the Excel file
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr(f"{company['company_name']}_audit_logs_{startdate_on_str}_{enddate_on_str}.xlsx", excel_buffer.read())
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        # Create the response
        response = make_response(zip_data)
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_audit_logs_{startdate_on_str}_{enddate_on_str}.zip"
        response.headers['Content-Type'] = 'application/zip'

        return response

###DOANLOAD LOGIN DATA   
@app.route('/download-login-data', methods=["POST"])
def download_login_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
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

        # Create an in-memory buffer for the Excel file
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Login Data', index=False)
        excel_buffer.seek(0)
        
        # Create a zip file containing the Excel file
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr(f"{company['company_name']}_login_data_{startdate_on_str}_{enddate_on_str}.xlsx", excel_buffer.read())
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        # Create the response
        response = make_response(zip_data)
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_login_data_{startdate_on_str}_{enddate_on_str}.zip"
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
        return jsonify({'redirect': url_for('/')})
    
    company = db.registered_managers.find_one({'username': login_data})
    all_items = request.json['items']  # Access the JSON data sent from the client
    skipped_items = []  # List to hold names of items that were not added
    added_items = []  # List to hold names of items that were successfully added

    for item in all_items:
        item['itemName'] = item['itemName'].strip()
        # Convert 'quantity' and 'unitPrice' to integers
        item['quantity'] = int(item['quantity'])
        item['available_quantity'] = item['quantity']
        item['unitPrice'] = int(item['unitPrice'])
        item['stockDate'] = datetime.strptime(item['stockDate'], '%Y-%m-%d')

        # Add 'totalPrice' field which is 'unitPrice' * 'quantity'
        item['totalPrice'] = item['unitPrice'] * item['quantity']
        item['company_name'] = company['company_name']

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

    message = ""
    if added_items:
        message += '. The following items were added: ' + ', '.join(added_items)
        flash(message, 'success')
    if skipped_items:
        message_skipped = 'The following items were not added because they already exist: ' + ', '.join(skipped_items)
        flash(message_skipped, 'error')

    return jsonify({'redirect': url_for('add_new_stock_page')})
    
@app.route('/update-new-stock', methods=['POST'])
def update_new_stock():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return jsonify({'redirect': url_for('/')})
    
    company = db.registered_managers.find_one({'username': login_data})
    all_items = request.json['items']  # Access the JSON data sent from the client

    for item in all_items:
        # Convert 'quantity' and 'unitPrice' to integers
        item['quantity'] = int(item['quantity'])
        item['unitPrice'] = int(item['unitPrice'])
        item['stockDate'] = datetime.strptime(item['stockDate'], '%Y-%m-%d')
        item['company_name'] = company['company_name']
        item['status'] = "updated stock"

        # Check if the item already exists in the database
        existing_item = db.inventories.find_one({
            'itemName': item['itemName'],
            'company_name': company['company_name']
        })

        if existing_item:
            if 'available_quantity' in existing_item:
                if existing_item['available_quantity'] > 0:
                    # Add 'totalPrice' field which is 'unitPrice' * 'quantity'
                    item['totalPrice'] = item['quantity']*item['unitPrice']
                    item['unitOfMeasurement'] = existing_item['unitOfMeasurement']
                    item['oldTotalPrice'] = existing_item['totalPrice']
                    item['oldUnitPrice'] = existing_item['unitPrice']
                    new_available_quantity = existing_item['available_quantity'] + item['quantity']
                    item['available_quantity'] = new_available_quantity
                else:
                    new_available_quantity = existing_item['available_quantity'] + item['quantity']
                    item['available_quantity'] = new_available_quantity
                    item['totalPrice'] = item['quantity']*item['unitPrice']
            else:
                new_available_quantity = item['quantity']
                item['available_quantity'] = new_available_quantity
                item['totalPrice'] = item['quantity']*item['unitPrice']

            # Insert the new stock entry into MongoDB
            db.inventories.insert_one(item)
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Updated item in stock', 'Item': 'Items', 'timestamp': datetime.now()})
            db.inventories.delete_one({'_id': existing_item['_id']})
            existing_item.pop('_id', None)
            db.old_inventories.insert_one(existing_item)
    
    flash('Stock updated successfully', 'success')
    
    return jsonify({'redirect': url_for('update_existing_stock')})
    
@app.route('/update-sale', methods=['POST'])
def update_sale():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return jsonify({'redirect': url_for('/')})
    
    company = db.registered_managers.find_one({'username': login_data})
    all_items = request.json['items']  # Access the JSON data sent from the client
    out_of_stock_items = []
    over_quantified = []
    
    for item in all_items:
        item['quantity'] = int(item['quantity'])
        item['unitPrice'] = int(item['unitPrice'])
        item['saleDate'] = datetime.strptime(item['saleDate'], '%Y-%m-%d')
        item['company_name'] = company['company_name']

        existing_item = db.inventories.find_one({
            'itemName': item['itemName'],
            'company_name': company['company_name']
        })

        if existing_item:
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

            db.stock_sales.insert_one(item)
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Added a new sale', 'Item': 'Items', 'timestamp': datetime.now()})
            db.inventories.update_one({'_id': existing_item['_id']}, {'$set': {'available_quantity': available_quantity}})
    
    message = 'Sales updated successfully'
    flash(message, 'success')

    if out_of_stock_items:
        flash(f'The following items are out of stock: {", ".join(out_of_stock_items)}', 'error')
    if over_quantified:
        flash(f'Enter smaller quantities for the following items: {", ".join(over_quantified)}', 'error')

    return jsonify({'redirect': url_for('update_sales_page')})
    
@app.route('/in-house-use', methods=['POST'])
def inhouse():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Login first', 'error')
        return jsonify({'redirect': url_for('/')})
    
    company = db.registered_managers.find_one({'username': login_data})
    all_items = request.json['items']  # Access the JSON data sent from the client

    # Initialize empty arrays for itemNames and itemQuantities
    itemNames = []
    itemQuantities = []
    itemStockDates = []
    itemUnitPrices = []
    itemOldUnitPrices = []
    
    # Extract productName, productQuantity, productPrice, useDate from the first itemObject
    productName = all_items[0]['productName']
    productQuantity = int(all_items[0]['productQuantity'])
    productPrice = int(all_items[0]['productPrice'])
    useDate = all_items[0]['useDate']
    useDate = datetime.strptime(useDate, '%Y-%m-%d')
    company_name = company['company_name']

    out_of_stock_items = []
    over_quantified = []
    in_stockID = []
    in_stockQty = []

    for item in all_items:
        itemNames.append(item['itemName'])
        item['itemQuantity'] = int(item['itemQuantity'])
        itemQuantities.append(item['itemQuantity'])

        # Check if the item already exists in the database
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
                else:
                    if item['itemQuantity'] > existing_item['available_quantity']:
                        over_quantified.append(item['itemName'])
                        flash(f'Quantity for item {item["itemName"]} is too high', 'error')
                        continue
                    else:
                        available_quantity = existing_item['available_quantity'] - item['itemQuantity']
                        itemStockDates.append(existing_item['stockDate'])
                        in_stockID.append(existing_item['_id'])
                        in_stockQty.append(available_quantity)
                        itemUnitPrices.append(existing_item['unitPrice'])
                        if 'oldUnitPrice' in existing_item:
                            itemOldUnitPrices.append(existing_item['oldUnitPrice'])
                        else:
                            itemOldUnitPrices.append(0)
                        flash(f'Inhouse use of {item["itemName"]} updated successfully', 'success')
            else:
                if item['itemQuantity'] > existing_item['quantity']:
                    over_quantified.append(item['itemName'])
                    flash(f'Quantity for item {item["itemName"]} is too high', 'error')
                else:
                    available_quantity = existing_item['quantity'] - item['itemQuantity']
                    itemStockDates.append(existing_item['stockDate'])
                    in_stockID.append(existing_item['_id'])
                    in_stockQty.append(available_quantity)
                    itemUnitPrices.append(existing_item['unitPrice'])
                    if 'oldUnitPrice' in existing_item:
                        itemOldUnitPrices.append(existing_item['oldUnitPrice'])
                    else:
                        itemOldUnitPrices.append(0)
                    flash(f'Inhouse use of {item["itemName"]} updated successfully', 'success')

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
        db.audit_logs.insert_one({'user': login_data, 'Activity': 'Inhouse production', 'Item': 'Items', 'timestamp': datetime.now()})

    return jsonify({'redirect': url_for('update_production_activity')})

@app.route('/in-house-used-items', methods=['POST'])
def inhouse_used_items():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    
    if login_data is None:
        flash('Please login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        all_items = request.json['items']  # Access the JSON data sent from the client

        # Initialize empty arrays for itemNames, itemQuantities, etc.
        itemNames = []
        itemQuantities = []
        itemStockDates = []
        itemUseDates = []
        itemUnitPrices = []
        itemOldUnitPrices = []
        
        company_name = company['company_name']

        out_of_stock_items = []
        over_quantified = []
        in_stockID = []
        in_stockQty = []

        for item in all_items:
            itemNames.append(item['usedItemName'])
            item['usedItemQuantity'] = int(item['usedItemQuantity'])
            itemQuantities.append(item['usedItemQuantity'])
            use_date = datetime.strptime(item['usedUseDate'], '%Y-%m-%d')
            itemUseDates.append(use_date)

            existing_item = db.inventories.find_one({
                'itemName': item['usedItemName'],
                'company_name': company_name
            })

            if existing_item:
                if 'available_quantity' in existing_item:
                    if existing_item['available_quantity'] <= 0:
                        out_of_stock_items.append(item['usedItemName'])
                        flash(f'Item {item["usedItemName"]} is out of stock', 'error')
                        continue
                    else:
                        if item['usedItemQuantity'] > existing_item['available_quantity']:
                            over_quantified.append(item['usedItemName'])
                            flash(f'Quantity for item {item["usedItemName"]} is too high', 'error')
                            continue
                        else:
                            available_quantity = existing_item['available_quantity'] - item['usedItemQuantity']
                            itemStockDates.append(existing_item['stockDate'])
                            in_stockID.append(existing_item['_id'])
                            in_stockQty.append(available_quantity)
                            itemUnitPrices.append(existing_item['unitPrice'])
                            if 'oldUnitPrice' in existing_item:
                                itemOldUnitPrices.append(existing_item['oldUnitPrice'])
                            else:
                                itemOldUnitPrices.append(0)
                            flash(f'Inhouse use of {item["usedItemName"]} updated successfully', 'success')

                else:
                    if item['usedItemQuantity'] > existing_item['quantity']:
                        over_quantified.append(item['usedItemName'])
                        flash(f'Quantity for item {item["usedItemName"]} is too high', 'error')
                    else:
                        available_quantity = existing_item['quantity'] - item['usedItemQuantity']
                        itemStockDates.append(existing_item['stockDate'])
                        in_stockID.append(existing_item['_id'])
                        in_stockQty.append(available_quantity)
                        itemUnitPrices.append(existing_item['unitPrice'])
                        if 'oldUnitPrice' in existing_item:
                            itemOldUnitPrices.append(existing_item['oldUnitPrice'])
                        else:
                            itemOldUnitPrices.append(0)
                        flash(f'Inhouse use of {item["usedItemName"]} updated successfully', 'success')

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
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Inhouse use of items', 'Item': 'Items', 'timestamp': datetime.now()})

    return jsonify({'redirect': url_for('update_inhouse_use_page')})
    
@app.route('/revenue-details')
def revenue_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        
        subscription = db.managers.find_one({'name': company['company_name']})
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
                }
            ]

            revenue_info = list(db.stock_sales.aggregate(pipeline))
            revenue_info.sort(key=lambda x: x['inventoryDetails'][0]['stockDate'], reverse=True)

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
            return render_template('revenue info.html', revenue_info = revenue_info, dp=dp_str)

@app.route('/sales-details')
def sales_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        
        subscription = db.managers.find_one({'name': company['company_name']})
        account_type = subscription['account_type']
        # Remove any empty strings from the list
        account_type = [atype for atype in account_type if atype]

        if 'Enterprise Resource Planning' in account_type:
            company_name = company['company_name']

            twelve_months_ago = datetime.now() - timedelta(days=365)

            sales_info = list(db.stock_sales.find({'company_name': company_name, 'saleDate': {'$gte': twelve_months_ago}}))
            sales_info.sort(key=lambda x: x['saleDate'], reverse=True)

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
            return render_template('sales info.html', sales_info = sales_info, dp=dp_str)

@app.route('/stock-details')
def stock_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        
        subscription = db.managers.find_one({'name': company['company_name']})
        account_type = subscription['account_type']
        # Remove any empty strings from the list
        account_type = [atype for atype in account_type if atype]

        if 'Enterprise Resource Planning' in account_type:
            company_name = company['company_name']
            twelve_months_ago = datetime.now() - timedelta(days=365)
            current_stock = list(db.inventories.find({'company_name': company_name, 'stockDate': {'$gte': twelve_months_ago}}))
            old_stock = list(db.old_inventories.find({'company_name': company_name, 'stockDate': {'$gte': twelve_months_ago}}))
            stock_info = current_stock + old_stock
            stock_info.sort(key=lambda x: x['stockDate'], reverse=True)

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
            return render_template('stock info.html', stock_info = stock_info, dp=dp_str)

@app.route('/inhouse-item-use-details')
def inhouse_items_use_details():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        
        subscription = db.managers.find_one({'name': company['company_name']})
        account_type = subscription['account_type']
        # Remove any empty strings from the list
        account_type = [atype for atype in account_type if atype]

        if 'Enterprise Resource Planning' in account_type:
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

@app.route('/stock-overview', methods=["GET", "POST"])
def stock_overview():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        # Clear sessions
        session.pop("profits_chart", None)
        session.pop("loss_chart", None)
        session.pop("revenue_and_qty_chart", None)
        session.pop("monthly_profits_chart", None)
        session.pop("inhouse_costs_chart", None)
        session.pop("inhouse_revenue_chart", None)

        company = db.registered_managers.find_one({'username': login_data})

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
        fig_profits = px.bar(positive_profits_df, x='Item Name', y='Profit', title='Profits on Each Item')
        fig_profits.update_traces(texttemplate='%{y}', textposition='inside')
        fig_profits.update_layout(showlegend=False)
        profits_chart = json.dumps(fig_profits, cls=plotly.utils.PlotlyJSONEncoder)

        # Filter negative profits
        negative_profits_df = df[df['Profit'] < 0]
        if not negative_profits_df.empty:
            session['loss_chart'] = 'loss_chart'
        negative_profits_df['Profit'] = -1*negative_profits_df['Profit']

        # Create the bar chart for losses
        fig_negative_profits = px.bar(negative_profits_df, x='Item Name', y='Profit', title='Losses on Each Item')
        fig_negative_profits.update_traces(texttemplate='%{y}', textposition='inside')
        fig_negative_profits.update_layout(showlegend=False)
        Losses_chart = json.dumps(fig_negative_profits, cls=plotly.utils.PlotlyJSONEncoder)

        ##total revenue
        if not df.empty:
            session['revenue_and_qty_chart'] = 'revenue_and_qty_chart'
        fig_total_revenue = px.bar(df, x='Item Name', y='Total Revenue', title='Revenue on Each Item')
        fig_total_revenue.update_traces(texttemplate='%{y}', textposition='inside')
        fig_total_revenue.update_layout(showlegend=False)
        revenue = json.dumps(fig_total_revenue, cls=plotly.utils.PlotlyJSONEncoder)

        ##Quantity sold
        fig_quantity_sold = px.bar(df, x='Item Name', y=['Quantity Sold', 'Quantity Stocked'],
                           title='Qty Sold vs. Qty Stocked',
                           labels={'value': 'Quantity'})
        fig_quantity_sold.update_traces(texttemplate='%{y}', textposition='inside')
        fig_quantity_sold.update_layout(legend=dict(orientation="h", yanchor="top", y=1.1))
        quantity_sold_stocked = json.dumps(fig_quantity_sold, cls=plotly.utils.PlotlyJSONEncoder)

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
        trended_profit_fig = px.line(monthly_profits_df, x='Month', y='Monthly Profit',
              title='Sum of Profits by Month')

        # Customize the appearance if needed (e.g., colors, layout)
        trended_profit_fig.update_traces(mode='lines+markers')
        trended_profit = json.dumps(trended_profit_fig, cls=plotly.utils.PlotlyJSONEncoder)

        ###INHOUSE UPDATES
        inhouse_info = list(db.inhouse.find({'company_name': company['company_name'], 'useDate': {
                        '$gte': start_of_previous_month,
                        '$lt': first_day_of_current_month}}))
        
        inhouse_itemName = []
        inhouse_itemQuantity = []
        inhouse_itemUnitPrices = []

        for record in inhouse_info:
            item_name = record['itemName']
            item_quantity = record['itemQuantity']
            item_unit_price = record['itemUnitPrices']
            
            inhouse_itemName.append(item_name)
            inhouse_itemQuantity.append(item_quantity)
            inhouse_itemUnitPrices.append(item_unit_price)

        # Create the DataFrame
        inhouse_df = pd.DataFrame({
            'Item Name': inhouse_itemName,
            'quantity': inhouse_itemQuantity,
            'unit price': inhouse_itemUnitPrices
        })

        # Assuming you have the DataFrame 'inhouse_df_new'
        # Explode all variables (Item Name, quantity, unit price)
        inhouse_df_exploded = inhouse_df.explode('Item Name')
        inhouse_df_exploded['quantity'] = inhouse_df.explode('quantity')['quantity']
        inhouse_df_exploded['unit price'] = inhouse_df.explode('unit price')['unit price']
        inhouse_df_exploded.reset_index(drop=True, inplace=True)  # Reset the index

        inhouse_df_exploded['cost'] = inhouse_df_exploded['quantity']*inhouse_df_exploded['unit price']

        total_cost_by_item = inhouse_df_exploded.groupby('Item Name')['cost'].sum()
        inhouse_cost_df = pd.DataFrame(total_cost_by_item).reset_index()

        ##total inhouse cost
        if not inhouse_cost_df.empty:
            session['inhouse_costs_chart'] = 'inhouse_costs_chart'
        inhouse_cost_fig = px.bar(inhouse_cost_df, x='Item Name', y='cost', title='Inhouse Costs')
        inhouse_cost_fig.update_traces(texttemplate='%{y}', textposition='inside')
        inhouse_cost_fig.update_layout(showlegend=False)
        inhouse_cost_chart = json.dumps(inhouse_cost_fig, cls=plotly.utils.PlotlyJSONEncoder)

        ##inhouse revenues
        inhouse_productName = []
        inhouse_productQuantity = []
        inhouse_productPrice = []

        for record in inhouse_info:
            productName = record['productName']
            productQuantity = record['productQuantity']
            productPrice = record['productPrice']
            
            inhouse_productName.append(productName)
            inhouse_productQuantity.append(productQuantity)
            inhouse_productPrice.append(productPrice)


        # Create the DataFrame
        inhouse_revenue_df = pd.DataFrame({
            'Product Name': inhouse_productName,
            'Quantity': inhouse_productQuantity,
            'Unit Price': inhouse_productPrice
        })

        inhouse_revenue_df['Revenue'] = inhouse_revenue_df['Quantity']*inhouse_revenue_df['Unit Price']

        # Group by 'Product Name' and sum 'Revenue'
        product_revenue_summary = inhouse_revenue_df.groupby('Product Name', as_index=False)['Revenue'].sum()
        
        ##total inhouse revenue
        if not product_revenue_summary.empty:
            session['inhouse_revenue_chart'] = 'inhouse_revenue_chart'
        inhouse_revenue_fig = px.bar(product_revenue_summary, x='Product Name', y='Revenue', title='Inhouse Revenue')
        inhouse_revenue_fig.update_traces(texttemplate='%{y}', textposition='inside')
        inhouse_revenue_fig.update_layout(showlegend=False)
        inhouse_revenue_chart = json.dumps(inhouse_revenue_fig, cls=plotly.utils.PlotlyJSONEncoder)

        dp = company.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        return render_template('stock dashboard.html',profits_chart=profits_chart,Losses_chart=Losses_chart,revenue=revenue,
                               quantity_sold_stocked=quantity_sold_stocked,trended_profit=trended_profit,inhouse_cost_chart=inhouse_cost_chart,
                               inhouse_revenue_chart=inhouse_revenue_chart,start_of_previous_month=start_of_previous_month,
                               first_day_of_current_month=first_day_of_current_month, dp=dp_str)
    
@app.route('/all-accounts-overview')
def all_accounts_overview():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data})
        dp = company.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        return render_template('all count type overview.html', dp=dp_str)

###DOANLOAD STOCK DATA   
@app.route('/download-stock-data', methods=["POST"])
def download_stock_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})

        current_stock = db.inventories.find(
            {'company_name': company['company_name'], 'stockDate': {'$gte': startdate, '$lte': enddate}},
            {'_id': 0, 'company_name': 0, 'available_quantity': 0}
        )
        old_stock = db.old_inventories.find(
            {'company_name': company['company_name'], 'stockDate': {'$gte': startdate, '$lte': enddate}},
            {'_id': 0, 'company_name': 0, 'available_quantity': 0}
        )
        combined_stock = list(current_stock) + list(old_stock)

        sorted_combined_stock = sorted(combined_stock, key=lambda x: x["stockDate"], reverse=True)
        df = pd.DataFrame(sorted_combined_stock)

        new_column_names = {
            'itemName': 'Item Name',
            'quantity': 'Stocked Quantity',
            'unitOfMeasurement': 'Unit Of Measurement',
            'unitPrice': 'Unit Buying Price',
            'stockDate': 'Stock Date',
            'totalPrice': 'Total Buying Price'
        }
        df.rename(columns=new_column_names, inplace=True)

        # Create an in-memory buffer for the Excel file
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Stock Data', index=False)
        excel_buffer.seek(0)

        # Create a zip file containing the Excel file
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr(f"{company['company_name']}_Stock_Data_{startdate_on_str}_{enddate_on_str}.xlsx", excel_buffer.read())
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        # Create the response
        response = make_response(zip_data)
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Stock_Data_{startdate_on_str}_{enddate_on_str}.zip"
        response.headers['Content-Type'] = 'application/zip'

        return response
    
###DOANLOAD REVENUE DATA   
@app.route('/download-revenue-data', methods=["POST"])
def download_revenue_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})

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

        # Create a zip file containing the Excel file
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr(f"{company['company_name']}_Revenue_Data_{startdate_on_str}_{enddate_on_str}.xlsx", excel_buffer.read())
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        # Create the response
        response = make_response(zip_data)
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Revenue_Data_{startdate_on_str}_{enddate_on_str}.zip"
        response.headers['Content-Type'] = 'application/zip'

        return response
    
###DOANLOAD SALES DATA   
@app.route('/download-sales-data', methods=["POST"])
def download_sales_data():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})

        company_name = company['company_name']

        sales_info = list(db.stock_sales.find({
            'company_name': company_name,
            'saleDate': {'$gte': startdate, '$lte': enddate}
        }, {
            '_id': 0,
            'company_name': 0,
            'stockDate': 0
        }))

        sorted_sales_info = sorted(sales_info, key=lambda x: x["saleDate"], reverse=True)
        df = pd.DataFrame(sorted_sales_info)
        new_column_names = {
            'itemName': 'Item Name',
            'quantity': 'Sold Quantity',
            'unitPrice': 'Unit Selling Price',
            'revenue': 'Revenue',
            'saleDate': 'Sale Date',
        }

        df.rename(columns=new_column_names, inplace=True)

        # Create an in-memory buffer for the Excel file
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Sales Data', index=False)
        excel_buffer.seek(0)

        # Create a zip file containing the Excel file
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            zip_file.writestr(f"{company['company_name']}_Sales_Data_{startdate_on_str}_{enddate_on_str}.xlsx", excel_buffer.read())
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        # Create the response
        response = make_response(zip_data)
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Sales_Data_{startdate_on_str}_{enddate_on_str}.zip"
        response.headers['Content-Type'] = 'application/zip'

        return response

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
        twelve_months_ago = datetime.now() - timedelta(days=365)
        company = db.registered_managers.find_one({'username': login_data})

        company_name = company['company_name']

        inhouse_info = list(db.inhouse.find({'company_name': company_name,'useDate': {'$gte': twelve_months_ago}},{'company_name':0}))

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
            'Product ID':inhouse_product_ids,
            'Product Name':inhouse_productName,
            'Product Quantity':inhouse_productQuantity,
            'Product Unit Price':inhouse_productPrice,
            'Date Produced':inhouse_useDate,
            'Item Used': inhouse_itemName,
            'Item Quantity': inhouse_itemQuantity,
            'Item Unit Price': inhouse_itemUnitPrices,
            'Item Stock Date': inhouse_itemStockDates
        })

        # Apply the function to each row to calculate 'Total Production Cost'
        inhouse_df['Total Production Cost'] = inhouse_df.apply(calculate_total_cost, axis=1)
        inhouse_df_sorted = inhouse_df.sort_values(by='Date Produced')

        dp = company.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        return render_template('production info.html', inhouse_df = inhouse_df_sorted, dp=dp_str)
       
###DOANLOAD SALES DATA   
@app.route('/download-inhouse-data', methods=["POST"])
def download_inhouse():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})

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

        # Create the response
        response = make_response(zip_data)
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Inhouse_Data_{startdate_on_str}_{enddate_on_str}.zip"
        response.headers['Content-Type'] = 'application/zip'

        return response
    
@app.route('/download-inhouse-item-data', methods=["POST"])
def download_inhouse_item_use():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        startdate_on_str = request.form.get("startdate")
        enddate_on_str = request.form.get("enddate")
        startdate = datetime.strptime(startdate_on_str, '%Y-%m-%d')
        enddate = datetime.strptime(enddate_on_str, '%Y-%m-%d')
        company = db.registered_managers.find_one({'username': login_data})

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

        # Create the response
        response = make_response(zip_data)
        response.headers['Content-Disposition'] = f"attachment; filename={company['company_name']}_Inhouse_Item_Use_Data_{startdate_on_str}_{enddate_on_str}.zip"
        response.headers['Content-Type'] = 'application/zip'

        return response

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

        company = db.registered_managers.find_one({'username': login_data})
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

    # Get the last seen timestamp from the session
    last_seen_timestamp = session.get('last_seen_timestamp', datetime.min)

    # Get the list of viewed notification IDs from the session
    viewed_notifications = session.get('viewed_notifications', [])

    # Fetch notifications with a timestamp greater than the last seen timestamp
    notifications_cursor = db.userNotifications.find({
        'user': login_data,
        'timestamp': {'$gt': last_seen_timestamp},
        '_id': {'$nin': viewed_notifications}  # Exclude already viewed notifications
    }, {'_id': 1, 'notification': 1, 'timestamp': 1})

    # Convert cursor to list and convert ObjectId to string
    notifications_to_send = [
        {
            'notification': notification['notification'],
            'timestamp': notification['timestamp'].isoformat()
        }
        for notification in notifications_cursor
    ]
    
    if notifications_to_send:
        # Update the last seen timestamp to the maximum timestamp of the fetched notifications
        new_last_seen_timestamp = max(notification['timestamp'] for notification in notifications_to_send)
        session['last_seen_timestamp'] = new_last_seen_timestamp

        # Update the list of viewed notifications
        new_viewed_notifications = [str(notification['_id']) for notification in notifications_cursor]
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
        '_id': {'$nin': viewed_notifications}  # Exclude already viewed notifications
    }, {'_id': 1, 'notification': 1, 'timestamp': 1})

    # Convert cursor to list and convert ObjectId to string
    notifications_to_send = [
        {
            'notification': notification['notification'],
            'timestamp': notification['timestamp'].isoformat()
        }
        for notification in notifications_cursor
    ]
    
    if notifications_to_send:
        # Update the last seen timestamp to the maximum timestamp of the fetched notifications
        new_last_seen_timestamp = max(notification['timestamp'] for notification in notifications_to_send)
        session['last_seen_timestamp'] = new_last_seen_timestamp

        # Update the list of viewed notifications
        new_viewed_notifications = [str(notification['_id']) for notification in notifications_cursor]
        session['viewed_notifications'] = viewed_notifications + new_viewed_notifications
    
    # Prepare the response with only new notifications
    notifications_list = [notification['notification'] for notification in notifications_to_send]

    return jsonify(notifications_list)

if __name__ == '__main__':
    app.run()
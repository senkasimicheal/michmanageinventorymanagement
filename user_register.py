from flask import Blueprint, render_template, url_for, request, session, flash, redirect, make_response, jsonify, current_app
from utils import get_mongo_client, get_db_and_fs, send_async_email
from flask_mail import Message
import threading
import bcrypt
from datetime import datetime, timedelta, timezone

registration = Blueprint('registration_route', __name__)

@registration.route('/manager_register')
def manager_register_page():
    company_name = request.args.get('company_name')
    return render_template("manager register.html", company_name=company_name)

@registration.route('/tenant_register')
def tenant_register_page():
    db, fs = get_db_and_fs()
    companies = db.managers.find({}, {"name": 1})
    company_names = [company['name'] for company in companies]
    
    cursor = db.property_managed.find({}, {'propertyName': 1, '_id': 0})
    property_data = [item['propertyName'] for item in cursor if 'propertyName' in item]
    
    resp = make_response(render_template("tenant register.html", property_data=property_data, company_names=company_names))
    return resp

#######TENANT REGISTER ACCOUNT###############          
@registration.route('/tenant-register-account', methods=["POST"])
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

###########REGISTRING AN ACCOUNT###############
@registration.route('/register-account', methods=["POST"])
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
        return render_template("manager register.html", company_name=company_name)

    # Check if user is a manager
    company = db.managers.find_one({'name': company_name})
    if company and email not in company.get('managers', []):  # Check if the user is a manager
        flash('Not a manager in the registered companies', 'error')
        return render_template("manager register.html", company_name=company_name)

    # Check if username or email already exists
    if db.registered_managers.find_one({'username': username}):
        flash('Username already taken', 'error')
        return render_template("manager register.html", company_name=company_name)
    if db.registered_managers.find_one({'email': email, 'company_name': company_name}):
        flash('User already registered', 'error')
        return render_template("manager register.html", company_name=company_name)

    # Generate verification code
    code = generate_code()
    is_manager = db.managers.find_one({'manager_email': email,'name':company_name})
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    if is_manager:
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
            'system_selling_price': 'no',
            'point_of_sale': 'no',
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
                    sender='michmanage@outlook.com', 
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

        thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
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
@registration.route('/auto-registration-verification')
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
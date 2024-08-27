from flask import Blueprint, render_template, url_for, request, session, flash, redirect, make_response, jsonify, current_app
from pymongo import ASCENDING
from datetime import datetime, timedelta
import bcrypt
from utils import get_mongo_client, get_db_and_fs, send_async_email
from flask_mail import Message
import threading
import random

login = Blueprint('login_route', __name__)

def generate_code(length=6):
    return ''.join(random.choice('0123456789') for _ in range(length))

@login.route('/manager login page')
def manager_login_page():
    return render_template('manager login.html')

@login.route('/tenant login page')
def tenant_login_page():
    return render_template('tenant login.html')

@login.route("/userlogin", methods=["POST"])
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
                              sender='michmanage@outlook.com', 
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
                thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
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
                      'update_sales','inhouse','view_stock_info','view_revenue','view_sales','system_selling_price','point_of_sale',
                      'view_finance_dashboard','add_new_finance_account','update_finance_account','view_finance','edit_finance',
                      'delete_finance']
            
            is_manager = db.managers.find_one({'manager_email': manager['email'], 'name':manager['company_name']})
            if is_manager:
                for field in fields:
                    value = manager.get(field)
                    if value is not None:
                        session[field] = value
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
                for field in fields:
                    if field in manager:
                        value = manager.get(field)
                        if value is not None:
                            session[field] = value
                    else:
                        session[field] = "no"
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

@login.route('/verify-username')
def verify_username():
    return render_template('forgot_password_verify_username.html')

#RESEND CODE
@login.route("/resend auth code/<username>")
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
        sender='michmanage@outlook.com', 
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
        thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
        thread.start()
    else:
        session['no_send_emails_code'] = 'no_send_emails_code'
        no_send_emails_code = code

    db.login_auth.create_index([("createdAt", ASCENDING)], expireAfterSeconds=300)
    db.login_auth.insert_one(user_auth)
    return render_template("authentication.html", no_send_emails_code=no_send_emails_code, username=username)

#USER AUTHENTICATION
@login.route("/authentication", methods=["POST"])
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

        is_manager = db.managers.find_one({'manager_email': manager['email'], 'name':manager['company_name']})
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

@login.route('/load-verification-page')
def load_verification_page():
    return render_template('verify_manager.html')

@login.route('/verifying-your-account', methods=["POST"])
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


def send_verification_email(manager_email, manager_name, code):
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

    if send_emails is not None:
        msg = Message('Password Reset Verification Code - Mich Manage', 
                    sender='michmanage@outlook.com', 
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
        thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
        thread.start()

@login.route('/send-verification-code', methods=["POST"])
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

    
@login.route('/password-reset-verifying_user', methods=["POST"])
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
                    sender='michmanage@outlook.com', 
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
        thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
        thread.start()

    flash('Your password was successfully reset', 'success')
    return redirect('/manager login page')

#######TENANT LOGIN##############
@login.route("/tenant-login", methods=["POST"])
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
                    sender='michmanage@outlook.com', 
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
                    thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
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
@login.route("/tenant-authentication", methods=["POST"])
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
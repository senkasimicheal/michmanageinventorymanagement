from flask import Blueprint, render_template, url_for, request, session, flash, redirect, make_response, jsonify, current_app
from pymongo import ASCENDING
from datetime import datetime, timedelta
from utils import get_mongo_client, get_db_and_fs, send_async_email
from flask_mail import Message
import threading

otherUserAccounts = Blueprint('otherUserAccounts_route', __name__)

##VIEW MANAGER ACCOUNTS
def get_managers_data(registered_managers):
    managers = []
    for manager in registered_managers:
        managers.append((manager['name'], manager['email'], manager['phone_number'], manager['company_name']))
    return managers

@otherUserAccounts.route('/view-user-accounts')
def view_user_accounts():
    db, fs = get_db_and_fs()
    # Get session data
    username = session.get('login_username')
    if username is None:
        flash('Login first', 'error')
        return redirect('/')

    # Get company data
    company = db.registered_managers.find_one({'username': username})
    if 'dp' in company:
        dp_str = company['dp']
    else:
        dp_str = None

    # Check if user is a manager
    is_manager = db.managers.find_one({'manager_email': company['email'], 'name':company['company_name']}) is not None
    if not is_manager:
        flash("You do not have rights to view other users", 'error')
        return render_template("view registered managers.html",dp=dp_str)

    # Get registered managers data
    registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': username}}))
    if not registered_managers:
        flash("We did not find other registered users", 'error')

    # Prepare managers data
    managers = get_managers_data(registered_managers)
    return render_template("view registered managers.html", managers=managers, dp=dp_str)

@otherUserAccounts.route('/delete_manager/<company_name>/<email>', methods=['POST'])
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
@otherUserAccounts.route('/add-new-manager-email')
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
        is_manager = db.managers.find_one({'manager_email': company['email'], 'name':company['company_name']})
        if is_manager:
            return render_template('add new manager email.html', dp=dp_str)
        else:
            flash("You do not have rights to add managers", 'error')
            return redirect('/load-dashboard-page')

@otherUserAccounts.route('/update-new-manager-email', methods=['POST'])
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
            company_name = manager_found['company_name']
            db.managers.update_one({'name': company_name}, {'$push': {'managers': email}})
            db.other_managers.insert_one({'company_name': company_name, 'manager_email': email, 'account_type': account_type})
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Add new manager', 'email':email, 'timestamp': datetime.now()})
            send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
            if send_emails is not None:
                msg = Message('Account Creation Invitation from Mich Manage', 
                            sender='michmanage@outlook.com', 
                            recipients=email)
                msg.html = f"""
                <html>
                <body>
                <p>Dear Manager,</p>
                <p>You have been granted permission to create an account with Mich Manage. Please click the link below to register:</p>
                <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com/manager_register?company_name={company_name}">Register</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
                thread.start()
                
            flash('New manager email was successfully added', 'success')
        return redirect('/add-new-manager-email')
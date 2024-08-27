from flask import Blueprint, render_template, url_for, request, session, flash, redirect, make_response, jsonify, current_app
from pymongo import ASCENDING, DESCENDING
from utils import get_mongo_client, get_db_and_fs, send_async_email
from flask_mail import Message
import threading
from bson.objectid import ObjectId
from datetime import datetime, timedelta, timezone
import calendar
import pytz
import numpy as np
import cv2
import base64
import bcrypt

Admin = Blueprint('admin_route', __name__)

@Admin.route('/admin')
def admin():
    return render_template('admin.html')

@Admin.route('/admin-login', methods=["POST"])
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

@Admin.route('/registered clients')
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

@Admin.route('/add-property-manager-page')
def add_property_manager_page():
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else:
        return render_template("managers accounts.html")

##########ADD MANAGER COMPANY#############
@Admin.route('/add-property-manager', methods=["POST"])
def add_property_manager():
    db, fs = get_db_and_fs()
    login_data = session.get('admin_email')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/admin')
    else:   
        send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

        email = request.form.get('email')
        name = request.form.get('name')
        allowed_managers = request.form.get('managers').split(',')
        manager_email = request.form.get('manager_email')
        subscribed_days = request.form.get('subscribed_days')
        subscribed_days = int(subscribed_days)
        amount_per_month_form_data = request.form.get('amount_per_month')
        amount_per_month = int(amount_per_month_form_data)
           
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
                            sender='michmanage@outlook.com', 
                            recipients=allowed_managers)
                msg.html = f"""
                <html>
                <body>
                <p>Dear Manager,</p>
                <p>You have been granted permission to create an account with Mich Manage. Please click the link below to register:</p>
                <p><b style="font-size: 20px;"><a href="https://michmanagement.onrender.com/manager_register?company_name={name}">Register</a></b></p>
                <p>Best Regards,</p>
                <p>Mich Manage</p>
                </body>
                </html>
                """
                thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
                thread.start()

            flash('Company managers can now create accounts', 'success')
            return render_template("managers accounts.html", user_data=user_data)
        else:
            flash('Company already registered', 'error')
            return render_template("managers accounts.html")

#######NEW SUBSCRIPTION PAGE###############
@Admin.route("/new-subscription")
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
@Admin.route("/new-subscription-initiated", methods=["POST"])
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
                flash('New Subscription was added', 'success')
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
            fields_to_update['amount_per_month'] = int(amount_per_month_form_data)
            flash('New Subscription plan was set', 'success')
        if account_type:
            if 'All Types' in account_type:
                account_type = ['Property Management', 'Enterprise Resource Planning']
            fields_to_update['account_type'] = account_type
            flash('New Subscription plan was set', 'success')

        db.managers.update_one({'name': company_name},{'$set': fields_to_update})
        return render_template("managers accounts.html")

#####ACTIVATE SENDING EMAILS
@Admin.route('/activate sending emails/<send_emails>')
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
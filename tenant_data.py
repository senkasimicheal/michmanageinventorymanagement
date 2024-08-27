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

tenantData = Blueprint('tenantData_route', __name__)

def parse_iso_format(iso_str):
    if iso_str.endswith('Z'):
        iso_str = iso_str[:-1]  # Remove 'Z'
        dt = datetime.fromisoformat(iso_str)
        return dt.replace(tzinfo=pytz.UTC)
    else:
        return datetime.fromisoformat(iso_str)

@tenantData.route('/tenant-data')
def tenant_data():
    db, fs = get_db_and_fs()
    tenantEmail = session.get('tenantEmail')
    propertyName = session.get('propertyName')
    login_data = session.get('tenantID')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant login page')
    else:
        account_type = session.get('account_type')
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

#############LOADING COMPLAINTS PAGE##########
@tenantData.route('/complaint-form')
def complaint_form():
    db, fs = get_db_and_fs()
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant login page')
    else:
        tenant_acc_setting = db.tenant_user_accounts.find_one({'_id': ObjectId(tenant_login_data)})
        dp = tenant_acc_setting.get('dp')
        dp_str = base64.b64encode(base64.b64decode(dp)).decode() if dp else None
        auth = tenant_acc_setting.get('auth', "no")

        return render_template('complaints template.html', dp=dp_str, auth=auth)
    
##########STORE COMPLAINTS##############
@tenantData.route('/add-complaint', methods=["POST"])
def add_complaint():
    db, fs = get_db_and_fs()
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant login page')
    else:
        send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

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
            sender='michmanage@outlook.com', 
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
            thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
            thread.start()

        flash('Complaint submitted, we will get back to you', 'success')
        return redirect('/complaint-form')
    
############SHOW MY COMPLAINTS######################
@tenantData.route('/my-complaints')
def my_complaints():
    db, fs = get_db_and_fs()
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant login page')
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
@tenantData.route('/tenant-reply-to-complaint', methods=['POST'])
def tenant_reply_complaint():
    db, fs = get_db_and_fs()
    tenant_login_data = session.get('tenantID')
    if tenant_login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})

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
            sender='michmanage@outlook.com', 
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
            thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
            thread.start()
        
        return redirect('/my-complaints')

##ACCOUNT SETTING FOR TENANT
@tenantData.route('/tenant-account-setup-page')
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
@tenantData.route('/tenant-account-setup-initiated', methods=["POST"])
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

#Tenant notifications
@tenantData.route('/tenant notifications')
def tenant_notifications():
    db, fs = get_db_and_fs()
    login_data = session.get('tenantID')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/tenant login page')
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

@tenantData.route('/tenant_popup_notifications')
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
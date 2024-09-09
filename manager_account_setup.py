from flask import Blueprint, render_template, url_for, request, session, flash, redirect, make_response, jsonify, current_app
from pymongo import ASCENDING
from utils import get_mongo_client, get_db_and_fs, send_async_email
import numpy as np
import cv2
import base64

managerAccountSetup = Blueprint('managerAccountSetup_route', __name__)

@managerAccountSetup.route('/account-setup-page')
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
@managerAccountSetup.route('/account-setup-initiated', methods=["POST"])
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

@managerAccountSetup.route('/apikey')
def apikey():
    db, fs = get_db_and_fs()
    login_data = session.get('login_username')
    if login_data is None:
        flash('Login first', 'error')
        return redirect('/')
    else:
        company = db.registered_managers.find_one({'username': login_data},{'_id':0,'createdAt':0,'code':0,'address':0,'password':0})
        apikey = db.managers.find_one({'name': company['company_name']})
        if apikey:
            api = str(apikey['_id'])
            if 'apikey_viewed' in apikey:
                if apikey['apikey_viewed'] == 'yes':
                    apikey_viewed = 'yes'
                    first_part = api[:18]
                    second_part = api[18:]
                    return render_template('apikey.html', first_part=first_part, second_part=second_part, apikey_viewed = apikey_viewed)
                else:
                    apikey_viewed = 'no'
                    db.managers.update_one({'name': company['company_name']}, {'$set': {'apikey_viewed': 'yes'}})
                    return render_template('apikey.html',apikey = api, apikey_viewed = apikey_viewed)
            else:
                apikey_viewed = 'no'
                db.managers.update_one({'name': company['company_name']}, {'$set': {'apikey_viewed': 'yes'}})
                return render_template('apikey.html',apikey = api, apikey_viewed = apikey_viewed)
        else:
            flash('No API keys found', 'error')
            return redirect('/account-setup-page')
from flask import Blueprint, render_template, url_for, request, session, flash, redirect, make_response, jsonify, current_app
from utils import get_mongo_client, get_db_and_fs, send_async_email
from flask_mail import Message
import threading

app_documentation = Blueprint('documentation_route', __name__)

@app_documentation.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy policy.html')

@app_documentation.route('/terms-of-service')
def terms_of_service():
    return render_template('terms of service.html')

@app_documentation.route("/about")
def about():
    return render_template("about.html")

@app_documentation.route("/contact")
def contact():
    return render_template("contact.html")

@app_documentation.route('/download-apk')
def download_apk():
    return send_from_directory(directory='.', path='michmanage.apk', as_attachment=True)

@app_documentation.route('/send-message', methods=["POST"])
def send_message():
    db, fs = get_db_and_fs()
    send_emails = db.send_emails.find_one({'emails': "yes"},{'emails': 1})
        
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    message = request.form.get('message')
    admin_sender = 'michmanage@outlook.com'
    #Sending inquiries
    if send_emails is not None:
        msg = Message('Inquiries - Mich Manage', 
        sender='michmanage@outlook.com', 
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
        thread = threading.Thread(target=send_async_email, args=[current_app._get_current_object(), msg])
        thread.start()
    flash('Your inquiry was sent', 'success')
    return redirect('/')

@app_documentation.route('/documentation')
def documentation():
    return render_template('documentation.html')
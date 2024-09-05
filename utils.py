from pymongo import MongoClient
from gridfs import GridFS
from flask_mail import Mail, Message
from flask import current_app

def get_mongo_client():
    client = MongoClient('mongodb://localhost:27017/')
    # client = MongoClient('mongodb+srv://micheal:QCKh2uCbPTdZ5sqS@cluster0.rivod.mongodb.net/ANALYTCOSPHERE?retryWrites=true&w=majority')
    return client

def get_db_and_fs():
    client = get_mongo_client()
    db = client.PropertyManagement
    fs = GridFS(db, collection='contracts')
    return db, fs

def get_mail_instance(app=None):
    if app is None:
        app = current_app
    return Mail(app)

def send_async_email(app, msg):
    with app.app_context():
        mail = get_mail_instance(app)
        mail.send(msg)
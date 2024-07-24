from flask_mail import Mail, Message
from app import send_reports, send_payment_reminders, send_contract_expiry_reminders

def scheduled_tasks():
    send_reports()
    send_payment_reminders()
    send_contract_expiry_reminders()

if __name__ == "__main__":
    scheduled_tasks()
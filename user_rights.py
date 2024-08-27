from flask import Blueprint, render_template, url_for, request, session, flash, redirect, make_response, jsonify, current_app
from pymongo import ASCENDING
from datetime import datetime, timedelta
from utils import get_mongo_client, get_db_and_fs, send_async_email

userRights = Blueprint('userRights_route', __name__)

def get_managers_data(registered_managers):
    managers = []
    for manager in registered_managers:
        managers.append((manager['name'], manager['email'], manager['phone_number'], manager['company_name']))
    return managers

####MANAGE USER RIGHTS
@userRights.route('/manage-user-rights')
def manage_user_rights():
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
        
        # Get registered managers data
        registered_managers = list(db.registered_managers.find({'company_name': company['company_name'], 'username': {'$ne': login_data}}))
        if not registered_managers:
            flash("We did not find other registered users", 'error')

        # Prepare managers data
        managers = get_managers_data(registered_managers)

        return render_template('user rights.html',managers=managers,dp=dp_str)
    
@userRights.route('/manage-user-rights-page/<email>/<company_name>')
def manage_user_rights_page(email,company_name):
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
        view_sales = manager.get('view_sales', "no")
        system_selling_price = manager.get('system_selling_price', "no")
        point_of_sale = manager.get('point_of_sale', "no")
        view_finance_dashboard = manager.get('view_finance_dashboard', "no")
        add_new_finance_account = manager.get('add_new_finance_account', "no")
        update_finance_account = manager.get('update_finance_account', "no")
        view_finance = manager.get('view_finance', "no")
        edit_finance = manager.get('edit_finance', "no")
        delete_finance = manager.get('delete_finance', "no")
        
        return render_template('user rights page.html', email=email,company_name=company_name,
                               add_properties=add_properties,add_tenants=add_tenants,
                               update_tenant=update_tenant,edit_tenant=edit_tenant,
                               manage_contracts=manage_contracts,add_stock=add_stock,
                               update_stock=update_stock,update_sales=update_sales,inhouse=inhouse,
                               view_stock_info=view_stock_info,view_revenue=view_revenue,view_sales=view_sales,
                               system_selling_price=system_selling_price,point_of_sale=point_of_sale,
                               view_finance_dashboard=view_finance_dashboard,add_new_finance_account=add_new_finance_account,
                               update_finance_account=update_finance_account,view_finance=view_finance,
                               edit_finance=edit_finance,delete_finance=delete_finance,dp=dp_str)

@userRights.route('/user-rights-initiated', methods=["POST"])
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
        system_selling_price = request.form.get('system_selling_price')
        point_of_sale = request.form.get('point_of_sale')
        view_finance_dashboard = request.form.get('view_finance_dashboard')
        add_new_finance_account = request.form.get('add_new_finance_account')
        update_finance_account = request.form.get('update_finance_account')
        view_finance = request.form.get('view_finance')
        edit_finance = request.form.get('edit_finance')
        delete_finance = request.form.get('delete_finance')

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
        if system_selling_price:
            update_fields['system_selling_price'] = system_selling_price
        if point_of_sale:
            update_fields['point_of_sale'] = point_of_sale
        if view_finance_dashboard:
            update_fields['view_finance_dashboard'] = view_finance_dashboard
        if add_new_finance_account:
            update_fields['add_new_finance_account'] = add_new_finance_account
        if update_finance_account:
            update_fields['update_finance_account'] = update_finance_account
        if view_finance:
            update_fields['view_finance'] = view_finance
        if edit_finance:
            update_fields['edit_finance'] = edit_finance
        if delete_finance:
            update_fields['delete_finance'] = delete_finance

        if not update_fields:
            flash("No updates were made", 'error')
        else:
            # Update the document with the non-empty fields
            db.registered_managers.update_one({'email': email, 'company_name': company_name}, {'$set': update_fields})
            db.audit_logs.insert_one({'user': login_data, 'Activity': 'Change of user rights', 'email':email, 'timestamp': datetime.now()})
            flash("User rights were set successfully", 'success')
        return redirect('/manage-user-rights')
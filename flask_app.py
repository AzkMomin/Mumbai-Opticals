from flask import Flask, render_template, redirect, jsonify, url_for, request,flash,session, abort, make_response # type: ignore
from mysql.connector import IntegrityError, Error
from mysql.connector import ProgrammingError
from io import BytesIO
import os
from functools import wraps
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin # type: ignore
from datetime import datetime, timedelta
import re
import base64
import uuid
import pytz
from werkzeug.security import generate_password_hash # type: ignore
import mysql.connector
from collections import defaultdict
from decimal import Decimal
import math
import secrets
from werkzeug.utils import secure_filename
from urllib.parse import quote

# Define the Flask app instance
app = Flask(__name__,static_folder='static', static_url_path='/static')

#=================================================================================================

                        #Database Connection

#=================================================================================================
from config import HOST, USER, PASSWORD
DB = 'hamdanopticals$mumbaiopticals'

app.config['MYSQL_HOST'] = HOST
app.config['MYSQL_USER'] = USER
app.config['MYSQL_PASSWORD'] = PASSWORD
app.config['MYSQL_DB'] = DB
app.secret_key = secrets.token_hex(32)

# File upload config
app.config['UPLOAD_FOLDER'] = 'static/uploads/products'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/uploads/prescriptions', exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = get_db_connection()
    return conn

def get_db_connection():
    conn = mysql.connector.connect(
        host= HOST,
        user= USER,
        password= PASSWORD,
        database= DB
    )
    return conn

#=================================================================================================

                            #Database Connection End

#=================================================================================================

#=================================================================================================

                            # Role-based Authentication

#=================================================================================================

# Function to check if a user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:  # Changed from 'user_type' to 'user_id'
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))
        return f(*args, **kwargs)
    return decorated_function

# Role-based access control decorator
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('user_type') != role:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Unauthorized access route
@app.route('/unauthorized_access')
def unauthorized_access():
    return "You are not authorized to access this page.", 403

# Add this after_request function to prevent caching
@app.after_request
def after_request(response):
    # Prevent all pages from being cached by the browser
    response.headers.add('Cache-Control', 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0')
    response.headers.add('Pragma', 'no-cache')
    response.headers.add('Expires', '0')
    return response

#=================================================================================================

                            # Role-based Authentication End

#=================================================================================================

#=================================================================================================

                            #Helper Functions

#=================================================================================================

def update_stock_transaction(product_id, transaction_type, quantity, reference_id, reference_type, notes=''):
    """Helper function to record stock transactions"""
    try:
        cursor = mysql.connection.cursor()

        # Get current stock
        cursor.execute("SELECT quantity FROM stock WHERE product_id = %s", (product_id,))
        stock = cursor.fetchone()

        if stock:
            previous_quantity = stock['quantity']

            if transaction_type == 'SALE':
                new_quantity = previous_quantity - quantity
            elif transaction_type in ['PURCHASE', 'RETURN']:
                new_quantity = previous_quantity + quantity
            else:  # ADJUSTMENT
                new_quantity = quantity  # quantity here is the new quantity

            # Update stock
            cursor.execute("""
                UPDATE stock SET quantity = %s
                WHERE product_id = %s
            """, (new_quantity, product_id))

            # Record transaction
            cursor.execute("""
                INSERT INTO stock_transactions
                (product_id, transaction_type, quantity, previous_quantity, new_quantity, reference_id, reference_type, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (product_id, transaction_type, quantity, previous_quantity, new_quantity, reference_id, reference_type, notes))

            mysql.connection.commit()

        cursor.close()
    except Exception as e:
        print(f"Error in update_stock_transaction: {str(e)}")

#=================================================================================================

                            #Helper Functions End

#=================================================================================================

#=================================================================================================

                            #Route

#=================================================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/login/view_login')
def view_login():
    return render_template('view_login.html')

@app.route('/login/add_list')
def add_list():
    return render_template('add_list.html')

@app.route('/login/all_list')
def all_list():
    return render_template('all_list.html')
#=================================================================================================

                            #Route End

#=================================================================================================

#=================================================================================================

                            #Login

#=================================================================================================

#-------------------------------------------------------#
                 # User Login
#-------------------------------------------------------#

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        # Get form data
        email = request.form['email']
        password = request.form['password']

        # Validate form inputs
        if not email or not password:
            error = "Please fill in both email and password fields."
            return render_template('login.html', error=error)

        try:
            # Connect to the database
            conn = get_db()
            cursor = conn.cursor(dictionary=True)

            query = "SELECT * FROM users WHERE username = %s AND password = %s"
            cursor.execute(query, (email, password))

            # Fetch user record
            user = cursor.fetchone()

            # Close database connection
            cursor.close()
            conn.close()

            if user:
                print("="*50)
                print("USER FOUND IN DATABASE:")
                print(user)  # Print the entire user record
                print("="*50)

                # Get user details from database
                login_id = user['login_id']
                username = user.get('username', email)
                user_type = user['user_type']

                # Set common session variables
                session['logged_in'] = True
                session['user_id'] = login_id
                session['username'] = username
                session['user_type'] = user_type

                # Force session to save
                session.modified = True

                print("SESSION SET:")
                print(f"user_id: {session.get('user_id')}")
                print(f"user_type: {session.get('user_type')}")
                print(f"username: {session.get('username')}")
                print("="*50)

                # Set role-specific session variables and redirect
                if user_type == 'super-admin' or user_type == 'admin':
                    session['admin_id'] = login_id
                    session['admin_name'] = username
                    return redirect(url_for('dashboard'))
                else:
                    error = "Invalid user type. Please contact administrator."
                    return render_template('login.html', error=error)

            else:
                print("No user found with these credentials")
                error = "Invalid email or password. Please try again."
                return render_template('login.html', error=error)

        except mysql.connector.Error as err:
            print(f"Database Error: {err}")
            error = "A database error occurred. Please try again later."
            return render_template('login.html', error=str(err))

        except Exception as e:
            print(f"Unexpected Error: {e}")
            error = "An unexpected error occurred. Please try again."
            return render_template('login.html', error=str(e))

    # GET request - show the login page
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

#-------------------------------------------------------#
                 # User Login End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # All Logins
#-------------------------------------------------------#

@app.route('/login/logins')
def manage_logins():
    try:
        # Get current logged in user from session
        current_user = {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'user_type': session.get('user_type'),  # 'super-admin', 'admin', 'employee
            'name': session.get('name')
        }

        # Check if user is logged in
        if not current_user['id']:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        # Get page number from query string (default to 1)
        page = request.args.get('page', 1, type=int)
        per_page = 10
        offset = (page - 1) * per_page

        # Get filter type from query string
        filter_type = request.args.get('filter', 'all')
        search_name = request.args.get('search', '')

        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Build count query based on filters
        count_query = "SELECT COUNT(*) as total FROM users WHERE 1=1"
        count_params = []

        # Apply role-based access
        if current_user['user_type'] == 'admin':
            count_query += " AND user_type IN ('admin', 'employee')"
        elif current_user['user_type'] == 'employee':
            count_query += " AND login_id = %s"
            count_params.append(current_user['id'])

        # Apply type filter
        if filter_type != 'all':
            filter_value = filter_type
            # Check if user has permission to see this type
            if not (current_user['user_type'] == 'admin' and filter_type == 'super-admin'):
                count_query += " AND user_type = %s"
                count_params.append(filter_value)

        # Apply name search filter
        if search_name:
            count_query += " AND (name LIKE %s OR username LIKE %s)"
            count_params.extend([f'%{search_name}%', f'%{search_name}%'])

        cursor.execute(count_query, count_params)
        total_records = cursor.fetchone()['total']
        total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1

        # Build main query
        query = """
            SELECT
                login_id,
                user_type,
                username,
                name,
                password,
                gender,
                mobile_no,
                status,
                DATE_FORMAT(created_at, '%d/%m/%Y %h:%i %p') as last_login,
                DATE_FORMAT(updated_at, '%d/%m/%Y %h:%i %p') as updated_at_formatted,
                CASE
                    WHEN user_type = 'super-admin' THEN 'Super Admin'
                    WHEN user_type = 'admin' THEN 'Admin'
                    WHEN user_type = 'employee' THEN 'Employee'
                    ELSE user_type
                END as user_type_display,
                CASE
                    WHEN status = 'active' THEN 'Active'
                    ELSE 'Inactive'
                END as status_display,
                UPPER(LEFT(name, 2)) as initials,
                'System' as created_by
            FROM users
            WHERE 1=1
        """

        params = []

        # Apply role-based access
        if current_user['user_type'] == 'admin':
            query += " AND user_type IN ('admin', 'employee')"
        elif current_user['user_type'] == 'employee':
            query += " AND login_id = %s"
            params.append(current_user['id'])

        # Apply type filter
        if filter_type != 'all':
            filter_value = filter_type
            # Check if user has permission to see this type
            if not (current_user['user_type'] == 'admin' and filter_type == 'super-admin'):
                query += " AND user_type = %s"
                params.append(filter_value)

        # Apply name search filter
        if search_name:
            query += " AND (name LIKE %s OR username LIKE %s)"
            params.extend([f'%{search_name}%', f'%{search_name}%'])

        # Add ordering and pagination
        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cursor.execute(query, params)
        users = cursor.fetchall()

        # Get counts for filter tabs
        cursor.execute("SELECT COUNT(*) as total FROM users")
        total_count = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as total FROM users WHERE user_type = 'super-admin'")
        super_admin_count = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as total FROM users WHERE user_type = 'admin'")
        admin_count = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as total FROM users WHERE user_type = 'employee'")
        employee_count = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as total FROM users WHERE status = 'active'")
        active_count = cursor.fetchone()['total']

        cursor.close()
        conn.close()

        return render_template('logins.html',
                              users=users,
                              current_user=current_user,
                              counts={
                                  'total': total_count,
                                  'super_admin': super_admin_count,
                                  'admin': admin_count,
                                  'employee': employee_count,
                                  'active': active_count
                              },
                              pagination={
                                  'current_page': page,
                                  'total_pages': total_pages,
                                  'total_records': total_records,
                                  'per_page': per_page,
                                  'has_prev': page > 1,
                                  'has_next': page < total_pages,
                                  'prev_page': page - 1,
                                  'next_page': page + 1
                              },
                              current_filter=filter_type,
                              current_search=search_name)

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        flash("Error loading users. Please try again.", "error")
        return redirect(url_for('dashboard'))

    except Exception as e:
        print(f"Unexpected Error: {e}")
        flash("An unexpected error occurred.", "error")
        return redirect(url_for('dashboard'))

#-------------------------------------------------------#
                 # All Logins End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Add Login
#-------------------------------------------------------#

@app.route('/login/add', methods=['GET', 'POST'])
def add_login():
    try:
        # Get login_id from query string for edit mode
        login_id = request.args.get('id', type=int)
        edit_mode = login_id is not None

        # Get current user from session for permissions
        current_user = {
            'id': session.get('user_id'),
            'user_type': session.get('user_type', 'employee'),  # Default if not set
            'name': session.get('name', 'User')
        }

        # Check if user is logged in
        if not current_user['id']:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        # Connect to database
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # If edit mode, fetch existing data
        user_data = None
        if edit_mode:
            # Check permission for editing
            if current_user['user_type'] == 'admin':
                cursor.execute("SELECT user_type FROM users WHERE login_id = %s", (login_id,))
                target_user = cursor.fetchone()
                if target_user and target_user['user_type'] == 'super-admin':
                    flash("You cannot edit Super Admin accounts.", "error")
                    cursor.close()
                    conn.close()
                    return redirect(url_for('manage_logins'))

            cursor.execute("SELECT * FROM users WHERE login_id = %s", (login_id,))
            user_data = cursor.fetchone()
            if not user_data:
                flash("User not found.", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('manage_logins'))

        if request.method == 'POST':
            # Get form data
            full_name = request.form.get('fullName')
            username = request.form.get('username')
            password = request.form.get('password')
            login_type = request.form.get('loginType')
            status = request.form.get('status')
            phone = request.form.get('phone')
            gender = request.form.get('gender')

            # Validate required fields for new users only
            if not edit_mode:
                if not all([full_name, username, password, login_type, status, phone, gender]):
                    flash("All fields are required for new login.", "error")
                    return render_template('add_login.html',
                                         edit_mode=edit_mode,
                                         user_data=user_data,
                                         current_user=current_user)

            if edit_mode:
                # Check if username already exists (if username is being changed)
                if username and username != user_data['username']:
                    cursor.execute("SELECT login_id FROM users WHERE username = %s AND login_id != %s",
                                 (username, login_id))
                    existing_user = cursor.fetchone()
                    if existing_user:
                        flash("Username already exists. Please choose another.", "error")
                        return render_template('add_login.html',
                                             edit_mode=edit_mode,
                                             user_data=user_data,
                                             current_user=current_user)

                # Build dynamic update query - only update fields that are provided
                update_fields = []
                update_values = []

                if full_name and full_name != user_data['name']:
                    update_fields.append("name = %s")
                    update_values.append(full_name)

                if username and username != user_data['username']:
                    update_fields.append("username = %s")
                    update_values.append(username)

                if password and password != user_data['password']:  # Only update if password is changed
                    update_fields.append("password = %s")
                    update_values.append(password)

                if login_type and login_type != user_data['user_type']:
                    update_fields.append("user_type = %s")
                    update_values.append(login_type)

                if status and status != user_data['status']:
                    update_fields.append("status = %s")
                    update_values.append(status)

                if phone and phone != user_data['mobile_no']:
                    update_fields.append("mobile_no = %s")
                    update_values.append(phone)

                if gender and gender != user_data['gender']:
                    update_fields.append("gender = %s")
                    update_values.append(gender)

                # Always update the updated_at timestamp
                update_fields.append("updated_at = NOW()")

                if update_fields:
                    # Add login_id to values
                    update_values.append(login_id)

                    # Build and execute update query
                    update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE login_id = %s"
                    cursor.execute(update_query, update_values)
                    conn.commit()
                    flash("Login updated successfully!", "success")
                    cursor.close()
                    conn.close()
                    return redirect(url_for('manage_logins'))
                else:
                    flash("No changes were made to the login.", "info")
                    cursor.close()
                    conn.close()
                    return redirect(url_for('manage_logins'))

            else:
                # Check if username already exists for new user
                cursor.execute("SELECT login_id FROM users WHERE username = %s", (username,))
                existing_user = cursor.fetchone()
                if existing_user:
                    flash("Username already exists. Please choose another.", "error")
                    return render_template('add_login.html',
                                         edit_mode=edit_mode,
                                         user_data=None,
                                         current_user=current_user)

                # Insert new user
                cursor.execute('''
                    INSERT INTO users
                    (user_type, username, name, password, gender, mobile_no, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ''', (login_type, username, full_name, password, gender, phone, status))
                conn.commit()
                flash("New login added successfully!", "success")
                cursor.close()
                conn.close()
                return redirect(url_for('manage_logins'))

        cursor.close()
        conn.close()

        return render_template('add_login.html',
                             edit_mode=edit_mode,
                             user_data=user_data,
                             current_user=current_user)

    except Exception as e:
        return render_template('add_login.html',error = e)

#-------------------------------------------------------#
                 # Add Login End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Delete Login
#-------------------------------------------------------#

@app.route('/login/delete')
def delete_login():
    try:
        login_id = request.args.get('id', type=int)

        # Check if user is super admin
        if session.get('user_type') != 'super-admin':
            flash("Only Super Admin can delete logins.", "error")
            return redirect(url_for('manage_logins'))

        if not login_id:
            flash("No login ID provided.", "error")
            return redirect(url_for('manage_logins'))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if trying to delete super admin
        cursor.execute("SELECT user_type FROM users WHERE login_id = %s", (login_id,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.", "error")
            cursor.close()
            conn.close()
            return redirect(url_for('manage_logins'))

        if user['user_type'] == 'super-admin':
            flash("Super Admin accounts cannot be deleted.", "error")
            cursor.close()
            conn.close()
            return redirect(url_for('manage_logins'))

        # Delete the user
        cursor.execute("DELETE FROM users WHERE login_id = %s", (login_id,))
        conn.commit()

        cursor.close()
        conn.close()

        flash(f"Login deleted successfully.", "success")
        return redirect(url_for('manage_logins'))

    except mysql.connector.Error as err:
        return redirect(url_for('manage_logins'))

#-------------------------------------------------------#
                 # Delete Login End
#-------------------------------------------------------#

#=================================================================================================

                            #Login End

#=================================================================================================
#******************************************************************************************************************************************************
#=================================================================================================

                            #Customer

#=================================================================================================
#-------------------------------------------------------#
                 # List Customer
#-------------------------------------------------------#

@app.route('/customers')
def customers():
    try:
        # Get current user from session
        current_user = {
            'id': session.get('user_id'),
            'user_type': session.get('user_type'),
            'name': session.get('name')
        }

        # Check if user is logged in
        if not current_user['id']:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        # Get page number from query string
        page = request.args.get('page', 1, type=int)
        per_page = 10
        offset = (page - 1) * per_page

        # Get search parameter
        search = request.args.get('search', '')

        # Connect to database
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Build count query
        count_query = "SELECT COUNT(*) as total FROM customers WHERE 1=1"
        count_params = []

        if search:
            count_query += " AND (name LIKE %s OR email LIKE %s OR phone LIKE %s)"
            count_params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

        cursor.execute(count_query, count_params)
        total_records = cursor.fetchone()['total']
        total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1

        # Main query - SIMPLIFIED: No JOIN, just customers table
        query = """
            SELECT
                customer_id,
                name,
                phone,
                email,
                 DATE_FORMAT(created_at, '%d/%m/%Y %h:%i %p') as created_at
            FROM customers
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (name LIKE %s OR email LIKE %s OR phone LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cursor.execute(query, params)
        customers = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('customers.html',
                             customers=customers,
                             current_user=current_user,
                             pagination={
                                 'current_page': page,
                                 'total_pages': total_pages,
                                 'total_records': total_records,
                                 'per_page': per_page,
                                 'has_prev': page > 1,
                                 'has_next': page < total_pages,
                                 'prev_page': page - 1,
                                 'next_page': page + 1
                             },
                             current_search=search)

    except Exception as e:
        print(f"Error in customers: {str(e)}")
        flash(f"An error occurred: {str(e)}", "error")
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # List Customer End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Add Customer
#-------------------------------------------------------#

@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    try:
        # Get current user from session
        current_user = {
            'id': session.get('user_id'),
            'user_type': session.get('user_type'),
            'name': session.get('name')
        }

        # Check if user is logged in
        if not current_user['id']:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        # Get customer_id for edit mode
        customer_id = request.args.get('id', type=int)
        edit_mode = customer_id is not None

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # If edit mode, fetch existing data
        customer_data = None
        if edit_mode:
            cursor.execute("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
            customer_data = cursor.fetchone()
            if not customer_data:
                flash("Customer not found.", "error")
                cursor.close()
                conn.close()
                return redirect(url_for('customers'))

        if request.method == 'POST':
            # Get form data
            name = request.form.get('name')
            # Use fullPhone if available (from intl-tel-input), otherwise fallback to phone
            phone = request.form.get('fullPhone') or request.form.get('phone')
            email = request.form.get('email')

            # Validate required fields
            if not all([name, phone, email]):
                flash("All fields are required.", "error")
                return render_template('add_customer.html',
                                     edit_mode=edit_mode,
                                     customer_data=customer_data,
                                     current_user=current_user)

            # Ensure phone has + prefix
            if phone and not phone.startswith('+'):
                phone = '+' + phone
            phone_pattern = r'^\+\d{1,3}\d{6,14}$'

            if not re.match(phone_pattern, phone):
                flash("Please enter a valid international phone number with country code (e.g., +919876543210).", "error")
                return render_template('add_customer.html',
                                     edit_mode=edit_mode,
                                     customer_data=customer_data,
                                     current_user=current_user)

            # Validate email format
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash("Please enter a valid email address.", "error")
                return render_template('add_customer.html',
                                     edit_mode=edit_mode,
                                     customer_data=customer_data,
                                     current_user=current_user)

            # Check if email already exists (skip if same email in edit mode)
            if edit_mode:
                # Only check if email is different from current
                if email != customer_data['email']:
                    cursor.execute("SELECT customer_id FROM customers WHERE email = %s AND customer_id != %s",
                                 (email, customer_id))
                    existing_email = cursor.fetchone()
                    if existing_email:
                        flash("Email already exists. Please use another email.", "error")
                        return render_template('add_customer.html',
                                             edit_mode=edit_mode,
                                             customer_data=customer_data,
                                             current_user=current_user)
            else:
                cursor.execute("SELECT customer_id FROM customers WHERE email = %s", (email,))
                existing_email = cursor.fetchone()
                if existing_email:
                    flash("Email already exists. Please use another email.", "error")
                    return render_template('add_customer.html',
                                         edit_mode=edit_mode,
                                         customer_data=customer_data,
                                         current_user=current_user)

            # Check if phone already exists (skip if same phone in edit mode)
            if edit_mode:
                # Only check if phone is different from current
                if phone != customer_data['phone']:
                    cursor.execute("SELECT customer_id FROM customers WHERE phone = %s AND customer_id != %s",
                                 (phone, customer_id))
                    existing_phone = cursor.fetchone()
                    if existing_phone:
                        flash("Phone number already exists. Please use another number.", "error")
                        return render_template('add_customer.html',
                                             edit_mode=edit_mode,
                                             customer_data=customer_data,
                                             current_user=current_user)
            else:
                cursor.execute("SELECT customer_id FROM customers WHERE phone = %s", (phone,))
                existing_phone = cursor.fetchone()
                if existing_phone:
                    flash("Phone number already exists. Please use another number.", "error")
                    return render_template('add_customer.html',
                                         edit_mode=edit_mode,
                                         customer_data=customer_data,
                                         current_user=current_user)

            if edit_mode:
                # Update existing customer
                cursor.execute('''
                    UPDATE customers
                    SET name = %s, phone = %s, email = %s
                    WHERE customer_id = %s
                ''', (name, phone, email, customer_id))
                conn.commit()
                flash("Customer updated successfully!", "success")
                cursor.close()
                conn.close()
                return redirect(url_for('customers'))
            else:
                # Insert new customer
                cursor.execute('''
                    INSERT INTO customers (name, phone, email, created_at)
                    VALUES (%s, %s, %s, NOW())
                ''', (name, phone, email))
                conn.commit()
                flash("Customer added successfully!", "success")
                cursor.close()
                conn.close()
                return redirect(url_for('customers'))

        cursor.close()
        conn.close()

        return render_template('add_customer.html',
                             edit_mode=edit_mode,
                             customer_data=customer_data,
                             current_user=current_user)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Add Customer End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Delete Customer
#-------------------------------------------------------#
@app.route('/customers/delete')
def delete_customer():
    try:
        # Check if user is logged in and has permission
        if session.get('user_type') not in ['super-admin', 'admin']:
            flash("You don't have permission to delete customers.", "error")
            return redirect(url_for('customers'))

        customer_id = request.args.get('id', type=int)
        if not customer_id:
            flash("No customer ID provided.", "error")
            return redirect(url_for('customers'))

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))
        conn.commit()

        cursor.close()
        conn.close()

        flash("Customer deleted successfully!", "success")
        return redirect(url_for('customers'))

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Delete Customer End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # View Customer
#-------------------------------------------------------#
@app.route('/customers/view')
def view_customer():
    try:
        customer_id = request.args.get('id', type=int)
        if not customer_id:
            flash("No customer ID provided.", "error")
            return redirect(url_for('customers'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        query = """
                    SELECT
                        c.customer_id,
                        c.name,
                        c.phone,
                        c.email,
                        DATE_FORMAT(c.created_at, '%d/%m/%Y %h:%i %p') as created_at
                    FROM customers c
                    WHERE c.customer_id = %s
                """

        cursor.execute(query, (customer_id,))
        customer = cursor.fetchone()

        cursor.close()
        conn.close()

        if not customer:
            flash("Customer not found.", "error")
            return redirect(url_for('customers'))

        return render_template('view_customer.html', customer=customer)

    except Exception as e:
        return render_template('error.html', error=e)
#-------------------------------------------------------#
                 # View Customer End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Search Customers
#-------------------------------------------------------#

@app.route('/search_customers')
def search_customers():
    try:
        search_term = request.args.get('term', '')
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        if search_term:
            cursor.execute("""
                SELECT customer_id, name, phone, email
                FROM customers
                WHERE name LIKE %s OR phone LIKE %s
                ORDER BY name
                LIMIT 10
            """, (f'%{search_term}%', f'%{search_term}%'))
        else:
            cursor.execute("SELECT customer_id, name, phone, email FROM customers ORDER BY name LIMIT 10")

        customers = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(customers)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Search Customers End
#-------------------------------------------------------#
#=================================================================================================

                            #Customer End

#=================================================================================================
#******************************************************************************************************************************************************
#=================================================================================================

                            #Products

#=================================================================================================
#-------------------------------------------------------#
                 # Products List
#-------------------------------------------------------#

@app.route('/products')
def products():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        # Get filter from query string
        stock_filter = request.args.get('stock_filter', 'all')
        search_query = request.args.get('search', '')

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Build base query
        base_query = """
            SELECT p.*, pt.type_name, pc.category_name,
                   COALESCE(s.quantity, 0) as quantity,
                   s.purchase_price, s.selling_price, s.reorder_level
            FROM products p
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
            LEFT JOIN stock s ON p.product_id = s.product_id
        """

        # Add WHERE clause based on filters
        where_clauses = []
        params = []

        if search_query:
            where_clauses.append("(p.product_name LIKE %s OR p.model_code LIKE %s)")
            params.extend([f'%{search_query}%', f'%{search_query}%'])

        if stock_filter == 'low':
            where_clauses.append("COALESCE(s.quantity, 0) < 5")
        elif stock_filter == 'medium':
            where_clauses.append("COALESCE(s.quantity, 0) BETWEEN 5 AND 10")
        elif stock_filter == 'high':
            where_clauses.append("COALESCE(s.quantity, 0) > 10")

        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)

        base_query += " ORDER BY p.created_at DESC"

        cursor.execute(base_query, params)
        products = cursor.fetchall()

        # Get all products for counts (unfiltered)
        cursor.execute("""
            SELECT COALESCE(s.quantity, 0) as quantity
            FROM products p
            LEFT JOIN stock s ON p.product_id = s.product_id
        """)
        all_quantities = cursor.fetchall()

        # Calculate stock counts for filter tabs
        total_count = len(all_quantities)
        low_stock_count = 0
        medium_stock_count = 0
        high_stock_count = 0

        for item in all_quantities:
            quantity = item['quantity']
            if quantity < 5:
                low_stock_count += 1
            elif 5 <= quantity <= 10:
                medium_stock_count += 1
            else:  # quantity > 10
                high_stock_count += 1

        counts = {
            'total': total_count,
            'low_stock': low_stock_count,
            'medium_stock': medium_stock_count,
            'high_stock': high_stock_count
        }

        cursor.close()
        conn.close()

        return render_template('products.html',
                             products=products,
                             counts=counts,
                             current_stock_filter=stock_filter,
                             current_search=search_query)

    except Exception as e:
        print(f"Error in products: {str(e)}")
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Products List End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Add Product
#-------------------------------------------------------#

@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            product_type_id = request.form['product_type_id']

            # Get product type details to determine category
            cursor.execute("""
                SELECT pt.*, pc.category_name
                FROM product_types pt
                JOIN product_categories pc ON pt.category_id = pc.category_id
                WHERE pt.type_id = %s
            """, (product_type_id,))
            product_type = cursor.fetchone()

            if not product_type:
                flash("Invalid product type selected.", "error")
                return redirect(url_for('add_product'))

            # Validate required fields
            product_name = request.form.get('product_name', '')
            if not product_name:
                flash("Product name is required.", "error")
                return redirect(url_for('add_product'))

            # Get selling price and purchase price from form
            selling_price = float(request.form.get('selling_price', 0))
            purchase_price = float(request.form.get('purchase_price', 0))

            if selling_price < 0:
                flash("Selling price cannot be negative.", "error")
                return redirect(url_for('add_product'))
            if purchase_price < 0:
                flash("Purchase price cannot be negative.", "error")
                return redirect(url_for('add_product'))

            # Handle file upload
            product_image = ''
            if 'product_image' in request.files:
                file = request.files['product_image']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"

                    # Determine upload folder based on category
                    category_name = product_type['category_name']
                    category_folder = os.path.join(app.config['UPLOAD_FOLDER'], category_name)
                    os.makedirs(category_folder, exist_ok=True)

                    file.save(os.path.join(category_folder, unique_filename))
                    product_image = f"uploads/products/{category_name}/{unique_filename}"

            # Insert product
            query = """
                INSERT INTO products (
                    product_type_id, product_name, product_image, product_description,
                    selling_price, purchase_price,
                    frame_type, material, model_name, model_code, model_color, model_size,
                    lens_type, which_side, lens_for, company,
                    watch_type, watch_mechanism, strap_material, water_resistance, dial_color,
                    sku, brand, color, size, warranty
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            values = (
                product_type_id,
                product_name,
                product_image,
                request.form.get('product_description', ''),
                selling_price,
                purchase_price,
                request.form.get('frame_type', ''),
                request.form.get('material', ''),
                request.form.get('model_name', ''),
                request.form.get('model_code', ''),
                request.form.get('model_color', ''),
                request.form.get('model_size', ''),
                request.form.get('lens_type', ''),
                request.form.get('which_side', ''),
                request.form.get('lens_for', ''),
                request.form.get('company', ''),
                request.form.get('watch_type', ''),
                request.form.get('watch_mechanism', ''),
                request.form.get('strap_material', ''),
                request.form.get('water_resistance', ''),
                request.form.get('dial_color', ''),
                request.form.get('sku', ''),
                request.form.get('brand', ''),
                request.form.get('color', ''),
                request.form.get('size', ''),
                request.form.get('warranty', '')
            )

            cursor.execute(query, values)
            product_id = cursor.lastrowid

            # Insert stock with quantity = 0 (stock will be added separately)
            cursor.execute("""
                INSERT INTO stock (product_id, quantity, reorder_level)
                VALUES (%s, %s, %s)
            """, (
                product_id,
                0,  # Initial quantity set to 0
                request.form.get('reorder_level', 5)
            ))

            conn.commit()
            cursor.close()
            conn.close()

            flash('Product added successfully! Stock can be added later from the "Add Stock" section.', 'success')
            return redirect(url_for('products'))

        # GET request - get product types
        cursor.execute("""
            SELECT pt.*, pc.category_name
            FROM product_types pt
            JOIN product_categories pc ON pt.category_id = pc.category_id
            ORDER BY pc.category_name, pt.type_name
        """)
        product_types = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('add_product.html', product_types=product_types)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Add Product End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Get Product Fields
#-------------------------------------------------------#

@app.route('/get_product_fields/<int:type_id>')
def get_product_fields(type_id):
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM product_types WHERE type_id = %s", (type_id,))
        product_type = cursor.fetchone()
        cursor.close()
        conn.close()

        fields = []
        html = ''

        if product_type['type_name'] in ['Goggles', 'Frames']:
            fields = [
                {'name': 'frame_type', 'label': 'Frame Type', 'type': 'select', 'options': ['Full Rim', 'Half Rim', 'Rimless', 'Sports']},
                {'name': 'material', 'label': 'Material', 'type': 'select', 'options': ['Metal', 'Plastic', 'Acetate', 'Titanium', 'Stainless Steel', 'Wood']},
                {'name': 'model_name', 'label': 'Model Name', 'type': 'text'},
                {'name': 'model_code', 'label': 'Model Code', 'type': 'text'},
                {'name': 'model_color', 'label': 'Model Color', 'type': 'text'},
                {'name': 'model_size', 'label': 'Model Size', 'type': 'text', 'placeholder': 'e.g., 52-18-140'}
            ]
        elif product_type['type_name'] == 'Lenses':
            fields = [
                {'name': 'lens_type', 'label': 'Lens Type', 'type': 'select', 'options': ['Single Vision', 'Bifocal', 'Progressive', 'Photochromic', 'Blue Cut', 'Polarized']},
                {'name': 'which_side', 'label': 'Which Side', 'type': 'select', 'options': ['Both', 'Right Only', 'Left Only']},
                {'name': 'lens_for', 'label': 'Lens For', 'type': 'text', 'placeholder': 'e.g., Reading, Distance, Computer'},
                {'name': 'company', 'label': 'Company', 'type': 'text', 'placeholder': 'e.g., Zeiss, Kodak, Crizal'}
            ]
        elif product_type['type_name'] in ['Wrist Watches', 'Hand Watches']:
            fields = [
                {'name': 'watch_type', 'label': 'Watch Type', 'type': 'select', 'options': ['Analog', 'Digital', 'Analog-Digital', 'Smart']},
                {'name': 'watch_mechanism', 'label': 'Mechanism', 'type': 'select', 'options': ['Quartz', 'Automatic', 'Mechanical', 'Solar', 'Kinetic']},
                {'name': 'strap_material', 'label': 'Strap Material', 'type': 'select', 'options': ['Leather', 'Metal', 'Silicone', 'Fabric', 'Rubber']},
                {'name': 'dial_color', 'label': 'Dial Color', 'type': 'text'},
                {'name': 'water_resistance', 'label': 'Water Resistance', 'type': 'text', 'placeholder': 'e.g., 50m, 100m, 200m'},
                {'name': 'model_name', 'label': 'Model Name', 'type': 'text'},
                {'name': 'model_code', 'label': 'Model Code', 'type': 'text'}
            ]
        else:  # Misc or any other type - Simple fields only
            fields = [

            ]

        for field in fields:
            required = 'required' if field.get('required', False) else ''
            placeholder = f'placeholder="{field.get("placeholder", "")}"' if field.get('placeholder') else ''

            if field['type'] == 'select':
                options = ''.join([f'<option value="{opt}">{opt}</option>' for opt in field['options']])
                html += f'''
                <div class="col-md-4 mb-2">
                    <label class="form-label">{field['label']}</label>
                    <select class="form-control form-control-sm" name="{field['name']}" {required}>
                        <option value="">Select {field['label']}</option>
                        {options}
                    </select>
                </div>
                '''
            else:
                html += f'''
                <div class="col-md-4 mb-2">
                    <label class="form-label">{field['label']}</label>
                    <input type="{field['type']}" class="form-control form-control-sm" name="{field['name']}" {placeholder} {required}>
                </div>
                '''

        return jsonify({
            'type_name': product_type['type_name'],
            'fields': fields,
            'html': html
        })

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Get Product Fields End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # View Product
#-------------------------------------------------------#

@app.route('/products/view/<int:product_id>')
def view_product(product_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get product details
        cursor.execute("""
            SELECT p.*, pt.type_name, pc.category_name,
                   s.quantity, s.purchase_price, s.selling_price, s.reorder_level
            FROM products p
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
            LEFT JOIN stock s ON p.product_id = s.product_id
            WHERE p.product_id = %s
        """, (product_id,))
        product = cursor.fetchone()

        if not product:
            flash("Product not found.", "error")
            cursor.close()
            conn.close()
            return redirect(url_for('products'))

        # Get stock transaction history
        cursor.execute("""
            SELECT * FROM stock_transactions
            WHERE product_id = %s
            ORDER BY created_at DESC
        """, (product_id,))
        transactions = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('view_product.html', product=product, transactions=transactions)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # View Product End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Edit Product
#-------------------------------------------------------#

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # Validate required fields
            product_name = request.form.get('product_name', '')
            if not product_name:
                flash("Product name is required.", "error")
                return redirect(url_for('edit_product', product_id=product_id))

            quantity = int(request.form.get('quantity', 0))
            purchase_price = float(request.form.get('purchase_price', 0))
            selling_price = float(request.form.get('selling_price', 0))

            if quantity < 0:
                flash("Quantity cannot be negative.", "error")
                return redirect(url_for('edit_product', product_id=product_id))
            if purchase_price < 0:
                flash("Purchase price cannot be negative.", "error")
                return redirect(url_for('edit_product', product_id=product_id))
            if selling_price < 0:
                flash("Selling price cannot be negative.", "error")
                return redirect(url_for('edit_product', product_id=product_id))

            # Handle file upload
            product_image = request.form.get('existing_image', '')
            if 'product_image' in request.files:
                file = request.files['product_image']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    product_image = f"uploads/products/{unique_filename}"

            query = """
                UPDATE products SET
                    product_name = %s, product_image = %s, product_description = %s,
                    frame_type = %s, material = %s, model_name = %s,
                    model_code = %s, model_color = %s, model_size = %s,
                    lens_type = %s, which_side = %s, lens_for = %s, company = %s,
                    watch_type = %s, watch_mechanism = %s, strap_material = %s,
                    water_resistance = %s, dial_color = %s,
                    sku = %s, brand = %s, color = %s, size = %s, model_number = %s
                WHERE product_id = %s
            """

            values = (
                product_name,
                product_image,
                request.form.get('product_description', ''),
                request.form.get('frame_type', ''),
                request.form.get('material', ''),
                request.form.get('model_name', ''),
                request.form.get('model_code', ''),
                request.form.get('model_color', ''),
                request.form.get('model_size', ''),
                request.form.get('lens_type', ''),
                request.form.get('which_side', ''),
                request.form.get('lens_for', ''),
                request.form.get('company', ''),
                request.form.get('watch_type', ''),
                request.form.get('watch_mechanism', ''),
                request.form.get('strap_material', ''),
                request.form.get('water_resistance', ''),
                request.form.get('dial_color', ''),
                request.form.get('sku', ''),
                request.form.get('brand', ''),
                request.form.get('color', ''),
                request.form.get('size', ''),
                request.form.get('model_number', ''),
                product_id
            )

            cursor.execute(query, values)

            # Update stock (quantity, purchase_price, selling_price)
            cursor.execute("""
                UPDATE stock SET
                    quantity = %s,
                    purchase_price = %s,
                    selling_price = %s
                WHERE product_id = %s
            """, (quantity, purchase_price, selling_price, product_id))

            conn.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('view_product', product_id=product_id))

        # GET request - fetch product data
        cursor.execute("""
            SELECT p.*, pt.type_name, pc.category_name,
                   s.quantity, s.purchase_price, s.selling_price
            FROM products p
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
            LEFT JOIN stock s ON p.product_id = s.product_id
            WHERE p.product_id = %s
        """, (product_id,))
        product = cursor.fetchone()

        cursor.close()
        conn.close()

        return render_template('edit_product.html', product=product)

    except Exception as e:
        return render_template('error.html',error = e)

#-------------------------------------------------------#
                 # Edit Product End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Delete Product
#-------------------------------------------------------#

@app.route('/products/delete/<int:product_id>')
def delete_product(product_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Check if product is in any bills
        cursor.execute("SELECT COUNT(*) as count FROM bill_items WHERE product_id = %s", (product_id,))
        count = cursor.fetchone()['count']

        if count > 0:
            flash('Cannot delete product as it has been sold in bills', 'error')
        else:
            cursor.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
            conn.commit()
            flash('Product deleted successfully!', 'success')

        cursor.close()
        conn.close()

    except Exception as e:
        return render_template('error.html', error=e)

    return redirect(url_for('products'))

#-------------------------------------------------------#
                 # Delete Product End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Add Stock
#-------------------------------------------------------#

@app.route('/products/add_stock', methods=['GET', 'POST'])
def add_stock():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            product_id = request.form['product_id']
            quantity = int(request.form['quantity'])

            # Get current stock quantity
            cursor.execute("SELECT quantity FROM stock WHERE product_id = %s", (product_id,))
            stock = cursor.fetchone()

            if stock:
                previous_quantity = stock['quantity']
                new_quantity = previous_quantity + quantity

                # Update stock quantity only
                cursor.execute("""
                    UPDATE stock SET quantity = %s WHERE product_id = %s
                """, (new_quantity, product_id))

                # Record transaction
                update_stock_transaction(
                    product_id,
                    'PURCHASE',
                    quantity,
                    product_id,
                    'MANUAL_STOCK',
                    f'Added {quantity} units. Previous: {previous_quantity}, New: {new_quantity}'
                )

            conn.commit()
            flash('Stock updated successfully!', 'success')
            return redirect(url_for('products'))

        # GET request - get products for dropdown
        cursor.execute("""
            SELECT p.product_id, p.product_name, p.product_image, p.selling_price,
                   pt.type_name, pc.category_name,
                   COALESCE(s.quantity, 0) as quantity
            FROM products p
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
            LEFT JOIN stock s ON p.product_id = s.product_id
            ORDER BY p.created_at DESC
        """)
        products = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('add_stock.html', products=products)

    except Exception as e:
        print(f"Error in add_stock: {str(e)}")
        flash(f'Error adding stock: {str(e)}', 'error')
        return redirect(url_for('products'))

#-------------------------------------------------------#
                 # Add Stock End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Low Stock
#-------------------------------------------------------#

@app.route('/products/low_stock')
def low_stock():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get products with low stock
        cursor.execute("""
            SELECT p.*, pt.type_name, pc.category_name,
                   s.quantity, s.reorder_level, s.selling_price
            FROM products p
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
            JOIN stock s ON p.product_id = s.product_id
            WHERE s.quantity <= s.reorder_level
            ORDER BY s.quantity ASC
        """)
        low_stock_products = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('low_stock.html', products=low_stock_products)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Low Stock End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Stock Transactions
#-------------------------------------------------------#

@app.route('/products/stock_transactions')
def stock_transactions():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        # Get filter type from query string
        filter_type = request.args.get('type', 'all')

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Base query
        query = """
            SELECT st.*,
                   p.product_name,
                   p.model_code,
                   p.product_id,
                   pt.type_name,
                   pc.category_name,
                   DATE_FORMAT(st.created_at, '%%d/%%m/%%Y %%h:%%i %%p') as formatted_date
            FROM stock_transactions st
            JOIN products p ON st.product_id = p.product_id
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
        """

        # Add filter if specified
        params = []
        if filter_type != 'all':
            query += " WHERE st.transaction_type = %s"
            params.append(filter_type.upper())

        query += " ORDER BY st.created_at DESC LIMIT 100"

        cursor.execute(query, params)
        transactions = cursor.fetchall()

        # Get all products for the edit modal dropdown
        cursor.execute("""
            SELECT p.product_id, p.product_name, pt.type_name
            FROM products p
            JOIN product_types pt ON p.product_type_id = pt.type_id
            ORDER BY p.product_name
        """)
        all_products = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('stock_transactions.html',
                             transactions=transactions,
                             all_products=all_products,
                             current_filter=filter_type)

    except Exception as e:
        print(f"Error in stock_transactions: {str(e)}")
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for('products'))

#-------------------------------------------------------#
                 # Stock Transactions End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Get Stock Transaction for Edit
#-------------------------------------------------------#

@app.route('/get_stock_transaction/<int:transaction_id>')
def get_stock_transaction(transaction_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT st.*, p.product_name
            FROM stock_transactions st
            JOIN products p ON st.product_id = p.product_id
            WHERE st.transaction_id = %s
        """, (transaction_id,))

        transaction = cursor.fetchone()

        cursor.close()
        conn.close()

        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404

        return jsonify(transaction)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

#-------------------------------------------------------#
                 # Get Stock Transaction End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Edit Stock Transaction
#-------------------------------------------------------#

@app.route('/products/edit_stock_transaction', methods=['POST'])
def edit_stock_transaction():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        transaction_id = request.form['transaction_id']
        product_id = request.form['product_id']
        transaction_type = request.form['transaction_type']
        quantity = int(request.form['quantity'])
        notes = request.form.get('notes', '')

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get the original transaction
        cursor.execute("SELECT * FROM stock_transactions WHERE transaction_id = %s", (transaction_id,))
        original = cursor.fetchone()

        if not original:
            flash('Transaction not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('stock_transactions'))

        # Revert the original transaction effect on stock
        if original['transaction_type'] in ['PURCHASE', 'RETURN']:
            # Original added stock, so subtract it
            stock_change = -original['quantity']
        elif original['transaction_type'] == 'SALE':
            # Original removed stock, so add it back
            stock_change = original['quantity']
        else:  # ADJUSTMENT
            # Original set to new_quantity, revert to previous
            stock_change = original['previous_quantity'] - original['new_quantity']

        # Apply the revert
        cursor.execute("""
            UPDATE stock
            SET quantity = quantity + %s
            WHERE product_id = %s
        """, (stock_change, original['product_id']))

        # Get updated current stock
        cursor.execute("SELECT quantity FROM stock WHERE product_id = %s", (product_id,))
        current = cursor.fetchone()
        current_quantity = current['quantity'] if current else 0

        # Calculate new quantities for the updated transaction
        if transaction_type in ['PURCHASE', 'RETURN']:
            new_quantity = current_quantity + quantity
        elif transaction_type == 'SALE':
            new_quantity = current_quantity - quantity
        else:  # ADJUSTMENT
            new_quantity = quantity

        # Update the transaction
        cursor.execute("""
            UPDATE stock_transactions SET
                product_id = %s,
                transaction_type = %s,
                quantity = %s,
                previous_quantity = %s,
                new_quantity = %s,
                notes = %s
            WHERE transaction_id = %s
        """, (
            product_id,
            transaction_type,
            quantity,
            current_quantity,
            new_quantity,
            notes,
            transaction_id
        ))

        # Apply the new transaction effect on stock
        if transaction_type in ['PURCHASE', 'RETURN']:
            cursor.execute("UPDATE stock SET quantity = quantity + %s WHERE product_id = %s", (quantity, product_id))
        elif transaction_type == 'SALE':
            cursor.execute("UPDATE stock SET quantity = quantity - %s WHERE product_id = %s", (quantity, product_id))
        else:  # ADJUSTMENT
            cursor.execute("UPDATE stock SET quantity = %s WHERE product_id = %s", (quantity, product_id))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Stock transaction updated successfully!', 'success')
        return redirect(url_for('stock_transactions'))

    except Exception as e:
        print(f"Error in edit_stock_transaction: {str(e)}")
        flash(f'Error updating transaction: {str(e)}', 'error')
        return redirect(url_for('stock_transactions'))

#-------------------------------------------------------#
                 # Edit Stock Transaction End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Delete Stock Transaction
#-------------------------------------------------------#

@app.route('/products/delete_stock_transaction/<int:transaction_id>')
def delete_stock_transaction(transaction_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get the transaction to delete
        cursor.execute("SELECT * FROM stock_transactions WHERE transaction_id = %s", (transaction_id,))
        transaction = cursor.fetchone()

        if not transaction:
            flash('Transaction not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('stock_transactions'))

        # Revert the transaction effect on stock
        if transaction['transaction_type'] in ['PURCHASE', 'RETURN']:
            # Transaction added stock, so subtract it
            stock_change = -transaction['quantity']
        elif transaction['transaction_type'] == 'SALE':
            # Transaction removed stock, so add it back
            stock_change = transaction['quantity']
        else:  # ADJUSTMENT
            # Transaction set to new_quantity, revert to previous
            stock_change = transaction['previous_quantity'] - transaction['new_quantity']

        # Apply the revert
        cursor.execute("""
            UPDATE stock
            SET quantity = quantity + %s
            WHERE product_id = %s
        """, (stock_change, transaction['product_id']))

        # Delete the transaction
        cursor.execute("DELETE FROM stock_transactions WHERE transaction_id = %s", (transaction_id,))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Stock transaction deleted successfully! Stock has been reverted.', 'success')
        return redirect(url_for('stock_transactions'))

    except Exception as e:
        print(f"Error in delete_stock_transaction: {str(e)}")
        flash(f'Error deleting transaction: {str(e)}', 'error')
        return redirect(url_for('stock_transactions'))

#-------------------------------------------------------#
                 # Delete Stock Transaction End
#-------------------------------------------------------#

#=================================================================================================

                            #Products End

#=================================================================================================
#******************************************************************************************************************************************************
#=================================================================================================

                            #Bills

#=================================================================================================

#-------------------------------------------------------#
                 # Bills List
#-------------------------------------------------------#

@app.route('/bills')
def bills():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        # Get filter parameters
        status = request.args.get('status', 'all')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        search = request.args.get('search', '')
        is_ajax = request.args.get('ajax', '0') == '1'

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Build query for bills list
        query = """
            SELECT b.*, c.name as customer_name, c.phone as customer_phone,
                   COUNT(bi.item_id) as item_count,
                   DATE_FORMAT(b.bill_date, '%d/%m/%Y') as formatted_date,
                   DATE_FORMAT(b.created_at, '%d/%m/%Y %H:%i') as formatted_created
            FROM bills b
            LEFT JOIN customers c ON b.customer_id = c.customer_id
            LEFT JOIN bill_items bi ON b.bill_id = bi.bill_id
            WHERE 1=1
        """
        params = []

        # Apply status filter - Now using payment_status instead of status
        if status != 'all':
            if status == 'paid':
                query += " AND b.payment_status = 'PAID'"
            elif status == 'pending':
                query += " AND b.payment_status = 'PENDING'"
            elif status == 'partially_paid':
                query += " AND b.payment_status = 'PARTIALLY_PAID'"
            elif status == 'cancelled':
                query += " AND b.status = 'CANCELLED'"

        # Apply date filters
        if date_from:
            query += " AND b.bill_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND b.bill_date <= %s"
            params.append(date_to)

        # Apply search filter
        if search:
            query += " AND (b.bill_number LIKE %s OR c.name LIKE %s OR c.phone LIKE %s)"
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])

        # Group by and order
        query += " GROUP BY b.bill_id ORDER BY b.created_at DESC"

        cursor.execute(query, params)
        bills = cursor.fetchall()

        # Convert Decimal values to float for bills
        for bill in bills:
            bill['subtotal'] = float(bill['subtotal']) if bill['subtotal'] else 0
            bill['discount'] = float(bill['discount']) if bill['discount'] else 0
            bill['tax'] = float(bill['tax']) if bill['tax'] else 0
            bill['total_amount'] = float(bill['total_amount']) if bill['total_amount'] else 0
            bill['total_paid'] = float(bill['total_paid']) if bill.get('total_paid') else 0
            bill['balance_due'] = float(bill['balance_due']) if bill.get('balance_due') else bill['total_amount'] - bill['total_paid']

        # ========== SUMMARY STATISTICS ==========
        # Get summary data for the cards with payment status
        summary_query = """
            SELECT
                COUNT(*) as total_bills,
                SUM(CASE WHEN payment_status = 'PAID' THEN 1 ELSE 0 END) as paid_count,
                SUM(CASE WHEN payment_status = 'PENDING' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN payment_status = 'PARTIALLY_PAID' THEN 1 ELSE 0 END) as partially_paid_count,
                SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) as cancelled_count,
                SUM(CASE WHEN payment_status = 'PAID' THEN total_amount ELSE 0 END) as total_revenue,
                SUM(CASE WHEN payment_status IN ('PENDING', 'PARTIALLY_PAID') AND status != 'CANCELLED' THEN (total_amount - total_paid) ELSE 0 END) as total_outstanding
            FROM bills
            WHERE 1=1
        """
        summary_params = []

        # Apply date filters to summary
        if date_from:
            summary_query += " AND bill_date >= %s"
            summary_params.append(date_from)
        if date_to:
            summary_query += " AND bill_date <= %s"
            summary_params.append(date_to)
        if search:
            summary_query += " AND (bill_number LIKE %s)"
            summary_params.append(f'%{search}%')

        cursor.execute(summary_query, summary_params)
        summary_data = cursor.fetchone()

        # Get additional summary for filter tabs (without search filter)
        tab_summary_query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN payment_status = 'PAID' THEN 1 ELSE 0 END) as paid,
                SUM(CASE WHEN payment_status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN payment_status = 'PARTIALLY_PAID' THEN 1 ELSE 0 END) as partially_paid,
                SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) as cancelled
            FROM bills
        """
        cursor.execute(tab_summary_query)
        tab_counts = cursor.fetchone()

        cursor.close()
        conn.close()

        # Prepare summary dictionary for template
        summary = {
            'total_bills': int(summary_data['total_bills']) if summary_data['total_bills'] else 0,
            'paid_count': int(summary_data['paid_count']) if summary_data['paid_count'] else 0,
            'pending_count': int(summary_data['pending_count']) if summary_data['pending_count'] else 0,
            'partially_paid_count': int(summary_data['partially_paid_count']) if summary_data['partially_paid_count'] else 0,
            'cancelled_count': int(summary_data['cancelled_count']) if summary_data['cancelled_count'] else 0,
            'total_revenue': float(summary_data['total_revenue']) if summary_data['total_revenue'] else 0,
            'total_outstanding': float(summary_data['total_outstanding']) if summary_data['total_outstanding'] else 0
        }

        # Prepare filter counts
        filter_counts = {
            'all': int(tab_counts['total']) if tab_counts['total'] else 0,
            'paid': int(tab_counts['paid']) if tab_counts['paid'] else 0,
            'pending': int(tab_counts['pending']) if tab_counts['pending'] else 0,
            'partially_paid': int(tab_counts['partially_paid']) if tab_counts['partially_paid'] else 0,
            'cancelled': int(tab_counts['cancelled']) if tab_counts['cancelled'] else 0
        }

        # If AJAX request, return JSON for real-time filtering
        if is_ajax:
            html = render_template('bills_partial.html', bills=bills)
            return jsonify({
                'html': html,
                'summary': summary,
                'filter_counts': filter_counts
            })

        return render_template('bills.html',
                             bills=bills,
                             summary=summary,
                             filter_counts=filter_counts,
                             current_status=status,
                             date_from=date_from,
                             date_to=date_to,
                             current_search=search)

    except Exception as e:
        return render_template('error.html', error=e)
#-------------------------------------------------------#
                 # Bills List End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Generate Bill (with Stock Validation)
#-------------------------------------------------------#

@app.route('/bills/generate', methods=['GET', 'POST'])
def generate_bill():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # Validate required fields
            customer_id = request.form.get('customer_id')
            if not customer_id:
                flash("Please select a customer.", "error")
                return redirect(url_for('generate_bill'))

            items = request.form.getlist('items[]')
            if len(items) == 0:
                flash("Please add at least one product to the bill.", "error")
                return redirect(url_for('generate_bill'))

            # Validate stock availability before processing
            quantities = request.form.getlist('quantities[]')
            prices = request.form.getlist('prices[]')
            discounts = request.form.getlist('discounts[]')

            # Stock validation
            stock_errors = []
            for i in range(len(items)):
                product_id = int(items[i])
                quantity = int(quantities[i])

                cursor.execute("""
                    SELECT s.quantity, p.product_name
                    FROM stock s
                    JOIN products p ON s.product_id = p.product_id
                    WHERE s.product_id = %s
                """, (product_id,))
                stock = cursor.fetchone()

                if not stock:
                    stock_errors.append(f"Product not found in stock")
                elif stock['quantity'] < quantity:
                    stock_errors.append(f"{stock['product_name']}: Requested {quantity}, Available {stock['quantity']}")

            if stock_errors:
                flash(f"Cannot generate bill. Stock shortage:\n" + "\n".join(stock_errors), "error")
                return redirect(url_for('generate_bill'))

            # Generate unique bill number
            bill_number = f"BILL-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            subtotal = float(request.form['subtotal'])
            discount_total = float(request.form.get('discount_total', 0))
            tax_percent = float(request.form.get('tax', 0))
            tax_amount = subtotal * (tax_percent / 100)
            total = float(request.form['total'])

            # Calculate payment status
            payment_status = 'PENDING'
            total_paid = 0
            balance_due = total

            # Insert bill
            cursor.execute("""
                INSERT INTO bills (
                    bill_number, customer_id, bill_date, subtotal, discount,
                    tax, total_amount, payment_method, notes, status,
                    payment_status, total_paid, balance_due
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                bill_number,
                customer_id,
                datetime.now().date(),
                subtotal,
                discount_total,
                tax_amount,
                total,
                request.form.get('payment_method', 'CASH'),
                request.form.get('notes', ''),
                'ACTIVE',
                payment_status,
                total_paid,
                balance_due
            ))

            bill_id = cursor.lastrowid

            # Insert bill items and update stock
            for i in range(len(items)):
                product_id = int(items[i])
                quantity = int(quantities[i])
                price = float(prices[i])
                discount = float(discounts[i]) if i < len(discounts) else 0
                discount_amount = (price * quantity) * (discount / 100)
                total_price = (price * quantity) - discount_amount

                cursor.execute("""
                    INSERT INTO bill_items (
                        bill_id, product_id, quantity, price_per_unit,
                        discount_percent, discount_amount, total_price
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    bill_id,
                    product_id,
                    quantity,
                    price,
                    discount,
                    discount_amount,
                    total_price
                ))

                # Update stock
                update_stock_transaction(
                    product_id,
                    'SALE',
                    quantity,
                    bill_id,
                    'BILL',
                    f'Sold {quantity} units in bill {bill_number}'
                )

                cursor.execute("""
                    UPDATE stock
                    SET quantity = quantity - %s
                    WHERE product_id = %s
                """, (quantity, product_id))

            conn.commit()

            # Get customer phone number
            cursor.execute("SELECT phone FROM customers WHERE customer_id = %s", (customer_id,))
            customer = cursor.fetchone()
            customer_phone = customer['phone'] if customer else None

            cursor.close()
            conn.close()

            flash(f'Bill generated successfully! Bill Number: {bill_number}', 'success')

            # Redirect to view bill page
            return redirect(url_for('view_bill', bill_id=bill_id))

        # GET request - show bill generation form
        cursor.execute("""
            SELECT
                p.product_id,
                p.product_name,
                p.product_image,
                p.selling_price,
                pt.type_name,
                pc.category_name,
                s.quantity
            FROM products p
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
            JOIN stock s ON p.product_id = s.product_id
            WHERE s.quantity > 0
            ORDER BY pt.type_name, p.product_name
        """)
        products = cursor.fetchall()

        # Convert Decimal values to float
        for product in products:
            product['quantity'] = int(product['quantity']) if product['quantity'] else 0
            product['selling_price'] = float(product['selling_price']) if product['selling_price'] else 0
            product['type_name'] = product['type_name'] if product['type_name'] else 'Misc'

        cursor.close()
        conn.close()

        return render_template('generate_bill.html', products=products)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Generate Bill Ends
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Receive Payment
#-------------------------------------------------------#

@app.route('/bills/receive_payment/<int:bill_id>', methods=['GET', 'POST'])
def receive_payment(bill_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get bill details
        cursor.execute("""
            SELECT b.*, c.name as customer_name, c.phone as customer_phone,
                   COUNT(bi.item_id) as item_count
            FROM bills b
            LEFT JOIN customers c ON b.customer_id = c.customer_id
            LEFT JOIN bill_items bi ON b.bill_id = bi.bill_id
            WHERE b.bill_id = %s
            GROUP BY b.bill_id
        """, (bill_id,))
        bill = cursor.fetchone()

        if not bill:
            flash('Bill not found', 'error')
            return redirect(url_for('bills'))

        # Convert Decimal values to float for calculations
        bill_total = float(bill['total_amount']) if bill['total_amount'] else 0
        total_paid = float(bill['total_paid']) if bill.get('total_paid') else 0
        balance_due = float(bill['balance_due']) if bill.get('balance_due') else bill_total - total_paid

        # Update bill with converted values for template
        bill['total_amount'] = bill_total
        bill['total_paid'] = total_paid
        bill['balance_due'] = balance_due

        if bill['payment_status'] == 'PAID':
            flash('This bill is already fully paid.', 'warning')
            return redirect(url_for('view_bill', bill_id=bill_id))

        if request.method == 'POST':
            amount = float(request.form['amount'])
            payment_method = request.form['payment_method']
            reference_number = request.form.get('reference_number', '')
            notes = request.form.get('notes', '')

            # Validate payment amount
            if amount <= 0:
                flash('Payment amount must be greater than 0.', 'error')
                return render_template('receive_payment.html', bill=bill)

            if amount > balance_due:
                flash(f'Payment amount cannot exceed balance due of ₹{balance_due:.2f}', 'error')
                return render_template('receive_payment.html', bill=bill)

            # Generate unique payment number
            payment_number = f"PAY-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

            # Insert payment record
            cursor.execute("""
                INSERT INTO payments (bill_id, payment_number, amount, payment_method,
                                    payment_date, reference_number, notes, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                bill_id,
                payment_number,
                amount,
                payment_method,
                datetime.now().date(),
                reference_number,
                notes,
                session.get('user_id')
            ))

            # Update bill payment status
            new_total_paid = total_paid + amount
            new_balance_due = bill_total - new_total_paid

            if new_balance_due <= 0.01:  # Use small epsilon for floating point comparison
                payment_status = 'PAID'
                new_balance_due = 0
            else:
                payment_status = 'PARTIALLY_PAID'

            cursor.execute("""
                UPDATE bills SET
                    total_paid = %s,
                    balance_due = %s,
                    payment_status = %s
                WHERE bill_id = %s
            """, (new_total_paid, new_balance_due, payment_status, bill_id))

            conn.commit()

            flash(f'Payment of ₹{amount:.2f} received successfully! Payment Number: {payment_number}', 'success')
            return redirect(url_for('view_bill', bill_id=bill_id))

        cursor.close()
        conn.close()

        return render_template('receive_payment.html', bill=bill)

    except Exception as e:
        return render_template('error.html', error=e)
#-------------------------------------------------------#
                 # Receive Payment Ends
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # View Payment
#-------------------------------------------------------#

@app.route('/payments/view/<int:payment_id>')
def view_payment(payment_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT p.*, b.bill_number, b.total_amount as bill_total,
                   c.name as customer_name, c.phone as customer_phone,
                   u.name as created_by_name
            FROM payments p
            JOIN bills b ON p.bill_id = b.bill_id
            JOIN customers c ON b.customer_id = c.customer_id
            LEFT JOIN users u ON p.created_by = u.login_id
            WHERE p.payment_id = %s
        """, (payment_id,))
        payment = cursor.fetchone()

        if not payment:
            flash('Payment not found', 'error')
            return redirect(url_for('payments'))

        cursor.close()
        conn.close()

        return render_template('view_payment.html', payment=payment)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # View Payment Ends
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Payments List
#-------------------------------------------------------#

@app.route('/payments')
def payments():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        # Get filter parameters
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        search = request.args.get('search', '')
        is_ajax = request.args.get('ajax', '0') == '1'

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Build query for payments list
        query = """
            SELECT p.*,
                   b.bill_number,
                   b.total_amount as bill_total,
                   c.name as customer_name,
                   c.phone as customer_phone,
                   u.name as received_by,
                   DATE_FORMAT(p.payment_date, '%d/%m/%Y') as formatted_date,
                   DATE_FORMAT(p.created_at, '%d/%m/%Y %H:%i') as formatted_created
            FROM payments p
            JOIN bills b ON p.bill_id = b.bill_id
            JOIN customers c ON b.customer_id = c.customer_id
            LEFT JOIN users u ON p.created_by = u.login_id
            WHERE 1=1
        """
        params = []

        # Apply date filters
        if date_from:
            query += " AND p.payment_date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND p.payment_date <= %s"
            params.append(date_to)

        # Apply search filter
        if search:
            query += " AND (p.payment_number LIKE %s OR b.bill_number LIKE %s OR c.name LIKE %s OR c.phone LIKE %s)"
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term, search_term])

        # Order by
        query += " ORDER BY p.payment_date DESC, p.created_at DESC"

        cursor.execute(query, params)
        payments = cursor.fetchall()

        # Convert Decimal values in payments
        for payment in payments:
            payment['amount'] = float(payment['amount']) if payment['amount'] else 0
            payment['bill_total'] = float(payment['bill_total']) if payment['bill_total'] else 0

        # Get summary statistics
        summary_query = """
            SELECT
                COUNT(*) as total_payments,
                SUM(amount) as total_amount,
                AVG(amount) as avg_payment
            FROM payments
            WHERE 1=1
        """
        summary_params = []

        if date_from:
            summary_query += " AND payment_date >= %s"
            summary_params.append(date_from)
        if date_to:
            summary_query += " AND payment_date <= %s"
            summary_params.append(date_to)

        cursor.execute(summary_query, summary_params)
        summary_data = cursor.fetchone()

        summary = {
            'total_payments': int(summary_data['total_payments']) if summary_data['total_payments'] else 0,
            'total_amount': float(summary_data['total_amount']) if summary_data['total_amount'] else 0,
            'avg_payment': float(summary_data['avg_payment']) if summary_data['avg_payment'] else 0
        }

        cursor.close()
        conn.close()

        if is_ajax:
            html = render_template('payments_partial.html', payments=payments)
            return jsonify({
                'html': html,
                'summary': summary
            })

        return render_template('payments.html',
                             payments=payments,
                             summary=summary,
                             date_from=date_from,
                             date_to=date_to,
                             current_search=search)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Payments List
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Edit Payment
#-------------------------------------------------------#

@app.route('/payments/edit/<int:payment_id>', methods=['GET', 'POST'])
def edit_payment(payment_id):
    try:
        # Check if user is logged in and has permission
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        if session.get('user_type') not in ['super-admin', 'admin']:
            flash("You don't have permission to edit payments.", "error")
            return redirect(url_for('payments'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get payment details
        cursor.execute("""
            SELECT p.*, b.bill_number, b.total_amount as bill_total,
                   b.total_paid, b.balance_due, c.name as customer_name
            FROM payments p
            JOIN bills b ON p.bill_id = b.bill_id
            JOIN customers c ON b.customer_id = c.customer_id
            WHERE p.payment_id = %s
        """, (payment_id,))
        payment = cursor.fetchone()

        if not payment:
            flash('Payment not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('payments'))

        # Convert Decimal to float
        payment['amount'] = float(payment['amount'])
        payment['bill_total'] = float(payment['bill_total'])
        payment['total_paid'] = float(payment['total_paid'])
        payment['balance_due'] = float(payment['balance_due'])

        # Calculate maximum allowed amount (current balance_due + current payment amount)
        payment['max_allowed'] = payment['balance_due'] + payment['amount']

        if request.method == 'POST':
            new_amount = float(request.form['amount'])
            payment_method = request.form['payment_method']
            reference_number = request.form.get('reference_number', '')
            notes = request.form.get('notes', '')
            payment_date = request.form['payment_date']

            # Validate amount
            if new_amount <= 0:
                flash('Payment amount must be greater than 0.', 'error')
                return render_template('edit_payment.html', payment=payment)

            if new_amount > payment['max_allowed']:
                flash(f'Payment amount cannot exceed ₹{payment["max_allowed"]:.2f}', 'error')
                return render_template('edit_payment.html', payment=payment)

            # Calculate the difference
            amount_diff = new_amount - payment['amount']

            # Update payment record
            cursor.execute("""
                UPDATE payments SET
                    amount = %s,
                    payment_method = %s,
                    reference_number = %s,
                    notes = %s,
                    payment_date = %s
                WHERE payment_id = %s
            """, (new_amount, payment_method, reference_number, notes, payment_date, payment_id))

            # Update bill payment totals
            new_total_paid = payment['total_paid'] + amount_diff
            new_balance_due = payment['bill_total'] - new_total_paid

            if new_balance_due <= 0.01:
                payment_status = 'PAID'
                new_balance_due = 0
            elif new_total_paid > 0:
                payment_status = 'PARTIALLY_PAID'
            else:
                payment_status = 'PENDING'

            cursor.execute("""
                UPDATE bills SET
                    total_paid = %s,
                    balance_due = %s,
                    payment_status = %s
                WHERE bill_id = %s
            """, (new_total_paid, new_balance_due, payment_status, payment['bill_id']))

            conn.commit()
            cursor.close()
            conn.close()

            flash('Payment updated successfully!', 'success')
            return redirect(url_for('view_payment', payment_id=payment_id))

        cursor.close()
        conn.close()

        return render_template('edit_payment.html', payment=payment)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Edit Payment Ends
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Delete Payment
#-------------------------------------------------------#

@app.route('/payments/delete/<int:payment_id>')
def delete_payment(payment_id):
    try:
        # Check if user is logged in and has permission
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        if session.get('user_type') not in ['super-admin', 'admin']:
            flash("You don't have permission to delete payments.", "error")
            return redirect(url_for('payments'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get payment details before deletion
        cursor.execute("""
            SELECT p.*, b.bill_id, b.total_amount as bill_total,
                   b.total_paid, b.balance_due
            FROM payments p
            JOIN bills b ON p.bill_id = b.bill_id
            WHERE p.payment_id = %s
        """, (payment_id,))
        payment = cursor.fetchone()

        if not payment:
            flash('Payment not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('payments'))

        # Convert Decimal to float
        payment_amount = float(payment['amount'])
        bill_total = float(payment['bill_total'])
        total_paid = float(payment['total_paid'])

        # Calculate new totals after deletion
        new_total_paid = total_paid - payment_amount
        new_balance_due = bill_total - new_total_paid

        if new_balance_due <= 0.01:
            payment_status = 'PAID'
            new_balance_due = 0
        elif new_total_paid > 0:
            payment_status = 'PARTIALLY_PAID'
        else:
            payment_status = 'PENDING'

        # Update bill totals
        cursor.execute("""
            UPDATE bills SET
                total_paid = %s,
                balance_due = %s,
                payment_status = %s
            WHERE bill_id = %s
        """, (new_total_paid, new_balance_due, payment_status, payment['bill_id']))

        # Delete payment
        cursor.execute("DELETE FROM payments WHERE payment_id = %s", (payment_id,))

        conn.commit()
        cursor.close()
        conn.close()

        flash(f'Payment deleted successfully! Amount ₹{payment_amount:.2f} removed from bill.', 'success')
        return redirect(url_for('payments'))

    except Exception as e:
        print(f"Error in delete_payment: {str(e)}")
        flash(f'Error deleting payment: {str(e)}', 'error')
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Delete Payment Ends
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Send Bill via WhatsApp
#-------------------------------------------------------#

@app.route('/bills/send_whatsapp/<int:bill_id>')
def send_bill_whatsapp(bill_id):
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get customer phone number
        cursor.execute("""
            SELECT c.phone, b.bill_number
            FROM bills b
            JOIN customers c ON b.customer_id = c.customer_id
            WHERE b.bill_id = %s
        """, (bill_id,))
        bill_data = cursor.fetchone()

        cursor.close()
        conn.close()

        if not bill_data or not bill_data['phone']:
            flash("Customer phone number not found.", "error")
            return redirect(url_for('view_bill', bill_id=bill_id))

        # Generate WhatsApp link
        bill_link = url_for('customer_view_bill', bill_id=bill_id, _external=True)
        message = f"Dear Customer,\n\nYour bill has been generated. Click the link below to view your bill:\n\n{bill_link}\n\nThank you for shopping with Mumbai Opticals!"

        # Encode message for WhatsApp
        encoded_message = quote(message)
        whatsapp_url = f"https://wa.me/{bill_data['phone'].replace('+', '')}?text={encoded_message}"

        return redirect(whatsapp_url)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Send Bill via WhatsApp Ends
#-------------------------------------------------------#

#-------------------------------------------------------#
        # Customer View Bill (with Phone Verification)
#-------------------------------------------------------#

@app.route('/customer/bill/<int:bill_id>', methods=['GET', 'POST'])
def customer_view_bill(bill_id):
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get bill details
        cursor.execute("""
            SELECT b.*, c.name as customer_name, c.phone as customer_phone,
                   c.email as customer_email
            FROM bills b
            JOIN customers c ON b.customer_id = c.customer_id
            WHERE b.bill_id = %s
        """, (bill_id,))
        bill = cursor.fetchone()

        if not bill:
            flash("Bill not found.", "error")
            return redirect(url_for('index'))

        if request.method == 'POST':
            # Verify phone number
            entered_phone = request.form.get('phone')
            stored_phone = bill['customer_phone']

            # Normalize phone numbers for comparison
            entered_phone_clean = re.sub(r'[^\d]', '', entered_phone)
            stored_phone_clean = re.sub(r'[^\d]', '', stored_phone)

            if entered_phone_clean == stored_phone_clean or entered_phone == stored_phone:
                # Phone verified, store in session and show bill
                session[f'bill_verified_{bill_id}'] = True
                return redirect(url_for('customer_view_bill', bill_id=bill_id))
            else:
                flash("Incorrect phone number. Please try again.", "error")
                return render_template('customer_verify.html', bill_id=bill_id)

        # Check if bill is already verified in session
        if session.get(f'bill_verified_{bill_id}'):
            # Get bill items
            cursor.execute("""
                SELECT bi.*, p.product_name, p.model_code, p.product_image,
                       pt.type_name
                FROM bill_items bi
                JOIN products p ON bi.product_id = p.product_id
                JOIN product_types pt ON p.product_type_id = pt.type_id
                WHERE bi.bill_id = %s
            """, (bill_id,))
            items = cursor.fetchall()

            cursor.close()
            conn.close()

            # Company details
            company = {
                'name': 'Mumbai Opticals',
                'address': '123, Linking Road, Bandra West, Mumbai - 400050',
                'phone': '+91 98765 43210',
                'email': 'info@mumbaiopticals.com',
                'gst': '27AAECM1234F1Z9',
                'logo': url_for('static', filename='images/logo.png', _external=True)
            }

            return render_template('customer_bill.html', bill=bill, items=items, company=company)

        cursor.close()
        conn.close()

        # Show phone verification page
        return render_template('customer_verify.html', bill_id=bill_id)

    except Exception as e:
        return render_template('error.html', error=e)
#-------------------------------------------------------#
       # Customer View Bill (with Phone Verification) End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Print Bill
#-------------------------------------------------------#

@app.route('/bills/print/<int:bill_id>')
def print_bill(bill_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get bill details
        cursor.execute("""
            SELECT b.*, c.name as customer_name, c.phone as customer_phone,
                   c.email as customer_email
            FROM bills b
            LEFT JOIN customers c ON b.customer_id = c.customer_id
            WHERE b.bill_id = %s
        """, (bill_id,))
        bill = cursor.fetchone()

        if not bill:
            flash('Bill not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('bills'))

        # Get bill items
        cursor.execute("""
            SELECT bi.*, p.product_name, p.model_code
            FROM bill_items bi
            JOIN products p ON bi.product_id = p.product_id
            WHERE bi.bill_id = %s
        """, (bill_id,))
        items = cursor.fetchall()

        cursor.close()
        conn.close()

        # Company details
        company = {
            'name': 'Mumbai Opticals',
            'address': '123, Linking Road, Bandra West, Mumbai - 400050',
            'phone': '+91 98765 43210',
            'email': 'info@mumbaiopticals.com',
            'gst': '27AAECM1234F1Z9'
        }

        return render_template('print_bill.html', bill=bill, items=items, company=company)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Print Bill End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Search Products for Bill
#-------------------------------------------------------#

@app.route('/search_products')
def search_products():
    try:
        search_term = request.args.get('term', '')
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.product_id, p.product_name, p.product_image,
                   pt.type_name, pc.category_name, s.quantity, s.selling_price
            FROM products p
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
            JOIN stock s ON p.product_id = s.product_id
            WHERE s.quantity > 0
              AND (p.product_name LIKE %s OR p.model_code LIKE %s OR p.model_name LIKE %s)
            ORDER BY p.product_name
            LIMIT 20
        """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(products)
    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Search Products for Bill End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # View Bill
#-------------------------------------------------------#

@app.route('/bills/view/<int:bill_id>')
def view_bill(bill_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Get bill details with customer info
        cursor.execute("""
            SELECT b.*, c.name as customer_name, c.phone as customer_phone,
                   c.email as customer_email
            FROM bills b
            LEFT JOIN customers c ON b.customer_id = c.customer_id
            WHERE b.bill_id = %s
        """, (bill_id,))
        bill = cursor.fetchone()

        if not bill:
            flash('Bill not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('bills'))

        # Convert Decimal values to float for template
        bill['subtotal'] = float(bill['subtotal']) if bill['subtotal'] else 0
        bill['discount'] = float(bill['discount']) if bill['discount'] else 0
        bill['tax'] = float(bill['tax']) if bill['tax'] else 0
        bill['total_amount'] = float(bill['total_amount']) if bill['total_amount'] else 0
        bill['total_paid'] = float(bill['total_paid']) if bill.get('total_paid') else 0
        bill['balance_due'] = float(bill['balance_due']) if bill.get('balance_due') else bill['total_amount'] - bill['total_paid']

        # Get bill items with product details
        cursor.execute("""
            SELECT bi.*, p.product_name, p.product_image, p.model_code,
                   pt.type_name, pc.category_name
            FROM bill_items bi
            JOIN products p ON bi.product_id = p.product_id
            JOIN product_types pt ON p.product_type_id = pt.type_id
            JOIN product_categories pc ON pt.category_id = pc.category_id
            WHERE bi.bill_id = %s
        """, (bill_id,))
        items = cursor.fetchall()

        # Convert Decimal values in items
        for item in items:
            item['price_per_unit'] = float(item['price_per_unit']) if item['price_per_unit'] else 0
            item['discount_percent'] = float(item['discount_percent']) if item.get('discount_percent') else 0
            item['discount_amount'] = float(item['discount_amount']) if item.get('discount_amount') else 0
            item['total_price'] = float(item['total_price']) if item['total_price'] else 0

        # Get payment history
        cursor.execute("""
            SELECT p.*, u.name as received_by
            FROM payments p
            LEFT JOIN users u ON p.created_by = u.login_id
            WHERE p.bill_id = %s
            ORDER BY p.payment_date DESC
        """, (bill_id,))
        payments = cursor.fetchall()

        # Convert Decimal values in payments
        for payment in payments:
            payment['amount'] = float(payment['amount']) if payment['amount'] else 0

        cursor.close()
        conn.close()

        return render_template('view_bill.html', bill=bill, items=items, payments=payments)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # View Bill End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Edit Bill
#-------------------------------------------------------#

@app.route('/bills/edit/<int:bill_id>', methods=['GET', 'POST'])
def edit_bill(bill_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # Update bill details
            cursor.execute("""
                UPDATE bills SET
                    customer_id = %s,
                    bill_date = %s,
                    discount = %s,
                    tax = %s,
                    payment_method = %s,
                    status = %s,
                    notes = %s
                WHERE bill_id = %s
            """, (
                request.form.get('customer_id') or None,
                request.form['bill_date'],
                request.form.get('discount', 0),
                request.form.get('tax', 0),
                request.form['payment_method'],
                request.form['status'],
                request.form.get('notes', ''),
                bill_id
            ))

            conn.commit()
            flash('Bill updated successfully!', 'success')
            return redirect(url_for('view_bill', bill_id=bill_id))

        # GET request - fetch bill data
        cursor.execute("""
            SELECT b.*, c.name as customer_name, c.phone as customer_phone
            FROM bills b
            LEFT JOIN customers c ON b.customer_id = c.customer_id
            WHERE b.bill_id = %s
        """, (bill_id,))
        bill = cursor.fetchone()

        if not bill:
            flash('Bill not found', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('bills'))

        # Get bill items
        cursor.execute("""
            SELECT bi.*, p.product_name, p.product_image
            FROM bill_items bi
            JOIN products p ON bi.product_id = p.product_id
            WHERE bi.bill_id = %s
        """, (bill_id,))
        items = cursor.fetchall()

        # Get all products for potential item changes
        cursor.execute("""
            SELECT p.product_id, p.product_name, s.selling_price, s.quantity
            FROM products p
            JOIN stock s ON p.product_id = s.product_id
            WHERE s.quantity > 0
            ORDER BY p.product_name
        """)
        products = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('edit_bill.html', bill=bill, items=items, products=products)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Edit Bill End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Delete Bill
#-------------------------------------------------------#

@app.route('/bills/delete/<int:bill_id>')
def delete_bill(bill_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # First, restore stock for items in this bill
        cursor.execute("SELECT product_id, quantity FROM bill_items WHERE bill_id = %s", (bill_id,))
        items = cursor.fetchall()

        for item in items:
            # Record stock return transaction
            update_stock_transaction(
                item['product_id'],
                'RETURN',
                item['quantity'],
                bill_id,
                'BILL_DELETED',
                f'Stock restored from deleted bill #{bill_id}'
            )

            # Update stock quantity
            cursor.execute("""
                UPDATE stock
                SET quantity = quantity + %s
                WHERE product_id = %s
            """, (item['quantity'], item['product_id']))

        # Delete bill (cascade will delete bill_items)
        cursor.execute("DELETE FROM bills WHERE bill_id = %s", (bill_id,))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Bill deleted successfully and stock restored!', 'success')

    except Exception as e:
        return render_template('error.html', error=e)

    return redirect(url_for('bills'))

#-------------------------------------------------------#
                 # Delete Bill End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Cancel Bill
#-------------------------------------------------------#

@app.route('/bills/cancel/<int:bill_id>')
def cancel_bill(bill_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # Update bill status
        cursor.execute("UPDATE bills SET status = 'CANCELLED' WHERE bill_id = %s", (bill_id,))

        # Restore stock
        cursor.execute("SELECT product_id, quantity FROM bill_items WHERE bill_id = %s", (bill_id,))
        items = cursor.fetchall()

        for item in items:
            update_stock_transaction(
                item['product_id'],
                'RETURN',
                item['quantity'],
                bill_id,
                'BILL_CANCELLED',
                f'Stock restored from cancelled bill #{bill_id}'
            )

            cursor.execute("""
                UPDATE stock
                SET quantity = quantity + %s
                WHERE product_id = %s
            """, (item['quantity'], item['product_id']))

        conn.commit()
        cursor.close()
        conn.close()

        flash('Bill cancelled successfully and stock restored!', 'success')

    except Exception as e:
        return render_template('error.html', error=e)

    return redirect(url_for('view_bill', bill_id=bill_id))

#-------------------------------------------------------#
                 # Cancel Bill End
#-------------------------------------------------------#

#=================================================================================================

                            #Bills End

#=================================================================================================
#******************************************************************************************************************************************************
#=================================================================================================

                            #Prescriptions

#=================================================================================================
#-------------------------------------------------------#
                 # Prescriptions List
#-------------------------------------------------------#

@app.route('/prescriptions')
def prescriptions_list():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT pr.*, c.name as customer_name, c.phone as customer_phone, c.email as customer_email
            FROM prescriptions pr
            JOIN customers c ON pr.customer_id = c.customer_id
            ORDER BY pr.prescription_date DESC
        """)
        prescriptions = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('prescriptions_list.html', prescriptions=prescriptions)

    except Exception as e:
        return render_template('error.html', error=e)


@app.route('/debug_prescription_images')
def debug_prescription_images():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT prescription_id, photo_path
            FROM prescriptions
            WHERE photo_path IS NOT NULL AND photo_path != ''
        """)
        prescriptions = cursor.fetchall()
        cursor.close()
        conn.close()

        result = []
        base_dir = os.path.join(app.root_path, 'static')

        for pres in prescriptions:
            # Full path where file should be
            full_path = os.path.join(base_dir, pres['photo_path'])
            exists = os.path.exists(full_path)

            # Get file info
            file_info = {
                'id': pres['prescription_id'],
                'db_path': pres['photo_path'],
                'full_path': full_path,
                'exists': exists,
                'url': url_for('static', filename=pres['photo_path']) if exists else None
            }

            if exists:
                file_info['size'] = os.path.getsize(full_path)
                file_info['permissions'] = oct(os.stat(full_path).st_mode)[-3:]

            result.append(file_info)

        return jsonify({
            'base_directory': base_dir,
            'base_dir_exists': os.path.exists(base_dir),
            'prescriptions': result
        })

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Prescriptions List End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Add Prescription
#-------------------------------------------------------#

@app.route('/prescriptions/add', methods=['GET', 'POST'])
def add_prescription():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        if request.method == 'POST':
            conn = get_db()
            cursor = conn.cursor(dictionary=True)

            # Handle file upload
            photo_path = ''
            if 'photo' in request.files:
                photo = request.files['photo']
                filename = secure_filename(photo.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_filename = f"pres_{timestamp}_{filename}"

                # Use absolute path for saving
                upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'prescriptions')
                os.makedirs(upload_dir, exist_ok=True)

                # Save file
                file_path = os.path.join(upload_dir, new_filename)
                photo.save(file_path)

                # Set permissions (important for PythonAnywhere)
                os.chmod(file_path, 0o644)

                # Store relative path in database (this is correct)
                photo_path = f"uploads/prescriptions/{new_filename}"

            query = """
                INSERT INTO prescriptions (
                    customer_id, prescription_date, eye, splt, cvl, axis,
                    add_value, vision, pupillary_distance, photo_path
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                request.form['customer_id'],
                request.form['prescription_date'],
                request.form.get('eye', ''),
                request.form.get('splt') or None,
                request.form.get('cvl') or None,
                request.form.get('axis') or None,
                request.form.get('add_value') or None,
                request.form.get('vision', ''),
                request.form.get('pupillary_distance') or None,
                photo_path
            )

            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()

            flash('Prescription added successfully!', 'success')
            return redirect(url_for('prescriptions_list'))

        return render_template('add_prescription.html')

    except Exception as e:
        return render_template('error.html', error = e)

#-------------------------------------------------------#
                 # Add Prescription End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # View Prescription
#-------------------------------------------------------#

@app.route('/prescriptions/view/<int:prescription_id>')
def view_prescription(prescription_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT pr.*, c.name as customer_name, c.phone as customer_phone, c.email as customer_email
            FROM prescriptions pr
            JOIN customers c ON pr.customer_id = c.customer_id
            WHERE pr.prescription_id = %s
        """, (prescription_id,))
        prescription = cursor.fetchone()

        cursor.close()
        conn.close()

        if not prescription:
            flash('Prescription not found', 'error')
            return redirect(url_for('prescriptions_list'))

        return render_template('view_prescription.html', prescription=prescription)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # View Prescription End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Print Prescription
#-------------------------------------------------------#

@app.route('/prescriptions/print/<int:prescription_id>')
def print_prescription(prescription_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT pr.*, c.name as customer_name, c.phone as customer_phone, c.email as customer_email
            FROM prescriptions pr
            JOIN customers c ON pr.customer_id = c.customer_id
            WHERE pr.prescription_id = %s
        """, (prescription_id,))
        prescription = cursor.fetchone()

        cursor.close()
        conn.close()

        if not prescription:
            flash('Prescription not found', 'error')
            return redirect(url_for('prescriptions_list'))

        return render_template('print_prescription.html', prescription=prescription)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Print Prescription End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Delete Prescription
#-------------------------------------------------------#

@app.route('/prescriptions/delete/<int:prescription_id>')
def delete_prescription(prescription_id):
    try:
        # Check if user is logged in and has permission
        if session.get('user_type') not in ['super-admin', 'admin']:
            flash("You don't have permission to delete prescriptions.", "error")
            return redirect(url_for('prescriptions_list'))

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM prescriptions WHERE prescription_id = %s", (prescription_id,))
        conn.commit()

        cursor.close()
        conn.close()

        flash('Prescription deleted successfully!', 'success')

    except Exception as e:
        return render_template('error.html', error=e)

    return redirect(url_for('prescriptions_list'))

#-------------------------------------------------------#
                 # Delete Prescription End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Edit Prescription
#-------------------------------------------------------#

@app.route('/prescriptions/edit/<int:prescription_id>', methods=['GET', 'POST'])
def edit_prescription(prescription_id):
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            flash("Please login to access this page.", "error")
            return redirect(url_for('user_login'))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            # Handle file upload
            photo_path = request.form.get('existing_photo', '')
            if 'photo' in request.files:
                photo = request.files['photo']
                if photo and photo.filename and allowed_file(photo.filename):
                    filename = secure_filename(photo.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    new_filename = f"pres_{timestamp}_{filename}"
                    photo.save(os.path.join('static/uploads/prescriptions', new_filename))
                    photo_path = f"uploads/prescriptions/{new_filename}"

            query = """
                UPDATE prescriptions SET
                    prescription_date = %s,
                    eye = %s,
                    splt = %s,
                    cvl = %s,
                    axis = %s,
                    add_value = %s,
                    vision = %s,
                    pupillary_distance = %s,
                    photo_path = %s
                WHERE prescription_id = %s
            """
            values = (
                request.form['prescription_date'],
                request.form.get('eye', ''),
                request.form.get('splt') or None,
                request.form.get('cvl') or None,
                request.form.get('axis') or None,
                request.form.get('add_value') or None,
                request.form.get('vision', ''),
                request.form.get('pupillary_distance') or None,
                photo_path,
                prescription_id
            )

            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()

            flash('Prescription updated successfully!', 'success')
            return redirect(url_for('view_prescription', prescription_id=prescription_id))

        # GET request - fetch prescription data
        cursor.execute("""
            SELECT pr.*, c.name as customer_name, c.phone as customer_phone, c.email as customer_email
            FROM prescriptions pr
            JOIN customers c ON pr.customer_id = c.customer_id
            WHERE pr.prescription_id = %s
        """, (prescription_id,))
        prescription = cursor.fetchone()

        cursor.close()
        conn.close()

        if not prescription:
            flash('Prescription not found', 'error')
            return redirect(url_for('prescriptions_list'))

        return render_template('add_prescription.html',
                             edit_mode=True,
                             prescription=prescription)

    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Edit Prescription End
#-------------------------------------------------------#

#-------------------------------------------------------#
                 # Get Prescription
#-------------------------------------------------------#

@app.route('/get_customer_prescriptions')
def get_customer_prescriptions():
    try:
        customer_id = request.args.get('customer_id', type=int)
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT prescription_id, prescription_date,
                   right_sph, right_cyl, right_axis, right_add, right_vision,
                   left_sph, left_cyl, left_axis, left_add, left_vision,
                   pupillary_distance
            FROM prescriptions
            WHERE customer_id = %s
            ORDER BY prescription_date DESC
        """, (customer_id,))
        prescriptions = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(prescriptions)
    except Exception as e:
        return render_template('error.html', error=e)

#-------------------------------------------------------#
                 # Get Prescription End
#-------------------------------------------------------#
#=================================================================================================

                            #Prescriptions End

#=================================================================================================
#******************************************************************************************************************************************************
#=================================================================================================

                            #Context Processor

#=================================================================================================

@app.context_processor
def utility_processor():
    def now():
        return datetime.now()
    return dict(now=now)

#=================================================================================================

                            #Context Processor End

#=================================================================================================
#******************************************************************************************************************************************************

if __name__ == '__main__':
    app.run(debug=True)
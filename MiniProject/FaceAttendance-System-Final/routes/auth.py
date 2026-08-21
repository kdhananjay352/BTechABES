import os
import re
from datetime import datetime, date
import random
import string
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf.csrf import validate_csrf, ValidationError
from sqlalchemy import func
from werkzeug.utils import secure_filename
from extensions import db
# Ensure Department and Course are imported
from models import User, Student, FacultyStaff, Department, Course
from services.face_detection import extract_face_encoding, save_encoding
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from rate_limiter import limiter


auth_bp = Blueprint('auth', __name__)

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'


def allowed_file(filename):
    """Check if uploaded file extension is in ALLOWED_EXTENSIONS."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


# =================================================
# Captcha Puzzle (Updated to track type)
# =================================================
def generate_random_captcha():
    """Randomly returns EITHER a complex alphanumeric string (case-sensitive) OR a math puzzle."""
    choice = random.choice(['alphanumeric', 'math'])

    if choice == 'alphanumeric':
        upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
        lower = "abcdefghijkmnpqrstuvwxyz"
        symbols = "!@#$%&*"

        code_chars = [
            random.choice(upper),
            random.choice(lower),
            random.choice(symbols),
            random.choice(upper),
            random.choice(lower)
        ]
        random.shuffle(code_chars)
        code = "".join(code_chars)

        # Store both the exact answer and its type in session
        return code, code, 'alphanumeric'
    else:
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        operator = random.choice(['+', '-', '*'])

        if operator == '-' and num1 < num2:
            num1, num2 = num2, num1
        elif operator == '*':
            num1 = random.randint(1, 5)
            num2 = random.randint(1, 5)

        if operator == '+':
            answer = num1 + num2
        elif operator == '-':
            answer = num1 - num2
        else:
            answer = num1 * num2

        question = f"{num1} {operator} {num2} = ?"
        return question, str(answer), 'math'

# ==============================================================================
# LOGIN ROUTE (UPDATED WITH CASE-SENSITIVE CAPTCHA VERIFICATION)
# ==============================================================================


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("8 per minute", key_func=lambda: request.remote_addr)
def login():
    """Login route with role validation and captcha verification."""
    if current_user.is_authenticated:
        return redirect(url_for('main.attendance'))

    if request.method == 'POST':
        user_answer = request.form.get('captcha_answer', '').strip()
        correct_answer = session.get('captcha_answer', '')
        captcha_type = session.get('captcha_type', 'math')

        # Clear captcha data from session immediately
        session.pop('captcha_answer', None)
        session.pop('captcha_type', None)

        # Validate based on type: Alphanumeric is strict case-sensitive, Math is evaluated as value
        if captcha_type == 'alphanumeric':
            is_valid = (user_answer == correct_answer)
        else:
            is_valid = (user_answer.strip() == correct_answer.strip())

        if not correct_answer or not is_valid:
            flash('Incorrect Captcha code or answer. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        selected_role = request.form.get('userRole', '').strip().lower()
        username_or_email = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        remember = True if request.form.get('rememberMe') else False

        user = User.query.filter(
            (func.lower(User.email) == username_or_email) |
            (func.lower(User.username) == username_or_email)
        ).first()

        if not user or not user.check_password(password):
            flash(
                'Invalid credentials. Please check your username/email and password.', 'danger')
            return redirect(url_for('auth.login'))

        if user.role.lower() != selected_role:
            if not (selected_role == 'teacher' and user.role.lower() in ['teacher', 'faculty']):
                role_label = 'Teacher / Faculty' if selected_role == 'teacher' else selected_role.capitalize()
                flash(
                    f'Account exists, but assigned role is not "{role_label}". Please select your correct login role.', 'warning')
                return redirect(url_for('auth.login'))

        if not user.is_active:
            flash(
                'Your account has been deactivated. Please contact the administrator.', 'warning')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        flash(f'Welcome back, {user.username}!', 'success')
        return redirect(url_for('main.attendance'))

    # Initial GET Request
    question, answer, c_type = generate_random_captcha()
    session['captcha_answer'] = answer
    session['captcha_type'] = c_type
    return render_template('login.html', captcha_question=question)


@auth_bp.route('/refresh-captcha', methods=['GET'])
def refresh_captcha():
    """Refreshes the captcha question, answer, and type."""
    question, answer, c_type = generate_random_captcha()
    session['captcha_answer'] = answer
    session['captcha_type'] = c_type
    return jsonify({'captcha': question})
# def login():
#     if current_user.is_authenticated:
#         return redirect(url_for('main.attendance'))

#     if request.method == 'POST':
#         # 1. Capture Form Inputs
#         selected_role = request.form.get('userRole', '').strip().lower()
#         username_or_email = request.form.get('username', '').strip().lower()
#         password = request.form.get('password', '')
#         remember = True if request.form.get('rememberMe') else False

#         # 2. Query User by Email or Username (Case-Insensitive)
#         user = User.query.filter(
#             (func.lower(User.email) == username_or_email) |
#             (func.lower(User.username) == username_or_email)
#         ).first()

#         # 3. Credential Check
#         if not user or not user.check_password(password):
#             flash(
#                 'Invalid credentials. Please check your username/email and password.', 'danger')
#             return redirect(url_for('auth.login'))

#         # 4. Role Match Check
#         if user.role.lower() != selected_role:
#             if not (selected_role == 'teacher' and user.role.lower() in ['teacher', 'faculty']):
#                 role_label = 'Teacher / Faculty' if selected_role == 'teacher' else selected_role.capitalize()
#                 flash(
#                     f'Account exists, but assigned role is not "{role_label}". Please select your correct login role.', 'warning')
#                 return redirect(url_for('auth.login'))

#         # 5. Account Deactivation Check
#         if not user.is_active:
#             flash(
#                 'Your account has been deactivated. Please contact the administrator.', 'warning')
#             return redirect(url_for('auth.login'))

#         # 6. Authenticate User
#         login_user(user, remember=remember)
#         flash(f'Welcome back, {user.username}!', 'success')
#         return redirect(url_for('main.attendance'))

#     return render_template('login.html')


# ==============================================================================
# REGISTER ROUTE
# ==============================================================================
@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute", key_func=lambda: request.remote_addr)
def register():
    if request.method == 'POST':
        role = request.form.get('role')
        allowed_roles = {'student', 'teacher', 'faculty', 'staff'}
        if role not in allowed_roles:
            flash('Invalid registration role. Please choose a supported role.', 'danger')
            return redirect(url_for('auth.register', step=1))

        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Shared Demographics
        full_name = request.form.get('full_name', '').strip()
        gender = request.form.get('gender')
        dob_str = request.form.get('dob', '').strip()
        mobile_no = request.form.get('mobile_no', '').strip()
        father_name = request.form.get('father_name', '').strip()
        mother_name = request.form.get('mother_name', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pin_code = request.form.get('pincode', '').strip()
        address = request.form.get('address', '').strip()

        # Capture dynamic FK IDs instead of strings
        current_draft = {
            'role': role,
            'username': username,
            'email': email,
            'full_name': full_name,
            'gender': gender,
            'dob': dob_str,
            'mobile_no': mobile_no,
            'father_name': father_name,
            'mother_name': mother_name,
            'city': city,
            'state': state,
            'pincode': pin_code,
            'address': address,
            'roll_no': request.form.get('roll_no', '').strip(),
            'admission_no': request.form.get('admission_no', '').strip(),
            'course_id': request.form.get('course_id', ''),
            'session': request.form.get('session', ''),
            'student_qualification': request.form.get('student_qualification', '').strip(),
            'employee_id': request.form.get('employee_id', '').strip(),
            'designation': request.form.get('designation', '').strip(),
            'department_id': request.form.get('department_id', ''),
            'faculty_qualification': request.form.get('faculty_qualification', '').strip()
        }

        # 1. Case-Insensitive Duplicate Verification
        existing_user = User.query.filter(
            (func.lower(User.email) == email) | (
                func.lower(User.username) == username)
        ).first()

        if existing_user:
            session['registration_draft'] = current_draft
            flash('Username or Email is already registered.', 'warning')
            return redirect(url_for('auth.register', step=1))

        if password != confirm_password:
            session['registration_draft'] = current_draft
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register', step=1))

        # 2. Date of Birth Validation
        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                today = date.today()
                age = today.year - dob.year - \
                    ((today.month, today.day) < (dob.month, dob.day))

                if dob >= today:
                    session['registration_draft'] = current_draft
                    flash('Date of birth cannot be today or in the future.', 'danger')
                    return redirect(url_for('auth.register', step=2))

                if age < 17:
                    session['registration_draft'] = current_draft
                    flash(
                        f'Registration rejected: Minimum required age is 17 years (Calculated age: {age}).', 'danger')
                    return redirect(url_for('auth.register', step=2))

            except ValueError:
                session['registration_draft'] = current_draft
                flash(
                    'Invalid Date of Birth format. Please select a valid date.', 'danger')
                return redirect(url_for('auth.register', step=2))

        # 3. File Upload & AI Face Extraction
        file = request.files.get('face_image')
        face_img_path = None
        encoding_file_path = None

        if not file or not allowed_file(file.filename):
            session['registration_draft'] = current_draft
            flash(
                'Invalid file upload. Please upload a valid .png, .jpg, or .jpeg photo.', 'danger')
            return redirect(url_for('auth.register', step=4))

        filename = secure_filename(f"{username}_{file.filename}")
        filepath = os.path.join(
            current_app.config['UPLOAD_FOLDER_FACES'], filename)
        file.save(filepath)
        face_img_path = filepath

        embedding = extract_face_encoding(filepath)

        if embedding is None:
            if os.path.exists(filepath):
                os.remove(filepath)

            session['registration_draft'] = current_draft
            flash('Warning: Could not detect a clear human face in the uploaded photo. Please upload a clear photo.', 'warning')
            return redirect(url_for('auth.register', step=4))

        enc_filename = f"{username}_encoding.npy"
        encoding_file_path = os.path.join(
            current_app.config['UPLOAD_FOLDER_ENCODINGS'], enc_filename)
        save_encoding(encoding_file_path, embedding)

        # 4. Database Transaction
        try:
            new_user = User(
                username=username,
                email=email,
                role=role
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()

            if role == 'student':
                # Convert the course ID to an integer securely
                course_val = int(current_draft['course_id']) if current_draft.get(
                    'course_id') and current_draft['course_id'].isdigit() else None

                student_profile = Student(
                    student_id=new_user.id,
                    roll_no=current_draft['roll_no'],
                    admission_no=current_draft['admission_no'],
                    full_name=full_name,
                    gender=gender,
                    dob=dob,
                    course_id=course_val,
                    session=current_draft['session'],
                    mobile_no=mobile_no,
                    father_name=father_name,
                    mother_name=mother_name,
                    city=city,
                    state=state,
                    pin_code=pin_code,
                    address=address,
                    last_qualification=current_draft['student_qualification'],
                    photo_path=face_img_path,
                    encoding_path=encoding_file_path
                )
                db.session.add(student_profile)

            elif role in ['faculty', 'staff']:
                # Convert the department ID to an integer securely
                dept_val = int(current_draft['department_id']) if current_draft.get(
                    'department_id') and current_draft['department_id'].isdigit() else None

                faculty_profile = FacultyStaff(
                    staff_id=new_user.id,
                    employee_id=current_draft['employee_id'],
                    full_name=full_name,
                    gender=gender,
                    dob=dob,
                    department_id=dept_val,
                    designation=current_draft['designation'],
                    mobile_no=mobile_no,
                    father_name=father_name,
                    mother_name=mother_name,
                    city=city,
                    state=state,
                    pin_code=pin_code,
                    address=address,
                    qualification=current_draft['faculty_qualification'],
                    photo_path=face_img_path,
                    encoding_path=encoding_file_path
                )
                db.session.add(faculty_profile)

            db.session.commit()
            session.pop('registration_draft', None)
            flash('Registration completed successfully! Please sign in.', 'success')
            return redirect(url_for('auth.login'))

        except SQLAlchemyError as err:
            db.session.rollback()
            session['registration_draft'] = current_draft
            flash(
                f'An error occurred during registration: {str(err)}', 'danger')
            return redirect(url_for('auth.register'))

    # Retrieve draft data and fetch the lists to populate HTML dropdowns
    draft_data = session.pop('registration_draft', None)
    departments = Department.query.order_by(Department.name).all()
    courses = Course.query.order_by(Course.name).all()

    return render_template('register.html', draft_data=draft_data, departments=departments, courses=courses)


# ==============================================================================
# SECURE AJAX USERNAME & EMAIL AVAILABILITY CHECK
# ==============================================================================
@auth_bp.route('/check-availability', methods=['POST'])
def check_availability():
    csrf_token = request.headers.get('X-CSRFToken')
    try:
        validate_csrf(csrf_token)
    except ValidationError:
        return jsonify({'valid': False, 'errors': {'csrf': 'CSRF token is missing or invalid.'}}), 400

    if not request.is_json:
        return jsonify({'valid': False, 'errors': {'request': 'Invalid payload type. Expected JSON.'}}), 400

    data = request.get_json() or {}
    username = str(data.get('username', '')).strip().lower()
    email = str(data.get('email', '')).strip().lower()

    errors = {}

    if username:
        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', username):
            errors['username'] = 'Username must be 3-30 characters long (letters, numbers, underscores).'
        else:
            existing_user = User.query.filter(
                func.lower(User.username) == username).first()
            if existing_user:
                errors['username'] = 'Username is already taken.'

    if email:
        if not re.match(EMAIL_REGEX, email):
            errors[
                'email'] = 'Invalid email format. Please include a valid domain extension (e.g., .com, .ac.in).'
        else:
            existing_email = User.query.filter(
                func.lower(User.email) == email).first()
            if existing_email:
                errors['email'] = 'Email address is already registered.'

    if errors:
        return jsonify({'valid': False, 'errors': errors}), 400

    return jsonify({'valid': True})


# ==============================================================================
# LOGOUT ROUTE
# ==============================================================================
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out successfully.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/extend-session', methods=['POST'])
@login_required
def extend_session():
    """Refresh the authenticated session after an explicit user action."""
    session.permanent = True
    session.modified = True
    return jsonify({'status': 'success', 'message': 'Your session has been extended.'})


# Helper function to get the serializer
def get_reset_serializer():
    # Uses your app's SECRET_KEY to encrypt the token
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per minute", key_func=lambda: request.remote_addr)
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            # 1. Generate a secure token valid for 3600 seconds (1 hour)
            s = get_reset_serializer()
            token = s.dumps(user.email, salt='password-reset-salt')

            # 2. Create the reset link
            reset_link = url_for('auth.reset_password',
                                 token=token, _external=True)

            # 3. TODO: Send the email!
            # You will need to configure Flask-Mail or an API like SendGrid here.
            print(f"DEBUG: Send this link to {user.email}: {reset_link}")

        # Security Best Practice: Always show the same success message whether the
        # email exists or not, to prevent hackers from "guessing" valid emails.
        flash('If an account with that email exists, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit("5 per minute", key_func=lambda: request.remote_addr)
def reset_password(token):
    s = get_reset_serializer()
    try:
        # Try to decode the token. max_age=3600 means it expires in 1 hour.
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except SignatureExpired:
        flash('The password reset link has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    except BadTimeSignature:
        flash('Invalid password reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    # If we get here, the token is valid! Find the user.
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        # Hash the new password through the model so password metadata is updated too.
        try:
            user.set_password(new_password)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash('Unable to reset the password right now. Please try again.', 'danger')
            return render_template('reset_password.html', token=token)

        flash('Your password has been reset successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)


# ==============================================================================
# ERROR HANDLERS
# ==============================================================================
@auth_bp.errorhandler(404)
def page_not_found(_e):
    flash('The page you requested was not found. Please sign in to continue.', 'warning')
    return redirect(url_for('auth.login'))


@auth_bp.errorhandler(500)
def internal_server_error(_e):
    return render_template('500.html'), 500


@auth_bp.errorhandler(403)
def forbidden(_e):
    flash('Please sign in with an authorized account to continue.', 'warning')
    return redirect(url_for('auth.login'))

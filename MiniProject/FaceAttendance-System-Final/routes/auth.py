import os
import re
from datetime import datetime, date
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

auth_bp = Blueprint('auth', __name__)

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'


def allowed_file(filename):
    """Check if uploaded file extension is in ALLOWED_EXTENSIONS."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


# ==============================================================================
# LOGIN ROUTE (UPDATED WITH ROLE VALIDATION)
# ==============================================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.attendance'))

    if request.method == 'POST':
        # 1. Capture Form Inputs
        selected_role = request.form.get('userRole', '').strip().lower()
        username_or_email = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        remember = True if request.form.get('rememberMe') else False

        # 2. Query User by Email or Username (Case-Insensitive)
        user = User.query.filter(
            (func.lower(User.email) == username_or_email) |
            (func.lower(User.username) == username_or_email)
        ).first()

        # 3. Credential Check
        if not user or not user.check_password(password):
            flash(
                'Invalid credentials. Please check your username/email and password.', 'danger')
            return redirect(url_for('auth.login'))

        # 4. Role Match Check
        if user.role.lower() != selected_role:
            if not (selected_role == 'teacher' and user.role.lower() in ['teacher', 'faculty']):
                role_label = 'Teacher / Faculty' if selected_role == 'teacher' else selected_role.capitalize()
                flash(
                    f'Account exists, but assigned role is not "{role_label}". Please select your correct login role.', 'warning')
                return redirect(url_for('auth.login'))

        # 5. Account Deactivation Check
        if not user.is_active:
            flash(
                'Your account has been deactivated. Please contact the administrator.', 'warning')
            return redirect(url_for('auth.login'))

        # 6. Authenticate User
        login_user(user, remember=remember)
        flash(f'Welcome back, {user.username}!', 'success')
        return redirect(url_for('main.attendance'))

    return render_template('login.html')


# ==============================================================================
# REGISTER ROUTE
# ==============================================================================
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role')
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
                course_val = int(current_draft['course_id']) if current_draft.get('course_id') and current_draft['course_id'].isdigit() else None
                
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
                dept_val = int(current_draft['department_id']) if current_draft.get('department_id') and current_draft['department_id'].isdigit() else None
                
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


# ==============================================================================
# ERROR HANDLERS
# ==============================================================================
@auth_bp.errorhandler(404)
def page_not_found(_e):
    return render_template('404.html'), 404


@auth_bp.errorhandler(500)
def internal_server_error(_e):
    return render_template('500.html'), 500


@auth_bp.errorhandler(403)
def forbidden(_e):
    return render_template('403.html'), 403
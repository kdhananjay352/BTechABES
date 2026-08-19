import csv
import io
import os
import cv2
import numpy as np
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, request, Response, jsonify, current_app, flash
from flask_login import login_required, current_user
from sqlalchemy import false, func, or_
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import User, Student, FacultyStaff, AttendanceRecord, Course, Department
# Import your existing custom face detection service
from services.face_detection import extract_face_encoding
from flask import render_template, request, flash, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from rate_limiter import limiter


main_bp = Blueprint('main', __name__)

# ==============================================================================
# GLOBAL CAMERA FRAME STATE
# ==============================================================================
# Holds the latest camera frame so the API route can grab it instantly
# when the "Capture" button is clicked.
global_frame = None


def generate_frames():
    """Capture video frames from the webcam and yield them as a byte stream."""
    global global_frame
    camera = cv2.VideoCapture(0)  # 0 is the default built-in webcam

    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            frame = cv2.flip(frame, 1)
            # Save a clean copy of the current frame for the verification API
            global_frame = frame.copy()

            # Encode the frame in JPEG format for the HTML video stream
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            # Yield the frame in the multipart format expected by the browser
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# ==============================================================================
# UI ROUTES
# ==============================================================================


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.attendance'))
    return redirect(url_for('auth.login'))


@main_bp.route('/attendance')
@login_required
def attendance():
    today_date = date.today()
    role = current_user.role.lower() if current_user.role else 'student'

    # 1. EVERYONE: Get the logged-in user's own record for today
    my_attendance = AttendanceRecord.query.filter_by(
        user_id=current_user.id,
        date=today_date
    ).first()


# 2. ADMIN ONLY: Fetch campus-wide metrics
    admin_stats = {}
    if role == 'admin':
        # Total present today
        admin_stats['total_present'] = db.session.query(func.count(db.distinct(AttendanceRecord.user_id))).filter(
            AttendanceRecord.date == today_date
        ).scalar() or 0

        # Total students present today
        admin_stats['students_present'] = db.session.query(func.count(db.distinct(AttendanceRecord.user_id)))\
            .join(User, AttendanceRecord.user_id == User.id)\
            .filter(AttendanceRecord.date == today_date, User.role == 'student').scalar() or 0

        # Total faculty/staff present today
        admin_stats['faculty_present'] = db.session.query(func.count(db.distinct(AttendanceRecord.user_id)))\
            .join(User, AttendanceRecord.user_id == User.id)\
            .filter(AttendanceRecord.date == today_date, User.role.in_(['teacher', 'faculty', 'staff'])).scalar() or 0

    # 3. FACULTY ONLY: Fetch branch-specific metrics
    teacher_stats = {}
    if role in ['teacher', 'faculty', 'staff']:

        if current_user.faculty_profile and current_user.faculty_profile.department_info:
            display_name = current_user.faculty_profile.department_info.name
            dept_id = current_user.faculty_profile.department_id
        else:
            display_name = 'General'
            dept_id = None

        teacher_stats['department'] = display_name

        try:
            if dept_id:
                count = db.session.query(func.count(db.distinct(AttendanceRecord.user_id)))\
                    .join(User, AttendanceRecord.user_id == User.id)\
                    .join(Student, User.id == Student.student_id)\
                    .join(Course, Student.course_id == Course.id)\
                    .filter(
                        AttendanceRecord.date == today_date,
                        User.role == 'student',
                        Course.department_id == dept_id
                ).scalar()

                teacher_stats['branch_students_present'] = count or 0
            else:
                teacher_stats['branch_students_present'] = 0

        except Exception as e:
            print(f"Query Error: {e}")
            teacher_stats['branch_students_present'] = 0

        except Exception as e:
            print(f"Query Error: {e}")
            teacher_stats['branch_students_present'] = 0

    # 4. Return everything to the frontend
    return render_template(
        'attendance.html',
        user=current_user,
        my_attendance=my_attendance,
        admin_stats=admin_stats,
        teacher_stats=teacher_stats
    )


@main_bp.route('/attendance-summary')
@login_required
def attendance_summary():
    selected_date = _summary_date(request.args.get('date'))
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all').strip().lower()
    course_id = request.args.get('course_id', 'all').strip()
    per_page = _summary_per_page(request.args.get('per_page'))
    page = max(request.args.get('page', 1, type=int), 1)

    query = _summary_query(selected_date, search, status, course_id)
    total_records = query.count()
    pagination = query.order_by(User.username.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    rows = [_summary_row(*result) for result in pagination.items]

    stats_query = _summary_query(selected_date, search, 'all', course_id)
    total_enrolled = stats_query.with_entities(func.count(User.id)).scalar() or 0
    present_count = stats_query.filter(AttendanceRecord.id.isnot(None)).count()
    absent_count = max(total_enrolled - present_count, 0)
    attendance_rate = round((present_count / total_enrolled) * 100, 1) if total_enrolled else 0

    return render_template(
        'attendance_summary.html',
        user=current_user,
        rows=rows,
        pagination=pagination,
        selected_date=selected_date.isoformat(),
        search=search,
        status=status,
        selected_course_id=course_id,
        per_page=per_page,
        courses=_summary_courses(),
        stats={
            'total_enrolled': total_enrolled,
            'present': present_count,
            'absent': absent_count,
            'rate': attendance_rate,
        },
    )


@main_bp.route('/attendance-summary/export')
@login_required
def export_attendance_summary():
    selected_date = _summary_date(request.args.get('date'))
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all').strip().lower()
    course_id = request.args.get('course_id', 'all').strip()
    rows = [_summary_row(*result) for result in _summary_query(
        selected_date, search, status, course_id
    ).order_by(User.username.asc()).all()]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Roll / ID', 'Student Name', 'Branch', 'Date', 'Time In', 'Time Out',
                     'Verification Method', 'Status', 'Total Hours'])
    for row in rows:
        writer.writerow([
            row['identifier'], row['name'], row['course'], row['date'], row['time_in'],
            row['time_out'], row['verification_method'], row['status'], row['total_hours']
        ])

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = (
        f'attachment; filename=attendance-summary-{selected_date.isoformat()}.csv'
    )
    return response


def _summary_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() if value else date.today()
    except (TypeError, ValueError):
        return date.today()


def _summary_per_page(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 10
    return parsed if parsed in {10, 25, 50, 100} else 10


def _summary_query(selected_date, search='', status='all', course_id='all'):
    role = (current_user.role or 'student').lower()
    query = db.session.query(User, Student, Course, AttendanceRecord).outerjoin(
        Student, Student.student_id == User.id
    ).outerjoin(Course, Course.id == Student.course_id).outerjoin(
        AttendanceRecord,
        (AttendanceRecord.user_id == User.id) & (AttendanceRecord.date == selected_date)
    ).filter(User.role == 'student')

    if role == 'student':
        query = query.filter(User.id == current_user.id)
    elif role in {'teacher', 'faculty', 'staff'}:
        department_id = current_user.faculty_profile.department_id if current_user.faculty_profile else None
        if department_id:
            query = query.filter(Course.department_id == department_id)

    if search:
        term = f'%{search}%'
        query = query.filter(or_(
            Student.full_name.ilike(term),
            Student.roll_no.ilike(term),
            User.username.ilike(term),
        ))

    if course_id != 'all':
        try:
            query = query.filter(Course.id == int(course_id))
        except (TypeError, ValueError):
            query = query.filter(false())

    if status == 'present':
        query = query.filter(AttendanceRecord.id.isnot(None))
    elif status == 'absent':
        query = query.filter(AttendanceRecord.id.is_(None))

    return query


def _summary_courses():
    role = (current_user.role or 'student').lower()
    query = Course.query.order_by(Course.name.asc())
    if role in {'teacher', 'faculty', 'staff'} and current_user.faculty_profile:
        query = query.filter(Course.department_id == current_user.faculty_profile.department_id)
    return query.all()


def _summary_row(user, student, course, record):
    profile = student or user.faculty_profile
    identifier = student.roll_no if student else getattr(profile, 'employee_id', user.username)
    name = student.full_name if student else getattr(profile, 'full_name', user.username)
    return {
        'identifier': identifier,
        'name': name,
        'course': course.name if course else 'N/A',
        'date': record.date.strftime('%d %b %Y') if record else '-',
        'time_in': record.time_in.strftime('%I:%M %p') if record and record.time_in else '-',
        'time_out': record.time_out.strftime('%I:%M %p') if record and record.time_out else '-',
        'verification_method': record.verification_method if record else 'None',
        'status': 'Present' if record else 'Absent',
        'total_hours': f'{record.total_hours:.2f}' if record and record.total_hours is not None else '-',
    }


@main_bp.route('/video_feed')
@login_required
def video_feed():
    """Route that provides the live video stream to the frontend."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ==============================================================================
# API: MARK ATTENDANCE ROUTE
# ==============================================================================


@main_bp.route('/api/mark-attendance', methods=['POST'])
@login_required
def mark_attendance():
    """API endpoint to capture frame, verify face, and save attendance."""
    global global_frame

    data = request.get_json()
    role = data.get('role', '').strip().lower()
    identifier = data.get('user_id', '').strip()  # Roll No or Employee ID

    # 1. Validation Errors (Yellow/Warning)
    if not identifier:
        return jsonify({'status': 'warning', 'title': 'Missing Input', 'message': 'ID Number is required.'})

    if global_frame is None:
        return jsonify({'status': 'danger', 'title': 'Camera Error', 'message': 'Camera is offline. Cannot capture frame.'})

    # 2. Fetch User Profile
    profile = None
    if role == 'student':
        profile = Student.query.filter_by(roll_no=identifier).first()
    elif role in ['teacher', 'faculty', 'staff']:
        profile = FacultyStaff.query.filter_by(employee_id=identifier).first()

    if not profile:
        return jsonify({'status': 'warning', 'title': 'Not Found', 'message': f'No account found with ID {identifier}.'})

    if not profile.encoding_path:
        return jsonify({'status': 'warning', 'title': 'Profile Incomplete', 'message': 'No registered face found for this user.'})

    # 3. Extract Face Encoding from LIVE Camera Frame
    temp_filename = "temp_capture_auth.jpg"
    temp_filepath = os.path.join(current_app.config.get(
        'UPLOAD_FOLDER_FACES', 'static/uploads/faces'), temp_filename)

    # Save the current frame to disk temporarily for the extraction service
    cv2.imwrite(temp_filepath, global_frame)
    live_encoding = extract_face_encoding(temp_filepath)

    # Clean up the temporary file immediately
    if os.path.exists(temp_filepath):
        os.remove(temp_filepath)

    if live_encoding is None:
        return jsonify({'status': 'danger', 'title': 'Face Not Detected', 'message': 'No clear face detected. Please look directly at the camera.'})

    # 4. Load the Saved Database Encoding Safely
    try:
        # Extract just the filename (fixes absolute Windows paths saved in DB)
        encoding_filename = profile.encoding_path.replace(
            '\\', '/').split('/')[-1]

        # Rebuild the correct path dynamically
        encodings_dir = current_app.config.get(
            'UPLOAD_FOLDER_ENCODINGS', 'static/uploads/encodings')
        safe_encoding_path = os.path.join(encodings_dir, encoding_filename)

        # Check if the file actually exists physically
        if not os.path.exists(safe_encoding_path):
            print(f"DEBUG: Missing File! Looked for -> {safe_encoding_path}")
            return jsonify({'status': 'danger', 'title': 'Storage Error', 'message': 'The face data file is missing from the server directory.'})

        # Load the array
        saved_encoding = np.load(safe_encoding_path)

    except Exception as e:
        print(f"DEBUG: Numpy Load Error -> {str(e)}")
        return jsonify({'status': 'danger', 'title': 'Storage Error', 'message': 'Failed to load registered face data.'})

    # 5. Compare the Faces using Euclidean Distance
    distance = np.linalg.norm(saved_encoding - live_encoding)
    threshold = 18.0
    if distance < threshold:
        # -- MATCH FOUND --
        user_account = profile.user_account
        today_date = date.today()
        current_time = datetime.now()
        # Check if they sent the "Yes, I want to leave early" override flag
        confirm_early_out = data.get('confirm_early_out', False)
        # Look for today's existing record
        existing_record = AttendanceRecord.query.filter_by(
            user_id=user_account.id,
            date=today_date
        ).first()

        try:
            # SCENARIO A: First scan of the day -> PUNCH IN
            if not existing_record:
                new_record = AttendanceRecord(
                    user_id=user_account.id,
                    verification_method='Face AI',
                    status='Punched In',
                    marked_by_operator_id=current_user.id,
                    date=today_date,
                    time_in=current_time
                )
                db.session.add(new_record)
                db.session.commit()

                return jsonify({
                    'status': 'success',
                    'title': 'Punched In',
                    'message': f'Good morning, {profile.full_name}! Your check-in is recorded.'
                })
            # SCENARIO B: Second scan of the day -> PUNCH OUT
            elif existing_record and not existing_record.time_out:
                # Calculate hours worked so far
                time_diff = current_time - existing_record.time_in
                hours_worked = time_diff.total_seconds() / 3600.0

                # Prevent accidental double-scans within 5 minutes (0.08 hours)
                if hours_worked < 0.08:
                    return jsonify({
                        'status': 'warning',
                        'title': 'Too Soon',
                        'message': 'You just punched in! Please wait at least 5 minutes before punching out.'
                    })

                # FACULTY/STAFF MANDATORY CHECK: Trigger 8.5hr warning
                if role != 'student' and hours_worked < 8.5 and not confirm_early_out:

                    # 1. Calculate time worked
                    worked_mins_total = int(hours_worked * 60)
                    h = worked_mins_total // 60
                    m = worked_mins_total % 60
                    time_str = f"{h} hrs {m} mins" if h > 0 else f"{m} mins"

                    # 2. Calculate time short (8.5 hours = 510 minutes)
                    short_total = 510 - worked_mins_total
                    short_h = short_total // 60
                    short_m = short_total % 60

                    if short_h > 0:
                        short_str = f"{short_h} hrs {short_m} mins"
                    else:
                        short_str = f"{short_m} mins"

                    return jsonify({
                        'status': 'confirm',
                        'title': 'Confirm Punch-Out',
                        'message': f'You have completed {time_str} today, which is {short_str} short of the standard 8.5 working hours.\n\nDo you want to punch out now?'
                    })

                # ========================================================
                # IF WARNING IS BYPASSED / CONFIRMED, PROCEED WITH CHECKOUT
                # ========================================================
                existing_record.time_out = current_time
                existing_record.total_hours = round(hours_worked, 2)
                existing_record.status = 'Completed'
                db.session.commit()

                return jsonify({
                    'status': 'success',
                    'title': 'Punched Out',
                    'message': f'Goodbye, {profile.full_name}! You logged {existing_record.total_hours} hours today.'
                })

            # SCENARIO C: Third scan of the day -> ALREADY DONE
            else:
                return jsonify({
                    'status': 'warning',
                    'title': 'Already Marked',
                    'message': f'Attendance for {profile.full_name} is already marked for today. you cannot punch in/out again until tomorrow.'
                })

        except Exception as e:
            db.session.rollback()
            print(f"Database Error: {e}")
            return jsonify({'status': 'danger', 'title': 'Database Error', 'message': 'Error while saving attendance.'})

    else:
        # -- NO MATCH --
        return jsonify({'status': 'danger', 'title': 'Verification Failed', 'message': 'Face mismatch. You do not match the registered user for this ID.'})


# ==============================================================================
# PROFILE ROUTE
# ==============================================================================

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # Determine the correct profile table based on user role
    if current_user.role == 'student':
        user_profile = current_user.student_profile
    else:
        user_profile = current_user.faculty_profile

    if request.method == 'POST':
        try:
            # Update editable fields from the form
            user_profile.mobile_no = request.form.get('mobile_no', '').strip()
            user_profile.father_name = request.form.get(
                'father_name', '').strip()
            user_profile.mother_name = request.form.get(
                'mother_name', '').strip()
            user_profile.address = request.form.get('address', '').strip()
            user_profile.city = request.form.get('city', '').strip()
            user_profile.state = request.form.get('state', '').strip()
            user_profile.pin_code = request.form.get('pin_code', '').strip()

            db.session.commit()
            flash('Your profile has been successfully updated.', 'success')
            return redirect(url_for('main.profile'))

        except SQLAlchemyError as err:
            db.session.rollback()
            flash('Database error occurred while updating profile.', 'danger')
            print(f"Profile Update Error: {err}")

    # Render template on GET request
    return render_template('profile.html', user=current_user)


# ==============================================================================
# CHANGE PASSWORD ROUTE
# ==============================================================================

@main_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per minute", key_func=lambda: request.remote_addr)
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Basic Validation
        if not current_password or not new_password or not confirm_password:
            flash('All fields are required.', 'warning')
            return redirect(url_for('main.change_password'))

        # Verify new passwords match
        if new_password != confirm_password:
            flash('New passwords do not match. Please try again.', 'danger')
            return redirect(url_for('main.change_password'))

        # Verify current password is correct (Updated to password_hash)
        if not check_password_hash(current_user.password_hash, current_password):
            flash('The current password you entered is incorrect.', 'danger')
            return redirect(url_for('main.change_password'))

        # Prevent reusing the same password (Updated to password_hash)
        if check_password_hash(current_user.password_hash, new_password):
            flash(
                'Your new password must be different from your current password.', 'warning')
            return redirect(url_for('main.change_password'))

        # Update and hash the new password (Updated to password_hash)
        try:
            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash(
                'Your password has been successfully updated! Please use it for future logins.', 'success')
            # Redirect to profile on success
            return redirect(url_for('main.attendance'))

        except Exception as e:
            db.session.rollback()
            flash('A database error occurred. Please try again.', 'danger')
            print(f"Password Change Error: {e}")

    return render_template('change_password.html')


# ==============================================================================
# system setting
# ==============================================================================

@main_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def system_settings():
    role = current_user.role.lower() if current_user.role else 'student'

    current_settings = {
        'ai_threshold': 18.0,
        'camera_source': '0',
        'shift_duration': 8.5,
        'cooldown_mins': 5,
        'session_timeout': 10,
        'maintenance_mode': False,
        'email_notifications': True,
        'theme_preference': 'dark'
    }

    if request.method == 'POST':
        if role == 'student':
            flash('Permission Denied: Students cannot modify system settings.', 'danger')
            return redirect(url_for('main.system_settings'))

        current_settings.update({
            'ai_threshold': float(request.form.get('ai_threshold', current_settings['ai_threshold'])),
            'camera_source': request.form.get('camera_source', current_settings['camera_source']),
            'shift_duration': float(request.form.get('shift_duration', current_settings['shift_duration'])),
            'cooldown_mins': int(request.form.get('cooldown_mins', current_settings['cooldown_mins'])),
            'session_timeout': int(request.form.get('session_timeout', current_settings['session_timeout'])),
            'maintenance_mode': request.form.get('maintenance_mode') == 'on',
            'email_notifications': request.form.get('email_notifications') == 'on',
            'theme_preference': request.form.get('theme_preference', current_settings['theme_preference'])
        })

        flash('Settings have been successfully updated.', 'success')
        return render_template('system_settings.html', settings=current_settings, role=role)

    return render_template('system_settings.html', settings=current_settings, role=role)

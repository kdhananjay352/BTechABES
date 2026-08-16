import os
import cv2
import numpy as np
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, request, Response, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import User, Student, FacultyStaff, AttendanceRecord, Course, Department

# Import your existing custom face detection service
from services.face_detection import extract_face_encoding

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
    return render_template('attendance_summary.html', user=current_user)


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
#           SCENARIO B: Second scan of the day -> PUNCH OUT
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
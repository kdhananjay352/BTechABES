import os
import cv2
import numpy as np
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, request, Response, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import User, Student, FacultyStaff, AttendanceRecord

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
    return render_template('attendance.html', user=current_user)

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
    identifier = data.get('user_id', '').strip() # Roll No or Employee ID

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
    temp_filepath = os.path.join(current_app.config.get('UPLOAD_FOLDER_FACES', 'static/uploads/faces'), temp_filename)
    
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
        encoding_filename = profile.encoding_path.replace('\\', '/').split('/')[-1]
        
        # Rebuild the correct path dynamically
        encodings_dir = current_app.config.get('UPLOAD_FOLDER_ENCODINGS', 'static/uploads/encodings')
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
    
    # THIS IS THE CRITICAL CHANGE! Matches your model's 14.xxx scale
    threshold = 18.0  
    
    if distance < threshold:
        # -- MATCH FOUND --
        user_account = profile.user_account
        today_date = date.today()
        
        # Prevent double-marking for the day
        existing_record = AttendanceRecord.query.filter(
            AttendanceRecord.user_id == user_account.id,
            func.date(AttendanceRecord.timestamp) == today_date
        ).first()

        # Already Marked (Blue/Info)
        if existing_record:
            return jsonify({
                'status': 'warning', 
                'title': 'Already Marked',
                'message': f'Attendance for {profile.full_name} is already marked for today.'
            })

        # Save new Attendance Record (Green/Success)
        try:
            new_record = AttendanceRecord(
                user_id=user_account.id,
                verification_method='Face AI',
                status='Present',
                marked_by_operator_id=current_user.id
            )
            db.session.add(new_record)
            db.session.commit()
            
            return jsonify({
                'status': 'success', 
                'title': 'Attendance Recorded',
                'message': f'Face verified! Attendance recorded for {profile.full_name}.'
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'status': 'danger', 'title': 'Database Error', 'message': 'Error while saving attendance.'})
            
    else:
        # -- NO MATCH (Red/Danger) --
        print(f"Failed Match Distance: {distance}")
        return jsonify({'status': 'danger', 'title': 'Verification Failed', 'message': 'Face mismatch. You do not match the registered user for this ID.'})
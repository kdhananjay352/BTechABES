from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager

# ==============================================================================
# 1. CORE AUTHENTICATION USER MODEL
# ==============================================================================
class User(UserMixin, db.Model):
    """Core authentication user model."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # 'student', 'faculty', 'staff', 'admin'
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    password_updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships (1-to-1 with Profile entities)
    student_profile = db.relationship(
        'Student', backref='user_account', uselist=False, cascade="all, delete-orphan")
    faculty_profile = db.relationship(
        'FacultyStaff', backref='user_account', uselist=False, cascade="all, delete-orphan")

    # Relationships for Attendance Records
    attendance_records = db.relationship(
        'AttendanceRecord', foreign_keys='AttendanceRecord.user_id', backref='student_user', lazy=True)
    operator_logs = db.relationship(
        'AttendanceRecord', foreign_keys='AttendanceRecord.marked_by_operator_id', backref='operator_user', lazy=True)

    def set_password(self, password):
        """Hash and set the user password."""
        self.password_hash = generate_password_hash(password)
        self.password_updated_at = datetime.utcnow()

    def check_password(self, password):
        """Check if the provided password matches the user's password."""
        return check_password_hash(self.password_hash, password)


# ==============================================================================
# 2. REFERENCE TABLES (Departments & Courses)
# ==============================================================================
class Department(db.Model):
    """Department model for standardizing faculty departments and course groupings."""
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # Relationships
    courses = db.relationship('Course', backref='department', lazy=True, cascade="all, delete-orphan")
    faculty_members = db.relationship('FacultyStaff', backref='department_info', lazy=True)


class Course(db.Model):
    """Course model for standardizing student branches and admission types."""
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "B.Tech - CSE"
    course_type = db.Column(db.String(50), nullable=False)  # e.g., "Regular", "Lateral Entry"
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    
    # Relationships
    students = db.relationship('Student', backref='course_info', lazy=True)


# ==============================================================================
# 3. STUDENT PROFILE ENTITY
# ==============================================================================
class Student(db.Model):
    """Student profile model for storing student information."""
    __tablename__ = 'students'

    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    roll_no = db.Column(db.String(50), unique=True, nullable=False)
    admission_no = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(15), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    
    # Replaced 'branch' string with a Foreign Key to the Course table
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    
    session = db.Column(db.String(20), nullable=False)
    mobile_no = db.Column(db.String(15), nullable=False)
    father_name = db.Column(db.String(100), nullable=False)
    mother_name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    address = db.Column(db.Text, nullable=False)
    last_qualification = db.Column(db.String(100), nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)
    encoding_path = db.Column(db.String(255), nullable=True)


# ==============================================================================
# 4. FACULTY & STAFF PROFILE ENTITY
# ==============================================================================
class FacultyStaff(db.Model):
    """FacultyStaff model for storing faculty staff information."""
    __tablename__ = 'faculty_staff'

    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(15), nullable=False)
    dob = db.Column(db.Date, nullable=False)
    
    # Replaced 'department' string with a Foreign Key to the Department table
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    
    designation = db.Column(db.String(100), nullable=False)
    mobile_no = db.Column(db.String(15), nullable=False)
    father_name = db.Column(db.String(100), nullable=False)
    mother_name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    address = db.Column(db.Text, nullable=False)
    qualification = db.Column(db.String(100), nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)
    encoding_path = db.Column(db.String(255), nullable=True)


# ==============================================================================
# 5. ATTENDANCE RECORD ENTITY
# ==============================================================================
class AttendanceRecord(db.Model):
    """Attendance record model for storing time-in/time-out attendance information."""
    __tablename__ = 'attendance_records'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    verification_method = db.Column(db.String(50), default='Face AI')
    status = db.Column(db.String(50), default='Present')
    marked_by_operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    date = db.Column(db.Date, default=date.today)
    time_in = db.Column(db.DateTime, default=datetime.now)
    time_out = db.Column(db.DateTime, nullable=True)
    total_hours = db.Column(db.Float, nullable=True)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    return User.query.get(int(user_id))
import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, Response, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import User, Student, FacultyStaff, AttendanceRecord

main_bp = Blueprint('main', __name__)


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

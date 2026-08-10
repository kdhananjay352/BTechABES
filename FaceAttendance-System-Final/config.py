import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Configuration class for Face Attendance System."""

    SECRET_KEY = os.environ.get(
        'SECRET_KEY', 'smart-attendance-system-secret-key-2026')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + \
        os.path.join(BASE_DIR, 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload directories
    UPLOAD_FOLDER_FACES = os.path.join(BASE_DIR, 'static', 'uploads', 'faces')
    UPLOAD_FOLDER_ENCODINGS = os.path.join(
        BASE_DIR, 'static', 'uploads', 'encodings')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

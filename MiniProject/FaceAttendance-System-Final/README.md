# Smart Face Recognition Attendance System

A Flask-based attendance platform for student and faculty/staff profiles, face-based verification, live camera capture, attendance logs, filtering, pagination, CSV export, and role-aware settings.

## Core Features

- Role-based login and registration for students, faculty, and staff.
- Admin-controlled AI and attendance configuration.
- Profile photo capture and InsightFace embedding generation.
- Live OpenCV camera stream through an MJPEG endpoint.
- Face verification before punch-in and punch-out.
- One attendance record per user per date.
- Attendance summary with date, course, status, and student search filters.
- Server-side pagination and CSV export.
- Persistent system settings with per-user camera selection.
- Responsive Bootstrap-based interface with light/dark theme support.

## Technology Stack

| Layer           | Technology                                                                           |
| --------------- | ------------------------------------------------------------------------------------ |
| Frontend        | HTML, CSS, Bootstrap 5, JavaScript, Font Awesome                                     |
| Backend         | Python 3, Flask, Flask-Login, Flask-WTF                                              |
| Database        | SQLite with SQLAlchemy ORM                                                           |
| Computer vision | OpenCV and InsightFace with ONNX Runtime                                             |
| Security        | Werkzeug password hashing, CSRF protection, signed timed reset tokens, rate limiting |

## Project Structure

```text
FaceAttendance-System-Final/
├── app.py                         # Flask application factory and startup
├── config.py                      # Environment and upload configuration
├── extensions.py                  # Database, login, CSRF, and limiter instances
├── models.py                      # SQLAlchemy entities
├── rate_limiter.py                # Rate-limit configuration
├── seed_db.py                     # Reference data/database seeding
├── requirements.txt               # Python dependencies
├── routes/
│   ├── auth.py                    # Login, registration, reset, logout
│   └── main.py                    # Attendance, camera, profiles, settings, reports
├── services/
│   └── face_detection.py          # InsightFace extraction and comparison helpers
├── static/
│   ├── css/                       # Bootstrap and application styles
│   ├── js/                        # Bootstrap and shared JavaScript
│   └── uploads/
│       ├── faces/                 # Reference face photographs
│       └── encodings/             # Saved NumPy embeddings
└── templates/                     # Jinja2 HTML pages and components
```

## Setup

Create or activate the project virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure `SECRET_KEY` before startup

The application intentionally refuses to start without an explicit secret key. Generate one in the same terminal session:

```bash|MacBook|Linux
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

Powershell:
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
Verify:
$env:SECRET_KEY

Command Prompt:
for /f %i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set SECRET_KEY=%i

Check that it is available without printing the secret itself:

```bash
python -c 'import os; print("SECRET_KEY configured:", bool(os.environ.get("SECRET_KEY")))'
```

The exported value lasts until the terminal session ends. For local development, place it in a private `.env` or shell profile that is excluded from Git. Never commit the value.

## Initialize and Run

```bash
python seed_db.py
python app.py
```

Open `http://127.0.0.1:8080` in a browser.

InsightFace may download or require the `buffalo_l` model on first use. The camera and face verification features also require an accessible camera and the corresponding OpenCV/ONNX runtime dependencies.

## Main Routes

| Route                        | Purpose                                         |
| ---------------------------- | ----------------------------------------------- |
| `/login`                     | Authenticate a user                             |
| `/register`                  | Create a student/faculty/staff account          |
| `/attendance`                | Attendance terminal and live camera page        |
| `/video_feed`                | Authenticated MJPEG camera stream               |
| `/api/mark-attendance`       | Verify the current user and record punch-in/out |
| `/attendance-summary`        | Filtered, paginated attendance report           |
| `/attendance-summary/export` | CSV report download                             |
| `/profile`                   | Edit personal profile data                      |
| `/change-password`           | Change the authenticated user's password        |
| `/settings`                  | Role-aware system and personal settings         |

## Documentation

- [Project Documentation](PROJECT_DOCUMENTATION.md): architecture, database schema, diagrams, workflows, and deployment notes.
- [Project Report](PROJECT_REPORT.md): synopsis and academic report structure.
- [Implementation Plan](IMPLEMENTATION_PLAN.md): original implementation roadmap.
- [Updated Notes](readme_updated.md): earlier schema and design notes retained for reference.

## Important Development Notes

- Existing SQLite databases may need a migration for the unique attendance constraint and the `system_settings` table. `db.create_all()` does not alter existing tables.
- Face matching uses cosine similarity. The admin threshold is expected to be between `0` and `1`; values above `1` fall back to the default `0.4`.
- The application stores face photographs and NumPy embeddings locally. Production deployments should use protected storage, backups, access controls, and a documented biometric retention policy.
- No automated test suite is currently included. Add route, authorization, database, and face-comparison tests before production deployment.

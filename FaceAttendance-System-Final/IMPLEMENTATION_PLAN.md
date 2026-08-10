# Smart Face Recognition Attendance System

## Step-by-Step Backend & Engine Implementation Guide

---

## Roadmap Overview

## [Step 1: Registration & Profiles] ──► [Step 2: Face Encoding Engine] ──► [Step 3: Live Video Stream & AI Terminal] ──► [Step 4: Attendance Summary & CSV Export]

## Step 1: Role-Based Registration & Profile Creation

### Objectives

- Implement dynamic frontend role switching (Student vs. Faculty/Staff).
- Process multi-part registration requests (`User` + `Student` or `FacultyStaff`).
- Handle face photo upload storage in `static/uploads/faces/`.

### Deliverables

1. **`templates/register.html`**: Form with dynamic JS section toggles and file input.
2. **`routes/auth.py`**: Processing logic using database transactions (`db.session.flush()`).

---

## Step 2: Facial Recognition Encoding Pipeline

### Objectives

- Extract 128-dimensional facial feature encodings from uploaded reference photos upon registration.
- Store face encodings securely (as `.npy` binary vector files or serialized arrays in DB).
- Create a reusable encoding loader service to keep active embeddings in memory for fast lookup.

### Deliverables

1. **`services/face_service.py`**:
   - `extract_face_encoding(image_path)`
   - `save_encoding(user_id, encoding)`
   - `load_all_encodings()`

---

## Step 3: Live Camera Stream & Real-Time Terminal

### Objectives

- Initialize webcam stream via OpenCV (`cv2.VideoCapture`).
- Process incoming frames: detect faces, generate frame encodings, and compute Euclidean distance against saved encodings.
- Draw visual bounding boxes:
  - **Green Box + Name**: Matched user (Mark Attendance).
  - **Red Box + "Unknown"**: Unrecognized person.
- Prevent duplicate marking for the same user within the same calendar date.
- Stream live annotated frames to `attendance.html` via MJPEG `/video_feed`.

### Deliverables

1. **`camera.py`**: OpenCV video camera generator class.
2. **`routes/main.py`**: `/video_feed` endpoint & live recognition logging route.

---

## Step 4: Attendance Summary, Filtering & CSV Export

### Objectives

- Query `AttendanceRecord` table joined with `User`, `Student`, and `FacultyStaff`.
- Implement dynamic filtering by:
  - Date (`YYYY-MM-DD`)
  - Course / Branch / Department
  - Attendance Status (`Present` / `Absent`)
  - Search query (Name / Roll No / Employee ID)
- Add server-side pagination with dynamic page-size limits (`10`, `25`, `50`, `100`).
- Build direct CSV export functionality using Python's `csv` module.

### Deliverables

1. **`routes/main.py`**:
   - `/attendance-summary` (Paginated filter route)
   - `/export-csv` (Downloadable CSV generator endpoint)
2. **`templates/attendance_summary.html`**: Dynamic Jinja loop binding and filter controls.

---

## Verification & Testing Checklist

- [ ] **Database Integrity**: Registering a student creates records in `users` and `students` tables; registering faculty creates records in `users` and `faculty_staff`.
- [ ] **Face Extraction**: Photo uploads properly produce facial encoding files without throwing face detection errors.
- [ ] **Live Terminal**: Web camera initializes on `/attendance` and accurately highlights recognized faces in green with the user's name.
- [ ] **Duplicate Guard**: Scanning the same person twice in one day logs only one `Present` status entry in `attendance_records`.
- [ ] **Summary & Export**: Attendance logs display correctly with student details and download cleanly as a `.csv` file.

from app import app # Adjust this import if your main flask instance is named differently
from extensions import db
from models import Department, Course

def seed_database():
    with app.app_context():
        # 1. Check if data already exists to prevent duplicates
        if Department.query.first():
            print("Database is already seeded!")
            return

        print("Seeding Departments...")
        
        # 2. Create Departments
        dept_cse = Department(name="Computer Science")
        dept_ece = Department(name="Electronics & Communication")
        dept_me = Department(name="Mechanical Engineering")
        dept_admin = Department(name="Administration")

        db.session.add_all([dept_cse, dept_ece, dept_me, dept_admin])
        db.session.commit() # Commit to generate the IDs

        print("Seeding Courses...")

        # 3. Create Courses and link them to their respective Departments
        courses = [
            Course(name="B.Tech - CSE", course_type="4 Years", department_id=dept_cse.id),
            Course(name="B.Tech - CSE Lateral", course_type="3 Years", department_id=dept_cse.id),
            Course(name="MCA", course_type="2 Years", department_id=dept_cse.id),
            Course(name="BCA", course_type="3 Years", department_id=dept_cse.id),
            Course(name="M.Tech - CSE", course_type="2 Years", department_id=dept_cse.id),
            
            Course(name="B.Tech - ECE", course_type="4 Years", department_id=dept_ece.id),
            
            Course(name="B.Tech - ME", course_type="4 Years", department_id=dept_me.id),
        ]

        db.session.add_all(courses)
        db.session.commit()

        print("Successfully seeded the database with Departments and Courses!")

if __name__ == "__main__":
    seed_database()
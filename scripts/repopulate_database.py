"""scripts/repopulate_database.py
Clears and repopulates the RESN PostgreSQL database with diverse, realistic rural Indian educational cases.
Covers:
- Extreme Danger (Child labor, migrant kilns, sibling dropouts, extreme poverty)
- Danger (Female domestic caretaking, distance barriers, sudden family crisis)
- Watch (Academic cliff edges, seasonal harvest dips, language barriers)
- Normal / Resilient (High attendance, high scores, financial aid matching)
"""

import os
import sys
from datetime import date, timedelta
from dotenv import load_dotenv

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from db_connector import run_query
from memory.pg_vector import PGVectorMemory

def repopulate():
    print("🧹 Cleaning existing database tables...")
    
    # Clean dependent tables first
    cleanup_sql = """
        TRUNCATE TABLE agent_memory, interventions, exam_scores, attendance, social_risk, students RESTART IDENTITY CASCADE;
    """
    run_query(cleanup_sql, is_write=True)
    print("✅ Existing student and memory tables cleared.")

    # 1. Insert Diverse Student Profiles
    print("🌱 Inserting 10 comprehensive student profiles...")
    students_data = [
        # 1: Extreme Danger (Child labor & Brick Kiln Migration)
        ("Ramesh Soren", "Male", "ST", 18000, 9, 15, 6, 4, 11.5, "Hindi", "Daily Wage Labor", "Rural"),
        # 2: Danger (Female domestic caretaking & academic collapse)
        ("Kavita Kumari", "Female", "SC", 24000, 10, 16, 7, 5, 8.0, "Hindi", "Farming", "Rural"),
        # 3: Watch (Academic cliff edge - high income but failing STEM)
        ("Aarav Sharma", "Male", "General", 95000, 10, 15, 4, 1, 2.0, "Hindi", "Shopkeeper", "Semi-Urban"),
        # 4: Watch (Extreme distance & seasonal river terrain)
        ("Sunita Murmu", "Female", "ST", 42000, 8, 14, 5, 3, 9.5, "Hindi", "Farming", "Rural"),
        # 5: Low-income high-potential (Needs minority scholarship)
        ("Mohammed Zeeshan", "Male", "Minority", 22000, 9, 14, 6, 3, 3.0, "Hindi", "Carpentry", "Rural"),
        # 6: Normal (Benchmark resilient top-performer)
        ("Ananya Sen", "Female", "General", 120000, 10, 15, 4, 1, 1.5, "Bengali", "Teacher", "Semi-Urban"),
        # 7: Danger (Parental bereavement - PM CARES eligible)
        ("Vikas Kumar", "Male", "SC", 14000, 7, 13, 3, 2, 4.0, "Hindi", "None", "Rural"),
        # 8: Watch (Seasonal harvest labor & Girls STEM candidate)
        ("Meera Patel", "Female", "OBC", 55000, 11, 17, 5, 2, 4.5, "Hindi", "Farming", "Rural"),
        # 9: Danger (Older sibling dropouts setting precedent)
        ("Deepak Baitha", "Male", "SC", 30000, 8, 14, 6, 4, 5.0, "Hindi", "Daily Wage Labor", "Rural"),
        # 10: Watch (Interstate migrant with language disconnect)
        ("Pooja Mondal", "Female", "General", 36000, 9, 15, 5, 2, 3.5, "Bengali", "Construction Labor", "Semi-Urban")
    ]

    insert_student_sql = """
        INSERT INTO students 
        (name, gender, caste_category, annual_income, grade, age, hh_size, hh_children, school_distanceKm, home_language, hh_occupation, location_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING student_id;
    """
    
    student_ids = []
    for s in students_data:
        res = run_query(insert_student_sql, s, is_write=True, return_dict=True)
        # res could be list of dicts or affected count
        # Let's query student_id by name if not returned directly
        sid_row = run_query("SELECT student_id FROM students WHERE name = %s", (s[0],), return_dict=True)
        student_ids.append(sid_row[0]['student_id'])

    print(f"✅ Created {len(student_ids)} students with IDs: {student_ids}")

    # 2. Insert Social Risk Factors
    print("📊 Populating social risk indicators...")
    social_risks = [
        # sid, seasonal_labor, sibling_dropout, migrant_family, childcare_resp, parent_edu
        (student_ids[0], True, True, True, False, "None"),        # Ramesh: Extreme
        (student_ids[1], False, True, False, True, "None"),        # Kavita: Caretaker + Sibling
        (student_ids[2], False, False, False, False, "Secondary"), # Aarav: Safe socio-economic
        (student_ids[3], True, False, False, False, "Primary"),    # Sunita: Distance/seasonal
        (student_ids[4], False, False, False, False, "None"),       # Zeeshan: Low income only
        (student_ids[5], False, False, False, False, "Graduate"),   # Ananya: Highly supportive
        (student_ids[6], False, False, False, True, "None"),       # Vikas: Orphan crisis
        (student_ids[7], True, False, False, False, "Primary"),    # Meera: Harvest helper
        (student_ids[8], False, True, False, False, "None"),       # Deepak: Multi-sibling dropout
        (student_ids[9], False, False, True, False, "Primary")     # Pooja: Migrant family
    ]

    insert_social_sql = """
        INSERT INTO social_risk
        (student_id, seasonal_labor, sibling_dropout, migrant_family, childcare_responsibility, parent_education_level)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    for sr in social_risks:
        run_query(insert_social_sql, sr, is_write=True)

    # 3. Insert Longitudinal Attendance Records (Last 3 months)
    print("📅 Populating attendance histories...")
    attendance_records = [
        # (sid, month, pct)
        # Ramesh: Severe collapse
        (student_ids[0], "2026-08-01", 62.0), (student_ids[0], "2026-09-01", 48.0), (student_ids[0], "2026-10-01", 38.5),
        # Kavita: Drop from 75 to 50
        (student_ids[1], "2026-08-01", 74.0), (student_ids[1], "2026-09-01", 61.0), (student_ids[1], "2026-10-01", 51.0),
        # Aarav: Consistent 82%
        (student_ids[2], "2026-08-01", 85.0), (student_ids[2], "2026-09-01", 83.0), (student_ids[2], "2026-10-01", 81.5),
        # Sunita: Drop during heavy rains
        (student_ids[3], "2026-08-01", 88.0), (student_ids[3], "2026-09-01", 76.0), (student_ids[3], "2026-10-01", 69.0),
        # Zeeshan: Good attendance 88%
        (student_ids[4], "2026-08-01", 90.0), (student_ids[4], "2026-09-01", 88.0), (student_ids[4], "2026-10-01", 87.0),
        # Ananya: High attendance 96%
        (student_ids[5], "2026-08-01", 98.0), (student_ids[5], "2026-09-01", 95.0), (student_ids[5], "2026-10-01", 96.5),
        # Vikas: Sharp drop after bereavement
        (student_ids[6], "2026-08-01", 80.0), (student_ids[6], "2026-09-01", 58.0), (student_ids[6], "2026-10-01", 52.0),
        # Meera: Seasonal harvest drop in Oct
        (student_ids[7], "2026-08-01", 86.0), (student_ids[7], "2026-09-01", 84.0), (student_ids[7], "2026-10-01", 72.0),
        # Deepak: Chronic low 60%
        (student_ids[8], "2026-08-01", 65.0), (student_ids[8], "2026-09-01", 62.0), (student_ids[8], "2026-10-01", 59.0),
        # Pooja: Moderate 78%
        (student_ids[9], "2026-08-01", 82.0), (student_ids[9], "2026-09-01", 79.0), (student_ids[9], "2026-10-01", 77.0),
    ]
    insert_att_sql = "INSERT INTO attendance (student_id, month, attendance_percent) VALUES (%s, %s, %s);"
    for att in attendance_records:
        run_query(insert_att_sql, att, is_write=True)

    # 4. Insert Academic Exam Scores
    print("📝 Populating academic exam performance...")
    exam_records = [
        # Ramesh: Failing grades across Math & Science
        (student_ids[0], "Mathematics", "2026-10-10", 24.0), (student_ids[0], "Mathematics", "2026-07-15", 38.0),
        (student_ids[0], "Science", "2026-10-12", 28.0), (student_ids[0], "Hindi", "2026-10-14", 45.0),
        
        # Kavita: Math plummeted from 68 to 29
        (student_ids[1], "Mathematics", "2026-10-10", 29.0), (student_ids[1], "Mathematics", "2026-07-15", 68.0),
        (student_ids[1], "Social Studies", "2026-10-12", 42.0),
        
        # Aarav: Academic cliff - Math plummeted from 78 to 33
        (student_ids[2], "Mathematics", "2026-10-10", 33.0), (student_ids[2], "Mathematics", "2026-07-15", 78.0),
        (student_ids[2], "Science", "2026-10-12", 41.0), (student_ids[2], "Science", "2026-07-15", 74.0),
        
        # Sunita: Borderline scores
        (student_ids[3], "Mathematics", "2026-10-10", 45.0), (student_ids[3], "Science", "2026-10-12", 48.0),
        
        # Zeeshan: Good scores 64%
        (student_ids[4], "Mathematics", "2026-10-10", 64.0), (student_ids[4], "Science", "2026-10-12", 67.0),
        
        # Ananya: High distinction 89%
        (student_ids[5], "Mathematics", "2026-10-10", 91.0), (student_ids[5], "Science", "2026-10-12", 87.0),
        
        # Vikas: Grade drop after bereavement
        (student_ids[6], "Mathematics", "2026-10-10", 31.0), (student_ids[6], "Mathematics", "2026-07-15", 58.0),
        
        # Meera: Strong in Biology/Science, struggling in Physics Math
        (student_ids[7], "Science", "2026-10-10", 72.0), (student_ids[7], "Mathematics", "2026-10-12", 48.0),
        
        # Deepak: Low passing 36%
        (student_ids[8], "Mathematics", "2026-10-10", 36.0), (student_ids[8], "Social Studies", "2026-10-12", 40.0),
        
        # Pooja: Language friction in Hindi/Social Science
        (student_ids[9], "Hindi", "2026-10-10", 38.0), (student_ids[9], "Mathematics", "2026-10-12", 55.0)
    ]
    insert_exam_sql = "INSERT INTO exam_scores (student_id, subject, exam_date, score) VALUES (%s, %s, %s, %s);"
    for ex in exam_records:
        run_query(insert_exam_sql, ex, is_write=True)

    # 5. Populate Semantic Episodic Memories (with Embeddings)
    print("🧠 Generating episodic memory embeddings for hybrid retrieval...")
    memory_engine = PGVectorMemory()
    memories_to_add = [
        (student_ids[0], "Student absent for 3 consecutive weeks during monsoon sowing. Family migrated to district brick kiln. Multiple elder siblings never completed primary schooling.", {"status": "DANGER", "score": 92, "grade": 9, "location": "Rural"}),
        (student_ids[1], "Mother bedridden; student tasked with full-time childcare and cooking. Severe drop in homework completion and math performance.", {"status": "DANGER", "score": 86, "grade": 10, "location": "Rural"}),
        (student_ids[2], "Severe conceptual struggle in quadratic equations and trigonometry. Attendance remains regular; parents actively seeking tutoring support.", {"status": "WATCH", "score": 45, "grade": 10, "location": "Semi-Urban"}),
        (student_ids[3], "River crossing becomes impassable in heavy rain. Long 9.5 km commute causing chronic physical exhaustion and late arrivals.", {"status": "WATCH", "score": 58, "grade": 8, "location": "Rural"}),
        (student_ids[4], "High academic motivation despite father's daily wage carpenter income. Extremely diligent in class; eligible for minority financial assistance.", {"status": "NORMAL", "score": 28, "grade": 9, "location": "Rural"}),
        (student_ids[6], "Father passed away suddenly; family lost primary breadwinner. Child struggling with grief and potential withdrawal to earn daily wages.", {"status": "DANGER", "score": 89, "grade": 7, "location": "Rural"}),
        (student_ids[8], "Two elder brothers dropped out at age 14 to work in transport hubs. Father believes eighth grade is sufficient literacy for manual work.", {"status": "DANGER", "score": 81, "grade": 8, "location": "Rural"})
    ]

    for sid, summary, meta in memories_to_add:
        try:
            memory_engine.add_memory(sid, summary, meta)
            print(f"  ✓ Embedded memory for Student ID {sid}")
        except Exception as e:
            print(f"  Notice: Embedding skipped for ID {sid}: {e}")

    # 6. Verify and Print Summary Statistics
    counts = run_query("""
        SELECT 
            (SELECT COUNT(*) FROM students) as students_count,
            (SELECT COUNT(*) FROM social_risk) as risk_count,
            (SELECT COUNT(*) FROM attendance) as att_count,
            (SELECT COUNT(*) FROM exam_scores) as exam_count,
            (SELECT COUNT(*) FROM schemes) as schemes_count,
            (SELECT COUNT(*) FROM agent_memory) as memory_count;
    """, return_dict=True)

    print("\n🎉 Database Repopulation Complete!")
    print(f"Summary Counts: {counts[0]}")

if __name__ == "__main__":
    repopulate()

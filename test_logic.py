import logging
import warnings
# Make sure db_connector actually has init_db!
from db_connector import run_query, init_db 
from utils import DropoutInterventionSystem

# Suppress "FutureWarning" from Google AI to keep output clean
warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def setup_test_data():
    """Resets the database to a known state for testing."""
    print("⚙️  Resetting Test Data in Database...")
    
    # --- 1. SETUP RAJU (ID 1) -> HIGH RISK ---
    # CRITICAL FIX: Delete CHILDREN first (Risk, Scores, Attendance)
    run_query("DELETE FROM social_risk WHERE student_id = 1")
    run_query("DELETE FROM exam_scores WHERE student_id = 1")
    run_query("DELETE FROM attendance WHERE student_id = 1")
    
    # THEN delete PARENT (Student)
    run_query("DELETE FROM students WHERE student_id = 1")
    
    # Now we can insert fresh data
    run_query("INSERT INTO students (student_id, name, gender, caste_category, annual_income, grade) VALUES (1, 'Raju', 'Male', 'OBC', 45000, 9)")
    run_query("INSERT INTO attendance (student_id, month, attendance_percent) VALUES (1, CURRENT_DATE, 60)")
    run_query("INSERT INTO social_risk (student_id, seasonal_labor, parent_education_level, sibling_dropout) VALUES (1, TRUE, 'None', TRUE)")
    run_query("INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES (1, 'Math', 85, CURRENT_DATE - INTERVAL '4 months')")
    run_query("INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES (1, 'Math', 40, CURRENT_DATE - INTERVAL '1 month')")

    # --- 2. SETUP AMIT (ID 3) -> ACADEMIC WATCH ---
    # Delete Children first
    run_query("DELETE FROM social_risk WHERE student_id = 3")
    run_query("DELETE FROM exam_scores WHERE student_id = 3")
    run_query("DELETE FROM attendance WHERE student_id = 3")
    
    # Delete Parent
    run_query("DELETE FROM students WHERE student_id = 3")
    
    # Insert fresh data
    run_query("INSERT INTO students (student_id, name, gender, caste_category, annual_income, grade) VALUES (3, 'Amit', 'Male', 'General', 600000, 10)")
    run_query("INSERT INTO attendance (student_id, month, attendance_percent) VALUES (3, CURRENT_DATE, 95)")
    # (No social risk for Amit, so we skip inserting it)
    run_query("INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES (3, 'Math', 60, CURRENT_DATE - INTERVAL '4 months')")
    run_query("INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES (3, 'Math', 45, CURRENT_DATE)")
def run_tests():
    system = DropoutInterventionSystem()
    
    # --- TEST CASE 1 ---
    print("\n" + "="*60)
    print("🚨 TEST 1: RAJU (High Risk -> Script + PDF)")
    print("="*60)
    
    report_raju = system.process_intervention(student_id=1, target_language="English")
    print(f"📊 STATUS: {report_raju['status']}")
    
    for action in report_raju['actions']:
        print(f"\n👉 Generated Action: {action['type'].upper()}")
        
        if action['type'] == 'script':
            # FIX: Removed [:150] and added a separator line
            print("-" * 20)
            print(action['content']) 
            print("-" * 20)
            
        elif action['type'] == 'file':
            print(f"   📂 File Path: {action['path']}")

    # --- TEST CASE 2 ---
    print("\n" + "="*60)
    print("⚠️  TEST 2: AMIT (Academic Watch -> Teacher Plan)")
    print("="*60)
    
    report_amit = system.process_intervention(student_id=3)
    print(f"📊 STATUS: {report_amit['status']}")
    
    for action in report_amit['actions']:
        print(f"\n👉 Generated Action: {action['type'].upper()}")
        
        if action['type'] == 'teacher_plan':
            # FIX: Removed [:200] and formatted it nicely
            print("-" * 20)
            print(action['content'])
            print("-" * 20)
if __name__ == "__main__":
    # CRITICAL STEP: Create tables first!
    init_db() 
    
    setup_test_data()
    run_tests()
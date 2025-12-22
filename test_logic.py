import json
import logging
from db_connector import run_query
from utils import DropoutInterventionSystem

# Configure logging to see what the system is doing
logging.basicConfig(level=logging.INFO)

def setup_test_data():
    """
    Resets the database to a known state so tests are consistent.
    """
    print("⚙️  Resetting Test Data in Database...")
    
    # 1. SETUP RAJU (ID 1) -> HIGH RISK (Low Attendance + Social Risk)
    run_query("UPDATE attendance SET attendance_percent = 60 WHERE student_id = 1")
    run_query("UPDATE social_risk SET parent_education_level = 'None', seasonal_labor = TRUE WHERE student_id = 1")
    
    # 2. SETUP AMIT (ID 3) -> ACADEMIC WATCH (Good Attendance, Bad Grades)
    run_query("UPDATE attendance SET attendance_percent = 95 WHERE student_id = 3")
    # Delete old scores and insert a 'Crash' scenario for Amit in Math
    run_query("DELETE FROM exam_scores WHERE student_id = 3")
    run_query("INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES (3, 'Math', 40, CURRENT_DATE)") 
    run_query("INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES (3, 'Math', 75, CURRENT_DATE - INTERVAL '4 months')")

def run_tests():
    # Initialize the System
    system = DropoutInterventionSystem()
    
    # --- TEST CASE 1: HIGH RISK INTERVENTION ---
    print("\n" + "="*60)
    print("🚨 TEST 1: RAJU (High Risk -> Script + PDF)")
    print("="*60)
    
    # We ask for the script in "Hindi" to test the AI's language capability
    report_raju = system.process_intervention(student_id=1, target_language="Hindi")
    
    print(f"📊 STATUS: {report_raju['status']}")
    
    for action in report_raju['actions']:
        print(f"\n👉 Generated Action: {action['type'].upper()}")
        if action['type'] == 'script':
            print(f"   📝 AI Script Preview: \"{action['content'][:150]}...\"")
        elif action['type'] == 'file':
            print(f"   📂 File Path: {action['path']}")

    # --- TEST CASE 2: ACADEMIC WATCH INTERVENTION ---
    print("\n" + "="*60)
    print("⚠️  TEST 2: AMIT (Academic Watch -> Teacher Plan)")
    print("="*60)
    
    report_amit = system.process_intervention(student_id=3)
    
    print(f"📊 STATUS: {report_amit['status']}")
    
    for action in report_amit['actions']:
        print(f"\n👉 Generated Action: {action['type'].upper()}")
        if action['type'] == 'teacher_plan':
            print(f"   👨‍🏫 Teacher Plan Preview: \n   {action['content'][:200]}...")

if __name__ == "__main__":
    setup_test_data()
    run_tests()
from db_connector import run_query
import json

def get_student_full_context(student_id):
    """
    Fetches a complete 360-degree view of a student for the Risk Analyst.
    Combines demographics, attendance trends, and academic performance.
    """
    # 1. Fetch Demographics
    student_sql = "SELECT * FROM students WHERE student_id = %s"
    student_data = run_query(student_sql, (student_id,), return_dict=True)
    
    if not student_data:
        return {"error": "Student not found"}

    # 2. Fetch Recent Attendance (Last 3 records)
    att_sql = "SELECT month, attendance_percent FROM attendance WHERE student_id = %s ORDER BY month DESC LIMIT 3"
    attendance = run_query(att_sql, (student_id,), return_dict=True)

    # 3. Fetch Academic Performance (Weakest Subjects)
    score_sql = "SELECT subject, score, exam_date FROM exam_scores WHERE student_id = %s ORDER BY exam_date DESC"
    scores = run_query(score_sql, (student_id,), return_dict=True)

    # 4. Fetch Social Risk Indicators
    risk_sql = "SELECT * FROM social_risk WHERE student_id = %s"
    social_risks = run_query(risk_sql, (student_id,), return_dict=True)

    return {
        "profile": student_data[0],
        "attendance_history": attendance,
        "academic_performance": scores,
        "social_risk_factors": social_risks[0] if social_risks else {}
    }

def find_eligible_scholarships(student_id):
    """
    Matches a student against the schemes table based on their specific profile.
    Used by the Financial Advocate agent.
    """
    # First, get the student's eligibility criteria
    student = run_query("SELECT grade, annual_income, caste_category, gender FROM students WHERE student_id = %s", (student_id,))
    if not student: return []
    
    s = student[0]
    sql = """
        SELECT scheme_name, income_limit 
        FROM schemes 
        WHERE min_grade <= %s AND max_grade >= %s
        AND income_limit >= %s 
        AND (caste_category = %s OR caste_category = 'Any')
        AND (gender = %s OR gender = 'Any')
    """
    params = (s['grade'], s['grade'], s['annual_income'], s['caste_category'], s['gender'])
    return run_query(sql, params, return_dict=True)

def record_intervention(student_id, agent_type, action_taken, content):
    """
    Logs an agent's specific output into the interventions table.
    This creates the structured 'short-term' memory for the system.
    """
    sql = """
        INSERT INTO interventions (student_id, agent_type, action_taken, content)
        VALUES (%s, %s, %s, %s)
        RETURNING intervention_id;
    """
    return run_query(sql, (student_id, agent_type, action_taken, content), is_write=True)

def get_intervention_history(student_id, limit=5):
    """
    Retrieves past structured interventions to provide context to an agent
    before it generates a new plan.
    """
    sql = """
        SELECT agent_type, action_taken, content, created_at 
        FROM interventions 
        WHERE student_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
    """
    return run_query(sql, (student_id, limit), return_dict=True)
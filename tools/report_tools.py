import os
from fpdf import FPDF
from pathlib import Path
from datetime import datetime

# Define the output directory for generated reports
OUTPUT_DIR = Path("generated_forms")
OUTPUT_DIR.mkdir(exist_ok=True)

def generate_intervention_pdf(student_data, scheme_name, risk_analysis):
    """
    Generates a printable PDF report for a student intervention.
    Includes student profile, identified risks, and the recommended scholarship.
    """
    # 1. Extract data safely
    profile = student_data.get('profile', {})
    
    # We use str() here to prevent "Object of type date is not serializable" 
    # if any of these fields are date types in the DB.
    student_name = str(profile.get('name', 'Unknown_Student'))
    gender = str(profile.get('gender', 'N/A'))
    grade = str(profile.get('grade', 'N/A'))
    caste = str(profile.get('caste_category', 'N/A'))
    income = str(profile.get('annual_income', 0))

    attendance_list = student_data.get('attendance_history', [])
    att_val = attendance_list[0].get('attendance_percent', 100) if attendance_list else 100
    
    # 2. Initialize PDF
    # Note: 'Arial' is standard, but 'helvetica' is more modern and widely supported in FPDF2
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER ---
    pdf.set_font("helvetica", 'B', 20)
    pdf.set_text_color(30, 58, 138)  # Professional Dark Blue
    pdf.cell(0, 20, txt="RESN INTERVENTION & SCHOLARSHIP FORM", ln=1, align='C')
    pdf.set_draw_color(30, 58, 138)
    pdf.line(10, 35, 200, 35)
    pdf.ln(10)

    # --- SECTION 1: STUDENT PROFILE ---
    pdf.set_fill_color(241, 245, 249) 
    pdf.set_font("helvetica", 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, " 1. STUDENT PROFILE", ln=1, fill=True)
    
    pdf.set_font("helvetica", size=11)
    # Profile details in a grid - explicitly converting to str to be safe
    pdf.cell(95, 10, f"Name: {student_name}", border=1)
    pdf.cell(95, 10, f"Gender: {gender}", border=1, ln=1)
    pdf.cell(95, 10, f"Grade: {grade}", border=1)
    pdf.cell(95, 10, f"Caste: {caste}", border=1, ln=1)
    pdf.cell(190, 10, f"Family Income: INR {income}", border=1, ln=1)
    pdf.ln(5)

    # --- SECTION 2: RISK ASSESSMENT ---
    pdf.set_font("helvetica", 'B', 12)
    pdf.cell(0, 10, " 2. ASSESSMENT SUMMARY", ln=1, fill=True)
    
    pdf.set_font("helvetica", size=11)
    att_status = "CRITICAL" if att_val < 75 else "STABLE"
    pdf.cell(95, 10, f"Attendance: {att_val}% ({att_status})", border=1)
    pdf.cell(95, 10, f"Assessment Date: {datetime.now().strftime('%Y-%m-%d')}", border=1, ln=1)
    
    # List identified social risks
    pdf.cell(0, 8, "Identified Social Risk Factors:", border="LR", ln=1)
    pdf.set_font("helvetica", 'I', 11)
    risks = student_data.get('social_risk_factors', {})
    found_any = False
    
    for risk_key, val in risks.items():
        if val is True:
            # Clean up key names (e.g., 'migrant_worker' -> 'Migrant Worker')
            risk_label = risk_key.replace('_', ' ').title()
            pdf.cell(0, 8, f"   - {risk_label}", border="LR", ln=1)
            found_any = True
    
    if not found_any:
        pdf.cell(0, 8, "   - No specific social risks identified.", border="LR", ln=1)
    
    pdf.cell(0, 2, "", border="T", ln=1) 
    pdf.ln(5)

    # --- SECTION 3: AI RECOMMENDATION ---
    pdf.set_font("helvetica", 'B', 12)
    pdf.cell(0, 10, " 3. RECOMMENDED ACTION PLAN", ln=1, fill=True)
    
    pdf.set_font("helvetica", size=11)
    recommendation_text = (
        f"Based on the agentic risk analysis, we recommend immediate enrollment in the: "
        f"{str(scheme_name).upper()}.\n\n"
        f"Agent Conclusion:\n{str(risk_analysis)}"
    )
    pdf.multi_cell(0, 8, recommendation_text, border=1)
    pdf.ln(15)
    
    # --- SIGNATURES ---
    pdf.set_font("helvetica", 'B', 10)
    # Using small spaces to align signatures
    pdf.cell(63, 10, "_______________________", align='C')
    pdf.cell(63, 10, "_______________________", align='C')
    pdf.cell(63, 10, "_______________________", align='C', ln=1)
    pdf.cell(63, 5, "Principal / Nodal Officer", align='C')
    pdf.cell(63, 5, "System Administrator", align='C')
    pdf.cell(63, 5, "Parent/Guardian", align='C', ln=1)

    # 3. Output file
    safe_name = "".join(x for x in student_name if x.isalnum() or x == "_")
    timestamp = datetime.now().strftime('%y%m%d_%H%M')
    file_path = OUTPUT_DIR / f"{safe_name}_Intervention_{timestamp}.pdf"
    
    pdf.output(str(file_path))
    
    return str(file_path)
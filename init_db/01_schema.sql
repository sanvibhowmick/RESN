-- ==========================================
-- 1. STUDENTS (Core Identity)
-- ==========================================
CREATE TABLE students (
  student_id SERIAL PRIMARY KEY,
  name TEXT,
  gender TEXT,          -- 'Male', 'Female'
  caste_category TEXT,  -- 'SC', 'ST', 'OBC', 'General'
  annual_income INT,
  grade INT
);

-- ==========================================
-- 2. ATTENDANCE (Monthly Aggregates)
-- ==========================================
CREATE TABLE attendance (
  record_id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(student_id),
  month DATE,           -- e.g., '2025-09-01'
  attendance_percent FLOAT
);

-- ==========================================
-- 3. EXAM SCORES (Time-Series Data)
-- ==========================================
CREATE TABLE exam_scores (
  score_id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(student_id),
  subject TEXT,
  exam_date DATE,
  score FLOAT
);

-- ==========================================
-- 4. SOCIAL RISK INDICATORS (The Hidden Factors)
-- ==========================================
CREATE TABLE social_risk (
  risk_id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(student_id),
  seasonal_labor BOOLEAN DEFAULT FALSE,
  sibling_dropout BOOLEAN DEFAULT FALSE,
  migrant_family BOOLEAN DEFAULT FALSE,
  childcare_responsibility BOOLEAN DEFAULT FALSE,
  
 
  parent_education_level VARCHAR(20) -- Values: 'None', 'Primary', 'Secondary', 'Graduate'
);

-- ==========================================
-- 5. GOVERNMENT SCHEMES (The Policy Rules)
-- ==========================================
CREATE TABLE schemes (
  scheme_id SERIAL PRIMARY KEY,
  scheme_name TEXT,
  min_grade INT,
  max_grade INT,
  income_limit INT,
  caste_category TEXT,
  gender TEXT           -- 'Male', 'Female', 'Any'
);

-- ==========================================
-- 6. STRATEGIC SEED DATA (To Test Your Logic)
-- ==========================================

-- SCHEMES (Policies)
INSERT INTO schemes (
  scheme_name,
  min_grade,
  max_grade,
  income_limit,
  caste_category,
  gender
) VALUES

('Pre-Matric Scholarship (SC)', 9, 10, 250000, 'SC', 'Any'),
('Begum Hazrat Mahal Scholarship', 9, 12, 200000, 'Any', 'Female'),


('Pre-Matric Scholarship (ST)', 9, 10, 250000, 'ST', 'Any'),

('OBC Pre-Matric Scholarship', 9, 10, 200000, 'OBC', 'Any'),

('National Means-cum-Merit Scholarship (NMMS)', 8, 12, 150000, 'Any', 'Any'),

('Girl Child Education Incentive Scheme', 6, 12, 300000, 'Any', 'Female');


INSERT INTO students (name, gender, caste_category, annual_income, grade)
VALUES ('Raju', 'Male', 'OBC', 45000, 9)
RETURNING student_id;
-- Exam score decline (trend-based)
INSERT INTO exam_scores (student_id, subject, score, exam_date) VALUES
(1, 'Math', 85, CURRENT_DATE - INTERVAL '4 months'),
(1, 'Math', 40, CURRENT_DATE - INTERVAL '1 month');

-- Social risk (low literacy household)
INSERT INTO social_risk (
  student_id, sibling_dropout, parent_education_level
) VALUES (1, TRUE, 'None');
INSERT INTO students (name, gender, caste_category, annual_income, grade)
VALUES ('Rani', 'Female', 'General', 150000, 9)
RETURNING student_id;
INSERT INTO social_risk (
  student_id, sibling_dropout, parent_education_level
) VALUES (2, TRUE, 'Secondary');
INSERT INTO students (name, gender, caste_category, annual_income, grade)
VALUES ('Amit', 'Male', 'General', 600000, 10)
RETURNING student_id;
INSERT INTO attendance (student_id, month, attendance_percent)
VALUES (3, '2025-01-01', 60.5);

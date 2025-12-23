-- schema.sql

-- ==========================================
-- 0. CLEANUP (Reset database for fresh start)
-- ==========================================
DROP TABLE IF EXISTS social_risk;
DROP TABLE IF EXISTS schemes;
DROP TABLE IF EXISTS exam_scores;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS students;

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
-- 6. STRATEGIC SEED DATA
-- ==========================================

-- SCHEMES
INSERT INTO schemes 
(scheme_name, min_grade, max_grade, income_limit, caste_category, gender)
VALUES
-- 1. Pre-Matric Scholarship for SC Students
('Pre-Matric Scholarship for SC Students', 1, 10, 250000, 'SC', 'Any'),

-- 2. Pre-Matric Scholarship for ST Students
('Pre-Matric Scholarship for ST Students', 1, 10, 250000, 'ST', 'Any'),

-- 3. Post-Matric Scholarship for SC Students
('Post-Matric Scholarship for SC Students', 11, 12, 250000, 'SC', 'Any'),

-- 4. Post-Matric Scholarship for ST Students
('Post-Matric Scholarship for ST Students', 11, 12, 250000, 'ST', 'Any'),

-- 5. Pre-Matric Scholarship for OBC Students
('Pre-Matric Scholarship for OBC Students', 1, 10, 100000, 'OBC', 'Any'),

-- 6. National Means-cum-Merit Scholarship (NMMS)
('National Means-cum-Merit Scholarship', 9, 12, 350000, 'Any', 'Any'),

-- 7. Begum Hazrat Mahal National Scholarship
('Begum Hazrat Mahal National Scholarship', 1, 12, 200000, 'Minority', 'Female'),

-- 8. Pragati Scholarship for Girl Students
('Pragati Scholarship for Girl Students', 11, 12, 800000, 'Any', 'Female'),

-- 9. Sukanya Samriddhi-linked State Scholarship
('Sukanya Samriddhi State Scholarship', 1, 12, 300000, 'Any', 'Female'),

-- 10. PM CARES for Children Scheme
('PM CARES for Children', 1, 12, 500000, 'Any', 'Any');


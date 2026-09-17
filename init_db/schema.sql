-- schema.sql

-- ==========================================
-- 0. EXTENSIONS & CLEANUP
-- ==========================================
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS agent_memory;
DROP TABLE IF EXISTS interventions;
DROP TABLE IF EXISTS social_risk;
DROP TABLE IF EXISTS schemes;
DROP TABLE IF EXISTS exam_scores;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS students;

-- ==========================================
-- 1. CORE RELATIONAL TABLES (Existing)
-- ==========================================
CREATE TABLE students (
  student_id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  gender TEXT CHECK (gender IN ('Male', 'Female', 'Other')),          -- 'Male', 'Female'
  caste_category TEXT,  -- 'SC', 'ST', 'OBC', 'General'
  annual_income INT,
  grade INT CHECK (grade BETWEEN 1 AND 12),
  age INT CHECK (age BETWEEN 3 AND 25),
  -- ==========================================
  -- Household & Location features
  -- Added to match the feature space the dropout_model.pth was trained on
  -- (previously hardcoded/defaulted in risk_analyst.py because the schema
  -- didn't capture them at all — see RESN_Interview_Prep.md)
  -- ==========================================
  hh_size INT,                  -- Total household size (number of people)
  hh_children INT,               -- Number of children in the household
  school_distanceKm FLOAT,       -- Distance from home to school, in km
  home_language TEXT,            -- Primary language spoken at home
  hh_occupation TEXT,            -- Primary household occupation (e.g., 'Farming', 'Daily Wage Labor')
  location_name TEXT             -- Village/town/settlement type (e.g., 'Rural', 'Semi-Urban', 'Urban')
);

CREATE TABLE attendance (
  record_id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(student_id) ON DELETE CASCADE,
  month DATE,
  attendance_percent FLOAT CHECK (attendance_percent BETWEEN 0 AND 100)
);

CREATE TABLE exam_scores (
  score_id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(student_id) ON DELETE CASCADE,
  subject TEXT,
  exam_date DATE,
  score FLOAT CHECK (score BETWEEN 0 AND 100)
);

CREATE TABLE social_risk (
  risk_id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(student_id) ON DELETE CASCADE,
  seasonal_labor BOOLEAN DEFAULT FALSE,
  sibling_dropout BOOLEAN DEFAULT FALSE,
  migrant_family BOOLEAN DEFAULT FALSE,
  childcare_responsibility BOOLEAN DEFAULT FALSE,
  parent_education_level VARCHAR(20) -- 'None', 'Primary', 'Secondary', 'Graduate'
);

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
-- 2. AGENTIC MEMORY & LOGGING (New)
-- ==========================================

-- Structured log of every action an agent takes
CREATE TABLE interventions (
  intervention_id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(student_id) ON DELETE CASCADE,
  agent_type TEXT,      -- 'RiskAnalyst', 'FinancialAdv', 'Educator'
  action_taken TEXT,    -- 'Generated Script', 'Matched Scholarship', 'Remedial Plan'
  content TEXT,         -- The actual text/plan generated
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector memory for semantic "Searchable" history
CREATE TABLE agent_memory (
  memory_id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(student_id) ON DELETE CASCADE,
  context_summary TEXT, -- Human-readable summary
  embedding vector(1536), -- Embedding size for OpenAI Models
  metadata JSONB,       -- Extra details (e.g., emotion, specific concerns)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 3. PERFORMANCE INDEXES
-- ==========================================
-- Speed up the WHERE student_id = %s lookups that every agent query uses.
CREATE INDEX idx_attendance_student_id ON attendance(student_id);
CREATE INDEX idx_exam_scores_student_id ON exam_scores(student_id);
CREATE INDEX idx_social_risk_student_id ON social_risk(student_id);
CREATE INDEX idx_interventions_student_id ON interventions(student_id);
CREATE INDEX idx_agent_memory_student_id ON agent_memory(student_id);

-- NOTE: ivfflat index quality degrades as row count grows significantly
-- past what it was built for. Run REINDEX once data grows past ~10k rows.
CREATE INDEX idx_agent_memory_embedding
  ON agent_memory USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

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

-- 7. REPLACED: Pre-Matric Scholarship for Minority Students
('Pre-Matric Scholarship for Minority Students', 1, 10, 100000, 'Minority', 'Any'),

-- 8. Pragati Scholarship for Girl Students
('Pragati Scholarship for Girl Students', 11, 12, 800000, 'Any', 'Female'),

-- 9. Sukanya Samriddhi-linked State Scholarship
('Sukanya Samriddhi State Scholarship', 1, 12, 300000, 'Any', 'Female'),

-- 10. PM CARES for Children Scheme
('PM CARES for Children', 1, 12, 500000, 'Any', 'Any');
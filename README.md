# RESN — Rural Education Safety Net
### Multi-Agent AI System for Student Dropout Mitigation

RESN is an end-to-end AI platform designed to identify at-risk students in rural communities and automate targeted, localized interventions. By bridging the gap between raw predictive analytics and human-centric support, the system provides a comprehensive "safety net" through automated scholarship matching, multilingual parent counseling, and teacher remediation planning.

[Live Demo](#https://resnbysanvi.streamlit.app/) 

---

## 🚀 Key Features

- **Predictive Risk Analytics:** High-precision identification of at-risk students using a custom Neural Network optimized for high-stakes recall.

- **Multi-Agent Orchestration:** A collaborative system of GPT-4o-powered agents that reason over socio-economic signals—such as seasonal labor patterns and sibling history—to generate explainable intervention strategies.

- **Automated Specialized Interventions:**
  - **Scholarship Matching:** Intelligent mapping of student demographics to eligible government schemes, including automated PDF application generation.
  - **Multilingual Parent Counseling:** Generation of persuasive talking points in local dialects (e.g., Bengali, Hindi), tailored to parent literacy levels.
  - **Teacher Remediation Planning:** Creation of pedagogical "Quick-Action Cards" using rural-context metaphors to assist struggling students in specific subjects.

- **Historical Memory Layer:** A PostgreSQL-backed persistent memory system that tracks and retrieves historical intervention summaries to ensure context-aware continuity in student support.

- **Real-Time Analytics Dashboard:** A Streamlit-based interface for school administrators to monitor risk trends, manage student data, and trigger agent-led interventions.

---

## 🧠 Technical Architecture

### 1. The Predictive Backbone (ML)

The system's foundation is a PyTorch Neural Network featuring a residual architecture designed to handle imbalanced socio-educational datasets.

- **Performance:** Achieved 0.98 Recall and 0.98 ROC-AUC.
- **Optimization:** Utilized Optuna for systematic hyperparameter tuning, focusing on architectural parameters like layer depth, unit counts, and dropout rates to ensure reliable detection of the minority "at-risk" class.

### 2. Intelligent Agent Triage

A central **Orchestrator** manages the flow of information between specialized agents based on the student's real-time risk status:

- **Risk Analyst:** Combines the ML-generated risk score with LLM reasoning to categorize students into `Normal`, `Watch`, or `Danger` statuses.
- **Financial Advocate:** Queries a database of scholarship schemes to identify the most impactful financial aid for the student's profile.
- **Educator & Community Mediator:** Triggered for `Watch` and `Danger` cases to provide academic and social support scripts.

### 3. Data & Memory Infrastructure

- **Persistent Storage:** PostgreSQL manages core relational data across tables for students, attendance, and exam scores.
- **Intervention Tracking:** Every agent action is logged in a structured `interventions` table, while a semantic memory layer (using `pgvector`) enables the system to "remember" and reference past student cases.

---

## 🛠️ Tech Stack

| Category | Technologies |
|---|---|
| Languages | Python, SQL |
| ML Frameworks | PyTorch, Scikit-learn, Optuna |
| AI Orchestration | OpenAI API (GPT-4o/mini), LangChain,LangGraph |
| Database | PostgreSQL, pgvector |
| Deployment | Docker, Streamlit |

---

## ⚙️ Installation & Setup

**1. Clone the Repository:**
```bash
git clone https://github.com/yourusername/resn.git
cd resn
```

**2. Environment Configuration:**
Create a `.env` file with your credentials:
```
OPENAI_API_KEY=your_key_here
DB_HOST=localhost
DB_NAME=neondb
DB_USER=admin
DB_PASS=password
```

**3. Deploy via Docker:**
```bash
docker-compose up --build
```

**4. Access the Dashboard:**
Open `http://localhost:8501` to view the RESN Intervention Center.

---

## 📊 Dashboard Preview

The platform provides a 360-degree view of school performance and individual student health:

- **Dashboard:** High-level metrics for enrollment, risk counts, and parental literacy profiles.
- **Intervention Center:** A case-management interface to run analysis on specific students and view recommended action cards.
- **Data Entry:** Manual and bulk CSV upload support for streamlined record-keeping.

---

## 🤝 Contribution

This project was built to address the specific challenges of rural education in India. If you have suggestions for better social factor integration or more localized datasets, feel free to open an issue or PR!

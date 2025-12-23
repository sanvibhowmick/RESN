🌾 RESN (Rural Education Safety Net)
RESN is a data-driven app designed to prevent student dropouts in rural India. It identifies at-risk students using academic and socioeconomic data and uses AI to generate personalized interventions.

🚀 Key Features
Risk Dashboard: Tracks attendance, grades, and social factors (like seasonal labor) to flag high-risk students.

AI Assistants: Uses Google Gemini to write personalized scripts for parent meetings and remedial plans for teachers.

Auto-Scholarships: Automatically matches students to government schemes and generates pre-filled PDF application forms.

🛠️ Quick Start
1. Prerequisites

Python 3.8+

Docker Desktop (for the database)

2. Configure Credentials Create a .env file in the root directory:

Code snippet

DB_HOST=localhost
DB_NAME=resn_school
DB_USER=admin
DB_PASS=password
GEMINI_API_KEY=your_google_api_key
3. Start the Database Run the following command to start PostgreSQL and load the initial data:

Bash

docker-compose up -d


4. Install Dependencies

Bash

pip install -r requirements.txt


5. Run the App

Bash

streamlit run app.py


📂 Tech Stack
Frontend: Streamlit

Backend: Python

Database: PostgreSQL

AI Model: Google Gemini Flash

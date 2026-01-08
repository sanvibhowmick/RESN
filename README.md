RESN: Rural Education Safety Net (Agentic AI Version)
=====================================================

**RESN** is an advanced, multi-agent AI system designed to identify and mitigate student dropout risks in rural India. By integrating real-time educational data with social and economic indicators, RESN orchestrates a team of specialized AI agents to provide targeted interventions, including scholarship matching, parent counseling, and remedial pedagogical plans.

🌟 Key Features
---------------

*   **Multi-Agent Orchestration**: A central "Brain" coordinates specialized agents for risk analysis, financial advocacy, academic planning, and community mediation.
    
*   **Deep Diagnostic Analysis**: Uses Large Language Models (LLMs) to analyze complex trends, such as correlating sharp academic declines with seasonal labor patterns.
    
*   **Semantic Long-Term Memory**: Utilizes **pgvector** to store and retrieve historical interventions, ensuring the system learns from past student progress.
    
*   **Automated Intervention Tools**:
    
    *   **Financial Advocate**: Matches students to government schemes and generates pre-filled PDF applications.
        
    *   **Educator Agent**: Creates subject-specific "Quick-Action Cards" using rural metaphors for teachers.
        
    *   **Community Mediator**: Generates persuasive counseling scripts for parents in local languages like Hindi, Bengali, Marathi, and Tamil.
        

🏗️ Project Architecture
------------------------

### Specialized Agents (/agents)

*   **risk\_analyst.py**: The diagnostic core that evaluates academic, attendance, and social risk data to determine risk scores and status.
    
*   **financial\_adv.py**: A policy expert that selects the most impactful scholarships and automates paperwork.
    
*   **educator.py**: A pedagogy expert that bridges conceptual gaps with actionable, low-cost teacher guidance.
    
*   **community\_mediator.py**: A cultural mediator that empowers volunteers with direct-speech scripts tailored to parent literacy levels.
    
*   **orchestrator.py**: The central "CEO" agent that manages the pipeline, triage logic, and memory integration.
    

### Core Tools (/tools)

*   **db\_tools.py**: Provides structured data fetching optimized for consumption by AI agents.
    
*   **report\_tools.py**: A standalone PDF generation engine for professional intervention forms.
    

### Memory Layer (/memory)

*   **pg\_vector.py**: Manages semantic searchable history using OpenAI embeddings and PostgreSQL.
    

🛠️ Technical Stack
-------------------

*   **Frontend**: [Streamlit](https://streamlit.io/) for an interactive dashboard and data management.
    
*   **Database**: [PostgreSQL](https://www.postgresql.org/) with [pgvector](https://github.com/pgvector/pgvector) for relational data and semantic memory.
    
*   **LLM Integration**: [OpenAI GPT-4o](https://openai.com/) for high-reasoning analysis and GPT-4o-mini for task-specific efficiency.
    
*   **Containerization**: [Docker](https://www.docker.com/) for unified database and vector extension deployment.
    

🚀 Getting Started
------------------

### 1\. Prerequisites

*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed.
    
*   Python 3.12+ environment.
    
*   OpenAI API Key.
    

### 2\. Infrastructure Setup

Use Docker to spin up the PostgreSQL instance with pgvector support:



 ```bash docker-compose up -d   ```

### 3\. Installation

Install required dependencies:



 ```bash  pip install -r requirements.txt   ```

### 4\. Configuration

Create a .env file in the root directory with the following variables:

Code snippet

 ```bash
OPENAI_API_KEY=your_key_here
DB_HOST=localhost
DB_PORT=5433
DB_NAME=resn_school
DB_USER=admin
DB_PASS=password
```

### 5\. Initialization

Apply the schema and initialize the vector extension:



```bash  python db_connector.py   ```

### 6\. Run the App

Launch the Streamlit dashboard:



 ```bash  streamlit run app.py   ```

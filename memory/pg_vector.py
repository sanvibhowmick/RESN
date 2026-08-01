import os
from openai import OpenAI
import json
from db_connector import run_query

class PGVectorMemory:
    def __init__(self):
        # Assumes OPENAI_API_KEY is available in your environment/secrets
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Using the high-performance small model
        self.model = "text-embedding-3-small" 

    def _get_embedding(self, text):
        """Generates a 1536-dimensional vector using OpenAI."""
        try:
            response = self.client.embeddings.create(
                input=[text.replace("\n", " ")],
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ OpenAI Embedding Error: {e}")
            return None

    def add_memory(self, student_id, context_summary, metadata=None):
        embedding = self._get_embedding(context_summary)
        if not embedding: return False

        # FIX: Added ::vector cast to the third parameter
        sql = """
            INSERT INTO agent_memory (student_id, context_summary, embedding, metadata)
            VALUES (%s, %s, %s::vector, %s)
        """
        metadata_json = json.dumps(metadata) if metadata else None
        return run_query(sql, (student_id, context_summary, embedding, metadata_json), is_write=True)

    def search_memory(self, student_id, query_text, limit=3):
        query_embedding = self._get_embedding(query_text)
        if not query_embedding: return []

        # FIX: Added ::vector cast to the embedding parameter
        sql = """
            SELECT context_summary, metadata, created_at,
                   (embedding <=> %s::vector) as distance
            FROM agent_memory
            WHERE student_id = %s
            ORDER BY distance ASC
            LIMIT %s;
        """
        return run_query(sql, (query_embedding, student_id, limit), return_dict=True)

    def find_similar_cases(self, query_text, exclude_student_id=None, limit=5):
        """Semantic search ACROSS ALL STUDENTS for cases with a similar risk
        profile/history, instead of one student's own past entries.

        query_text should describe the CURRENT situation (e.g. the
        RiskAnalyst's summary_for_memory for this run), not a fixed generic
        phrase -- the whole point of a cross-student search is to find
        entries whose meaning is close to what's happening right now.

        exclude_student_id lets you exclude the current student's own
        memories, so results are genuinely "other students like this one."
        """
        query_embedding = self._get_embedding(query_text)
        if not query_embedding: return []

        if exclude_student_id is not None:
            sql = """
                SELECT student_id, context_summary, metadata, created_at,
                       (embedding <=> %s::vector) as distance
                FROM agent_memory
                WHERE student_id != %s
                ORDER BY distance ASC
                LIMIT %s;
            """
            params = (query_embedding, exclude_student_id, limit)
        else:
            sql = """
                SELECT student_id, context_summary, metadata, created_at,
                       (embedding <=> %s::vector) as distance
                FROM agent_memory
                ORDER BY distance ASC
                LIMIT %s;
            """
            params = (query_embedding, limit)

        return run_query(sql, params, return_dict=True)
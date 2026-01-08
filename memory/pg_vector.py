import os
from openai import OpenAI
import json
from db_connector import run_query

class PGVectorMemory:
    def __init__(self):
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

        sql = """
            INSERT INTO agent_memory (student_id, context_summary, embedding, metadata)
            VALUES (%s, %s, %s, %s)
        """
        metadata_json = json.dumps(metadata) if metadata else None
        return run_query(sql, (student_id, context_summary, embedding, metadata_json), is_write=True)

    def search_memory(self, student_id, query_text, limit=3):
        query_embedding = self._get_embedding(query_text)
        if not query_embedding: return []

        sql = """
            SELECT context_summary, metadata, created_at,
                   (embedding <=> %s) as distance
            FROM agent_memory
            WHERE student_id = %s
            ORDER BY distance ASC
            LIMIT %s;
        """
        return run_query(sql, (query_embedding, student_id, limit), return_dict=True)
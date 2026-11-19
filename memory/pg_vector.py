import os
import json
import math
from openai import OpenAI
from db_connector import run_query


class PGVectorMemory:
    """Advanced Hybrid Episodic Memory Engine using PostgreSQL and pgvector.

    Key Architectural Upgrades:
    1. Hybrid Search: Fuses Dense Vector Embeddings (semantic) with Sparse BM25 (keyword matching).
    2. Exponential Time-Decay Weighting: Penalizes stale memories according to a configurable half-life.
    3. Metadata Filtering: Dynamic JSONB filtering across cohorts, districts, triage status, and languages.
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    def _get_embedding(self, text):
        """Generates a 1536-dimensional vector using OpenAI text-embedding-3-small."""
        if not text or not str(text).strip():
            return None
        try:
            response = self.client.embeddings.create(
                input=[str(text).replace("\n", " ")],
                model=self.model,
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ OpenAI Embedding Error: {e}")
            return None

    def add_memory(self, student_id, context_summary, metadata=None):
        """Persists a new contextual memory vector with rich JSONB metadata."""
        embedding = self._get_embedding(context_summary)
        if not embedding:
            return False

        sql = """
            INSERT INTO agent_memory (student_id, context_summary, embedding, metadata)
            VALUES (%s, %s, %s::vector, %s)
        """
        metadata_json = json.dumps(metadata) if metadata else None
        return run_query(
            sql,
            (student_id, context_summary, embedding, metadata_json),
            is_write=True,
        )

    def hybrid_search_memory(
        self,
        query_text,
        student_id=None,
        exclude_student_id=None,
        metadata_filter=None,
        time_decay_half_life_days=90.0,
        vector_weight=0.7,
        bm25_weight=0.3,
        limit=5,
    ):
        """Executes Reciprocal Rank Fusion / Weighted Hybrid Search across vector embeddings
        and PostgreSQL full-text search with exponential time decay and metadata filtering.

        Args:
            query_text: Plain text search query.
            student_id: (Optional) Match memories specifically for this student.
            exclude_student_id: (Optional) Exclude this student (for cross-student cohort search).
            metadata_filter: (Optional) Dict of JSONB key-values to match (e.g. {'status': 'DANGER', 'grade': 10}).
            time_decay_half_life_days: Half-life in days for exponential recency decay. Set <=0 to disable.
            vector_weight: Weight assigned to dense vector similarity (default 0.7).
            bm25_weight: Weight assigned to BM25 full-text keyword match (default 0.3).
            limit: Maximum records to return.
        """
        query_embedding = self._get_embedding(query_text)
        if not query_embedding:
            return []

        # Calculate decay constant lambda = ln(2) / half_life
        decay_lambda = (
            math.log(2.0) / float(time_decay_half_life_days)
            if time_decay_half_life_days and time_decay_half_life_days > 0
            else 0.0
        )

        # Build dynamic SQL WHERE conditions
        where_clauses = []
        where_params = []

        if student_id is not None:
            where_clauses.append("student_id = %s")
            where_params.append(student_id)

        if exclude_student_id is not None:
            where_clauses.append("student_id != %s")
            where_params.append(exclude_student_id)

        if metadata_filter and isinstance(metadata_filter, dict):
            for k, v in metadata_filter.items():
                where_clauses.append("metadata->>%s = %s")
                where_params.extend([str(k), str(v)])

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # SQL Hybrid Scoring:
        # 1. Vector similarity: 1.0 - (distance / 2.0) mapped into [0, 1]
        # 2. BM25 rank: ts_rank_cd text ranking normalized
        # 3. Time decay: EXP(-lambda * days_elapsed)
        sql = f"""
            WITH ranked_candidates AS (
                SELECT
                    memory_id,
                    student_id,
                    context_summary,
                    metadata,
                    created_at,
                    GREATEST(0.0, 1.0 - (embedding <=> %s::vector) / 2.0) AS vector_similarity,
                    COALESCE(
                        ts_rank_cd(
                            to_tsvector('english', context_summary),
                            plainto_tsquery('english', %s)
                        ),
                        0.0
                    ) AS bm25_score,
                    GREATEST(0.0, EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0) AS days_elapsed
                FROM agent_memory
                {where_sql}
            )
            SELECT
                memory_id,
                student_id,
                context_summary,
                metadata,
                created_at,
                vector_similarity,
                bm25_score,
                days_elapsed,
                EXP(-%s * days_elapsed) AS time_decay_factor,
                (
                    (%s * vector_similarity) + (%s * bm25_score)
                ) * EXP(-%s * days_elapsed) AS hybrid_score,
                (1.0 - vector_similarity) * 2.0 AS distance
            FROM ranked_candidates
            ORDER BY hybrid_score DESC
            LIMIT %s;
        """

        # Parameters order: query_embedding, query_text, *where_params, decay_lambda, vector_weight, bm25_weight, decay_lambda, limit
        query_params = [
            query_embedding,
            str(query_text),
            *where_params,
            decay_lambda,
            float(vector_weight),
            float(bm25_weight),
            decay_lambda,
            int(limit),
        ]

        try:
            return run_query(sql, tuple(query_params), return_dict=True) or []
        except Exception as e:
            print(f"Notice: Hybrid memory search fell back to standard vector search: {e}")
            return self._fallback_vector_search(query_embedding, student_id, exclude_student_id, limit)

    def _fallback_vector_search(self, query_embedding, student_id=None, exclude_student_id=None, limit=5):
        """Reliable fallback if PostgreSQL full-text search extensions have locale/version variance."""
        where_sql = ""
        params = [query_embedding]

        if student_id is not None:
            where_sql = "WHERE student_id = %s"
            params.append(student_id)
        elif exclude_student_id is not None:
            where_sql = "WHERE student_id != %s"
            params.append(exclude_student_id)

        params.append(limit)

        sql = f"""
            SELECT student_id, context_summary, metadata, created_at,
                   (embedding <=> %s::vector) AS distance
            FROM agent_memory
            {where_sql}
            ORDER BY distance ASC
            LIMIT %s;
        """
        return run_query(sql, tuple(params), return_dict=True) or []

    def search_memory(self, student_id, query_text, limit=3, metadata_filter=None):
        """Retrieves past contextual memories for a specific student using Hybrid Search + Time Decay."""
        return self.hybrid_search_memory(
            query_text=query_text,
            student_id=student_id,
            metadata_filter=metadata_filter,
            time_decay_half_life_days=90.0,
            vector_weight=0.75,
            bm25_weight=0.25,
            limit=limit,
        )

    def find_similar_cases(
        self,
        query_text,
        exclude_student_id=None,
        status=None,
        metadata_filter=None,
        limit=3,
    ):
        """Cross-student cohort retrieval with time decay, risk-level cohort alignment,
        student deduplication, and historical post-intervention improvements attached.

        Args:
            query_text: Plain text search query.
            exclude_student_id: Exclude this student (cross-student cohort search).
            status: (Optional) Current student's risk status ('NORMAL', 'WATCH', 'DANGER').
                    Aligns search so NORMAL/WATCH students are compared with comparable cases.
            metadata_filter: (Optional) JSONB key-value metadata filter.
            limit: Maximum distinct historical cases to return.
        """
        # Determine cohort-aligned statuses to prevent showing DANGER cases to NORMAL/WATCH students
        status_clean = str(status).strip().upper() if status else None
        if status_clean == "NORMAL":
            allowed_statuses = ["NORMAL", "WATCH"]
        elif status_clean == "WATCH":
            allowed_statuses = ["WATCH", "NORMAL"]
        elif status_clean == "DANGER":
            allowed_statuses = ["DANGER"]
        else:
            allowed_statuses = None

        candidates = self.hybrid_search_memory(
            query_text=query_text,
            exclude_student_id=exclude_student_id,
            metadata_filter=metadata_filter,
            time_decay_half_life_days=180.0,
            vector_weight=0.70,
            bm25_weight=0.30,
            limit=limit * 4,
        )

        if allowed_statuses:
            aligned = [
                c
                for c in candidates
                if str((c.get("metadata") or {}).get("status", "")).upper()
                in allowed_statuses
            ]
            if aligned:
                candidates = aligned

        # Deduplicate by student_id and attach latest post-intervention improvements
        seen_sids = set()
        deduped = []
        for c in candidates:
            sid = c.get("student_id")
            if sid not in seen_sids:
                seen_sids.add(sid)
                try:
                    imp_rows = run_query(
                        """
                        SELECT improvement_id, student_id, previous_attendance, new_attendance,
                               subject, previous_score, new_score, grade, outcome_status,
                               measures_taken, notes, created_at
                        FROM student_improvements
                        WHERE student_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (sid,),
                        return_dict=True,
                    )
                    c["improvement"] = imp_rows[0] if imp_rows else None
                except Exception as e:
                    print(f"Notice: Failed to fetch student improvement: {e}")
                    c["improvement"] = None

                deduped.append(c)
                if len(deduped) >= limit:
                    break

        return deduped

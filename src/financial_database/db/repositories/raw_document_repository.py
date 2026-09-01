"""Raw document repository.

Metadata references to preserved raw data files.
"""

import json

import psycopg


class RawDocumentRepository:
    """Repository for raw_documents table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(
        self,
        provider_id: str,
        source_identifier: str,
        storage_path: str,
        checksum: str | None = None,
        content_type: str | None = None,
        metadata: dict | None = None,
        is_processed: bool = False,
    ) -> dict:
        """Create a new raw document record."""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO raw_documents (provider_id, source_identifier, storage_path, checksum,
                   content_type, metadata, is_processed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (provider_id, source_identifier) DO NOTHING
                   RETURNING id, provider_id, source_identifier, storage_path, checksum,
                   content_type, metadata, is_processed, retrieved_at, created_at, updated_at""",
                (
                    provider_id,
                    source_identifier,
                    storage_path,
                    checksum,
                    content_type,
                    json.dumps(metadata or {}),
                    is_processed,
                ),
            )
            rows = cur.fetchall(); return rows[0] if rows else None

    def get_by_provider(self, provider_id: str) -> list[dict]:
        """Get raw documents for a provider."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, provider_id, source_identifier, storage_path, checksum, "
                "content_type, metadata, is_processed, retrieved_at, created_at, updated_at "
                "FROM raw_documents WHERE provider_id = %s ORDER BY retrieved_at DESC",
                (provider_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_unprocessed(self, provider_id: str | None = None) -> list[dict]:
        """Get unprocessed raw documents."""
        with self.conn.cursor() as cur:
            if provider_id:
                cur.execute(
                    "SELECT id, provider_id, source_identifier, storage_path, checksum, "
                    "content_type, metadata, is_processed, retrieved_at, created_at, updated_at "
                    "FROM raw_documents WHERE is_processed = FALSE AND provider_id = %s ORDER BY retrieved_at",
                    (provider_id,),
                )
            else:
                cur.execute(
                    "SELECT id, provider_id, source_identifier, storage_path, checksum, "
                    "content_type, metadata, is_processed, retrieved_at, created_at, updated_at "
                    "FROM raw_documents WHERE is_processed = FALSE ORDER BY retrieved_at"
                )
            return [dict(row) for row in cur.fetchall()]

    def mark_processed(self, doc_id: str) -> None:
        """Mark a raw document as processed."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE raw_documents SET is_processed = TRUE, updated_at = NOW() WHERE id = %s",
                (doc_id,),
            )

"""initial schema

Revision ID: 20260315_000001
Revises:
Create Date: 2026-03-15 00:00:01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.core.config import get_settings
from app.db.types import EmbeddingVector

# revision identifiers, used by Alembic.
revision = "20260315_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    embedding_dimensions = get_settings().embedding_dimensions

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("content_chars", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_path"),
    )
    op.create_index("ix_documents_checksum", "documents", ["checksum"], unique=False)

    op.create_table(
        "answer_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("refusal_reason", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("generator_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("token_usage", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("retrieved_scores", sa.JSON(), nullable=False),
        sa.Column("context_char_count", sa.Integer(), nullable=False),
        sa.Column("failure_stage", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_name", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("should_refuse", sa.Boolean(), nullable=False),
        sa.Column("expected_document_ids", sa.JSON(), nullable=False),
        sa.Column("expected_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("expected_keywords", sa.JSON(), nullable=False),
        sa.Column("forbidden_terms", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_cases_dataset_name", "eval_cases", ["dataset_name"], unique=False)

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dataset_name", sa.String(length=128), nullable=False),
        sa.Column("snapshot_name", sa.String(length=128), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("bad_cases_json", sa.JSON(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_runs_dataset_name", "eval_runs", ["dataset_name"], unique=False)

    op.create_table(
        "replay_experiments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_name", sa.String(length=255), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("source_eval_run_id", sa.String(length=36), nullable=True),
        sa.Column("source_snapshot_name", sa.String(length=128), nullable=True),
        sa.Column("snapshot_name", sa.String(length=128), nullable=False),
        sa.Column("overrides_json", sa.JSON(), nullable=False),
        sa.Column("effective_settings_json", sa.JSON(), nullable=False),
        sa.Column("audit_id", sa.String(length=36), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("refusal_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_replay_experiments_audit_id",
        "replay_experiments",
        ["audit_id"],
        unique=False,
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title_path", sa.String(length=512), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("embedding", EmbeddingVector(embedding_dimensions), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_index("ix_replay_experiments_audit_id", table_name="replay_experiments")
    op.drop_table("replay_experiments")
    op.drop_index("ix_eval_runs_dataset_name", table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_index("ix_eval_cases_dataset_name", table_name="eval_cases")
    op.drop_table("eval_cases")
    op.drop_table("answer_runs")
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.drop_table("documents")

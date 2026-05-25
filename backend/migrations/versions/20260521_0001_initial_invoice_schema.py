"""initial invoice schema

Revision ID: 20260521_0001
Revises:
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260521_0001"
down_revision = None
branch_labels = None
depends_on = None

invoice_status = postgresql.ENUM(
    "uploaded",
    "processing",
    "completed",
    "needs_review",
    "failed",
    name="invoicestatus",
    create_type=False,
)


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invoicestatus') THEN
                CREATE TYPE invoicestatus AS ENUM (
                    'uploaded',
                    'processing',
                    'completed',
                    'needs_review',
                    'failed'
                );
            END IF;
        END
        $$;
        """
    )

    if not table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=128), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    if not table_exists("invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
            sa.Column("user_id", sa.String(length=128), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.String(length=500), nullable=False),
            sa.Column("stored_file_path", sa.String(length=500), nullable=False),
            sa.Column("invoice_number", sa.String(length=100), nullable=True),
            sa.Column("invoice_date", sa.Date(), nullable=True),
            sa.Column("seller_name", sa.String(length=255), nullable=True),
            sa.Column("seller_address", sa.Text(), nullable=True),
            sa.Column("seller_vat_pan_number", sa.String(length=100), nullable=True),
            sa.Column("buyer_name", sa.String(length=255), nullable=True),
            sa.Column("buyer_address", sa.Text(), nullable=True),
            sa.Column("buyer_vat_pan_number", sa.String(length=100), nullable=True),
            sa.Column("subtotal", sa.Numeric(14, 2), nullable=True),
            sa.Column("discount", sa.Numeric(14, 2), nullable=True),
            sa.Column("vat_amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("total_amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("currency", sa.String(length=20), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("status", invoice_status, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_invoices_status"), "invoices", ["status"], unique=False)
        op.create_index(op.f("ix_invoices_user_id"), "invoices", ["user_id"], unique=False)

    if not table_exists("invoice_items"):
        op.create_table(
            "invoice_items",
            sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
            sa.Column("invoice_id", sa.UUID(as_uuid=False), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("quantity", sa.Numeric(14, 2), nullable=True),
            sa.Column("rate", sa.Numeric(14, 2), nullable=True),
            sa.Column("amount", sa.Numeric(14, 2), nullable=True),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_invoice_items_invoice_id"), "invoice_items", ["invoice_id"], unique=False)

    if not table_exists("invoice_extraction_logs"):
        op.create_table(
            "invoice_extraction_logs",
            sa.Column("id", sa.UUID(as_uuid=False), nullable=False),
            sa.Column("invoice_id", sa.UUID(as_uuid=False), nullable=False),
            sa.Column("raw_ai_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("status", invoice_status, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_invoice_extraction_logs_invoice_id"),
            "invoice_extraction_logs",
            ["invoice_id"],
            unique=False,
        )


def downgrade() -> None:
    if table_exists("invoice_extraction_logs"):
        op.drop_index(op.f("ix_invoice_extraction_logs_invoice_id"), table_name="invoice_extraction_logs")
        op.drop_table("invoice_extraction_logs")
    if table_exists("invoice_items"):
        op.drop_index(op.f("ix_invoice_items_invoice_id"), table_name="invoice_items")
        op.drop_table("invoice_items")
    if table_exists("invoices"):
        op.drop_index(op.f("ix_invoices_user_id"), table_name="invoices")
        op.drop_index(op.f("ix_invoices_status"), table_name="invoices")
        op.drop_table("invoices")
    if table_exists("users"):
        op.drop_index(op.f("ix_users_email"), table_name="users")
        op.drop_table("users")
    invoice_status.drop(op.get_bind(), checkfirst=True)

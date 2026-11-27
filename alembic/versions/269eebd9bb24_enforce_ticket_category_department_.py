"""enforce ticket category department consistency

Revision ID: 269eebd9bb24
Revises: 575b4819a5bc
Create Date: 2026-11-27 12:18:01.547392
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "269eebd9bb24"
down_revision: str | Sequence[str] | None = "575b4819a5bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    connection = op.get_bind()

    inconsistent_tickets = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM tickets t
            JOIN categories c
                ON c.id = t.category_id
            WHERE t.department_id <> c.department_id
            """
        )
    ).scalar_one()

    if inconsistent_tickets:
        raise RuntimeError(
            f"Found {inconsistent_tickets} tickets with "
            "inconsistent category and department values. "
            "Repair these records before applying the migration."
        )

    op.create_unique_constraint(
        "uq_categories_id_department_id",
        "categories",
        ["id", "department_id"],
    )

    op.create_foreign_key(
        "fk_tickets_category_department",
        "tickets",
        "categories",
        ["category_id", "department_id"],
        ["id", "department_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "fk_tickets_category_department",
        "tickets",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_categories_id_department_id",
        "categories",
        type_="unique",
    )

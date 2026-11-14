"""add ticket status value under_review

Revision ID: 3cc05abbaf22
Revises: 1282a9f06f85
Create Date: 2026-11-14 17:13:20.406564

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "3cc05abbaf22"
down_revision: Union[str, Sequence[str], None] = "1282a9f06f85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("check_ticket_status", "tickets", type_="check")

    op.create_check_constraint(
        "check_ticket_status",
        "tickets",
        "status IN ('open', 'under_review', 'in_progress', 'resolved', 'closed')",
    )


def downgrade() -> None:
    op.drop_constraint("check_ticket_status", "tickets", type_="check")

    op.create_check_constraint(
        "check_ticket_status",
        "tickets",
        "status IN ('open', 'in_progress', 'resolved', 'closed')",
    )

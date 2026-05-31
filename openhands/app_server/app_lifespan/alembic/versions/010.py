"""Add token_timeline and condensation_details columns to conversation_metadata table

Revision ID: 010
Revises: 009
Create Date: 2026-05-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'conversation_metadata',
        sa.Column('token_timeline', sa.JSON(), nullable=True),
    )
    op.add_column(
        'conversation_metadata',
        sa.Column('condensation_details', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('conversation_metadata', 'token_timeline')
    op.drop_column('conversation_metadata', 'condensation_details')

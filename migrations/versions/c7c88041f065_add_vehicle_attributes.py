"""add vehicle attributes

Revision ID: c7c88041f065
Revises: a739f8d10765
Create Date: 2026-06-05 14:07:36.993123
"""
from alembic import op
import sqlalchemy as sa


revision = 'c7c88041f065'
down_revision = 'a739f8d10765'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('detections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vehicle_type', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('vehicle_color', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('vehicle_confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('detections', schema=None) as batch_op:
        batch_op.drop_column('vehicle_confidence')
        batch_op.drop_column('vehicle_color')
        batch_op.drop_column('vehicle_type')

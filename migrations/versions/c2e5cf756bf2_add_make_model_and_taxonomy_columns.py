"""add make_model and taxonomy columns

Revision ID: c2e5cf756bf2
Revises: c7c88041f065
Create Date: 2026-06-05 14:27:59.999984
"""
from alembic import op
import sqlalchemy as sa


revision = 'c2e5cf756bf2'
down_revision = 'c7c88041f065'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('detections', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vehicle_make', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('vehicle_model', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('vehicle_make_model_confidence', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('vehicle_category', sa.String(length=48), nullable=True))
        batch_op.add_column(sa.Column('vehicle_category_confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('detections', schema=None) as batch_op:
        batch_op.drop_column('vehicle_category_confidence')
        batch_op.drop_column('vehicle_category')
        batch_op.drop_column('vehicle_make_model_confidence')
        batch_op.drop_column('vehicle_model')
        batch_op.drop_column('vehicle_make')

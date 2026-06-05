"""add watchlist and alerts

Revision ID: 316ccbc9e4c0
Revises: c2e5cf756bf2
Create Date: 2026-06-05 20:26:54.280738
"""
from alembic import op
import sqlalchemy as sa


revision = '316ccbc9e4c0'
down_revision = 'c2e5cf756bf2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('watchlist',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('plate_number', sa.String(length=32), nullable=False),
    sa.Column('note', sa.String(length=255), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('watchlist', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_watchlist_plate_number'), ['plate_number'], unique=True)

    op.create_table('alerts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('plate_number', sa.String(length=32), nullable=False),
    sa.Column('detection_id', sa.Integer(), nullable=True),
    sa.Column('stream_id', sa.Integer(), nullable=True),
    sa.Column('message', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('delivered', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['detection_id'], ['detections.id'], ),
    sa.ForeignKeyConstraint(['stream_id'], ['streams.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alerts_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_alerts_detection_id'), ['detection_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_alerts_plate_number'), ['plate_number'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('alerts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alerts_plate_number'))
        batch_op.drop_index(batch_op.f('ix_alerts_detection_id'))
        batch_op.drop_index(batch_op.f('ix_alerts_created_at'))

    op.drop_table('alerts')
    with op.batch_alter_table('watchlist', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_watchlist_plate_number'))

    op.drop_table('watchlist')

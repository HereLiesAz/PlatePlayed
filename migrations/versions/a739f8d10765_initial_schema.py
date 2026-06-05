"""initial schema

Revision ID: a739f8d10765
Revises: 
Create Date: 2026-06-05 13:56:34.514455
"""
from alembic import op
import sqlalchemy as sa


revision = 'a739f8d10765'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('plates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('plate_number', sa.String(length=32), nullable=False),
    sa.Column('first_seen', sa.DateTime(), nullable=False),
    sa.Column('last_seen', sa.DateTime(), nullable=False),
    sa.Column('sightings', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('plates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plates_plate_number'), ['plate_number'], unique=True)

    op.create_table('streams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('url', sa.String(length=512), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('url')
    )
    op.create_table('detections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('plate_id', sa.Integer(), nullable=False),
    sa.Column('stream_id', sa.Integer(), nullable=False),
    sa.Column('plate_number', sa.String(length=32), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('seen_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('frame_path', sa.String(length=512), nullable=True),
    sa.Column('plate_crop_path', sa.String(length=512), nullable=True),
    sa.ForeignKeyConstraint(['plate_id'], ['plates.id'], ),
    sa.ForeignKeyConstraint(['stream_id'], ['streams.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('detections', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_detections_plate_id'), ['plate_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_detections_plate_number'), ['plate_number'], unique=False)
        batch_op.create_index(batch_op.f('ix_detections_seen_at'), ['seen_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_detections_stream_id'), ['stream_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('detections', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_detections_stream_id'))
        batch_op.drop_index(batch_op.f('ix_detections_seen_at'))
        batch_op.drop_index(batch_op.f('ix_detections_plate_number'))
        batch_op.drop_index(batch_op.f('ix_detections_plate_id'))

    op.drop_table('detections')
    op.drop_table('streams')
    with op.batch_alter_table('plates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_plates_plate_number'))

    op.drop_table('plates')

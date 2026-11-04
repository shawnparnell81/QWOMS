"""Independent workbook drafts for the authenticated office editor bridge."""
from alembic import op
import sqlalchemy as sa
revision='0010'
down_revision='0009'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('workbook_drafts',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('work_order_id',sa.Integer(),sa.ForeignKey('work_orders.id'),nullable=False),
        sa.Column('attachment_id',sa.Integer(),sa.ForeignKey('work_order_attachments.id'),nullable=False),
        sa.Column('owner_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('auth_session_id',sa.String(64),sa.ForeignKey('auth_sessions.id'),nullable=False),
        sa.Column('source_file_id',sa.Integer(),sa.ForeignKey('stored_files.id'),nullable=False),
        sa.Column('content',sa.LargeBinary(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('lock_value',sa.String(1024),nullable=False),sa.Column('lock_expires_at',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_workbook_drafts_work_order_id','workbook_drafts',['work_order_id'])

def downgrade():op.drop_table('workbook_drafts')

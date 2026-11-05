"""Recoverable work-order archive. Preserve evidence, history and work-order number."""
from alembic import op
import sqlalchemy as sa

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('work_orders', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('work_orders', sa.Column('archived_by', sa.Integer(), nullable=True))
    op.add_column('work_orders', sa.Column('archive_reason', sa.Text(), nullable=True))
    op.create_index('ix_work_orders_archived_at', 'work_orders', ['archived_at'])

def downgrade():
    # Restoring a database backup, not dropping historical archival records, is the safe rollback.
    connection = op.get_bind()
    if connection.scalar(sa.text('SELECT count(*) FROM work_orders WHERE archived_at IS NOT NULL')):
        raise RuntimeError('Archived work orders exist. Restore a verified backup instead of destructive downgrade.')
    op.drop_index('ix_work_orders_archived_at', table_name='work_orders')
    op.drop_column('work_orders', 'archive_reason')
    op.drop_column('work_orders', 'archived_by')
    op.drop_column('work_orders', 'archived_at')

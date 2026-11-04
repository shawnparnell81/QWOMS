"""Original work-order evidence, template retirement and separate human disposition."""
from alembic import op
import sqlalchemy as sa
revision='0011'
down_revision='0010'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('controlled_documents',sa.Column('retired',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_table('work_order_evidence',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('work_order_id',sa.Integer(),sa.ForeignKey('work_orders.id'),nullable=False),
        sa.Column('part_id',sa.Integer(),sa.ForeignKey('physical_parts.id')),
        sa.Column('filename',sa.String(255),nullable=False),sa.Column('category',sa.String(30),nullable=False),
        sa.Column('media_type',sa.String(100),nullable=False),sa.Column('content',sa.LargeBinary(),nullable=False),
        sa.Column('sha256',sa.String(64),nullable=False),sa.Column('uploaded_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('uploaded_at',sa.DateTime(timezone=True),nullable=False),sa.Column('description',sa.String(2000),nullable=False),
        sa.Column('equipment',sa.String(200),nullable=False),sa.Column('sample',sa.String(100),nullable=False),
        sa.UniqueConstraint('work_order_id','filename',name='uq_order_evidence_filename'))
    op.create_index('ix_work_order_evidence_work_order_id','work_order_evidence',['work_order_id'])
    op.create_table('disposition_events',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('work_order_id',sa.Integer(),sa.ForeignKey('work_orders.id'),nullable=False),
        sa.Column('result',sa.String(30),nullable=False),sa.Column('state',sa.String(30),nullable=False),sa.Column('rationale',sa.Text(),nullable=False),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('request_id',sa.Integer(),sa.ForeignKey('disposition_events.id')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_disposition_events_work_order_id','disposition_events',['work_order_id'])

def downgrade():
    op.drop_table('disposition_events');op.drop_table('work_order_evidence');op.drop_column('controlled_documents','retired')

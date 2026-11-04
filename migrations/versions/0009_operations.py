"""Labor, pallet movement, internal forklift time and approved recoverable costs."""
from alembic import op
import sqlalchemy as sa
revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None

def ident():return sa.Column('id',sa.Integer(),primary_key=True)
def fk(name,table):return sa.Column(name,sa.Integer(),sa.ForeignKey(table+'.id'),nullable=False)
def string(name,size):return sa.Column(name,sa.String(size),nullable=False)

def upgrade():
    op.create_table('labor_entries',ident(),fk('work_order_id','work_orders'),fk('employee_id','users'),string('activity',40),sa.Column('started_at',sa.DateTime(timezone=True),nullable=False),sa.Column('stopped_at',sa.DateTime(timezone=True)),sa.Column('duration_seconds',sa.Integer()),sa.Column('note',sa.Text(),nullable=False),sa.Column('approved_by',sa.Integer(),sa.ForeignKey('users.id')),sa.Column('rate_cents',sa.Integer(),nullable=False),string('department_snapshot',30))
    op.create_index('ix_labor_entries_work_order_id','labor_entries',['work_order_id'])
    op.create_table('pallets',ident(),string('identifier',100),fk('work_order_id','work_orders'),sa.Column('quantity',sa.Integer(),nullable=False),string('original_bin',200),string('location',200),string('disposition',40),string('condition',500),sa.UniqueConstraint('identifier'))
    op.create_index('ix_pallets_work_order_id','pallets',['work_order_id'])
    op.create_table('pallet_movements',ident(),fk('pallet_id','pallets'),fk('actor_id','users'),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),string('previous_location',200),string('location',200),string('disposition',40),string('reason',1000))
    op.create_index('ix_pallet_movements_pallet_id','pallet_movements',['pallet_id'])
    op.create_table('forklift_entries',ident(),fk('work_order_id','work_orders'),fk('recorded_by','users'),sa.Column('duration_seconds',sa.Integer(),nullable=False),sa.Column('estimated',sa.Boolean(),nullable=False),string('note',1000))
    op.create_index('ix_forklift_entries_work_order_id','forklift_entries',['work_order_id'])
    op.create_table('charge_items',ident(),fk('work_order_id','work_orders'),fk('created_by','users'),string('category',40),string('description',1000),sa.Column('quantity',sa.Integer(),nullable=False),sa.Column('unit_cents',sa.Integer(),nullable=False),sa.Column('approved_by',sa.Integer(),sa.ForeignKey('users.id')))
    op.create_index('ix_charge_items_work_order_id','charge_items',['work_order_id'])

def downgrade():
    for table in ['charge_items','forklift_entries','pallet_movements','pallets','labor_entries']:op.drop_table(table)

"""Separate system authority from departments; never inherit employee grants."""
from alembic import op
import sqlalchemy as sa
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('is_admin',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('users',sa.Column('permissions',sa.JSON(),nullable=False,server_default='[]'))
    table=op.create_table('system_authority',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('initialized',sa.Boolean(),nullable=False))
    op.bulk_insert(table,[{'id':1,'initialized':False}])

def downgrade():
    op.drop_table('system_authority')
    op.drop_column('users','permissions')
    op.drop_column('users','is_admin')

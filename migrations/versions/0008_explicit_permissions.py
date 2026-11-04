"""Deny-by-default administrator and individual capabilities; no role promotion."""
from alembic import op
import sqlalchemy as sa
revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('is_admin',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('users',sa.Column('capabilities',sa.JSON(),nullable=False,server_default='[]'))

def downgrade():
    op.drop_column('users','capabilities')
    op.drop_column('users','is_admin')

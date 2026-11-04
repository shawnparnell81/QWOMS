"""Preserve remote one-time password setup on the canonical local migration chain.

This does not reconcile divergent live/local 0008/0009 permission/operations schemas.
No live upgrade is authorized until clone migration/rollback rehearsal succeeds.
"""
from alembic import op
import sqlalchemy as sa
revision='0012'
down_revision='0011'
branch_labels=None
depends_on=None

def upgrade():
    if 'must_change_password' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}:
        op.add_column('users',sa.Column('must_change_password',sa.Boolean(),nullable=False,server_default=sa.false()))

def downgrade():
    op.drop_column('users','must_change_password')

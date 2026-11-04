"""Force a password change after the one-time synthetic-demo owner login.

All existing accounts default to False; only the intentional first-login demo
transition sets this flag. Production owner bootstrapping is unchanged.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(),
                                    nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column("users", "must_change_password")

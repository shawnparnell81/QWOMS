"""Reconcile the legacy hosted permission/password history without losing grants.

Legacy 0008 used users.permissions + system_authority. Legacy 0009 added only
must_change_password, whereas canonical 0009 adds operations. Preserve original
permission/authority data in a system migration ledger; never infer role grants.
"""
from datetime import datetime,timezone
from pathlib import Path
import runpy
from alembic import op,context
import sqlalchemy as sa
revision='0013'
down_revision='0012'
branch_labels=None
depends_on=None

MAPPING={
    'import.parts':['import.part_master'],
    'import.drawings':['import.drawings'],
    'import.documents':['import.work_instructions','import.supporting_documents'],
    'import.templates':['import.form_masters'],
    'revision.approve':['engineering.approve'],
    'import.part_master':['import.part_master'],
    'import.form_masters':['import.form_masters'],
    'import.work_instructions':['import.work_instructions'],
    'import.supporting_documents':['import.supporting_documents'],
    'import.other':['import.other'],
    'engineering.approve':['engineering.approve'],
}
OPERATIONS={'labor_entries','pallets','pallet_movements','forklift_entries','charge_items'}


def upgrade():
    connection=op.get_bind();inspector=sa.inspect(connection)
    columns={c['name'] for c in inspector.get_columns('users')};tables=set(inspector.get_table_names())
    legacy='permissions' in columns
    if legacy:
        if 'capabilities' in columns or 'is_admin' not in columns or 'system_authority' not in tables:
            raise RuntimeError('Ambiguous permission schema; restore/review the clone before migration')
        if connection.dialect.name=='postgresql':
            connection.execute(sa.text('LOCK TABLE users, system_authority IN ACCESS EXCLUSIVE MODE'))
        users=sa.Table('users',sa.MetaData(),autoload_with=connection)
        authority=sa.Table('system_authority',sa.MetaData(),autoload_with=connection)
        originals=connection.execute(sa.select(users.c.id,users.c.permissions,users.c.is_admin)).mappings().all()
        converted=[]
        for row in originals:
            permissions=row['permissions']
            if not isinstance(permissions,list) or any(not isinstance(p,str) or p not in MAPPING for p in permissions):
                raise RuntimeError('Unrecognized legacy permissions; no migration changes committed. Review the explicit mapping')
            converted.append({'user_id':row['id'],'before':permissions,'after':sorted({new for old in permissions for new in MAPPING[old]}),'is_admin_before':bool(row['is_admin']),'is_admin_after':bool(row['is_admin'])})
        authority_rows=[dict(r) for r in connection.execute(sa.select(authority)).mappings()]
        present=OPERATIONS & tables
        if present and present!=OPERATIONS:raise RuntimeError('Partial operations schema; no migration changes committed. Manual review required')
    elif 'capabilities' not in columns or 'system_authority' in tables or not OPERATIONS.issubset(tables):
        raise RuntimeError('Unrecognized canonical schema; no migration changes committed. Manual review required')
    ledger=op.create_table('schema_reconciliations',sa.Column('id',sa.String(50),primary_key=True),
        sa.Column('source_revisions',sa.JSON(),nullable=False),sa.Column('target_revision',sa.String(32),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('report',sa.JSON(),nullable=False))
    if not legacy:return
    # A single explicit legacy documents grant included both categories. Split
    # that exact existing authority; never give it to ungranted employees/roles.
    op.alter_column('users','permissions',new_column_name='capabilities',existing_type=sa.JSON(),existing_nullable=False)
    updated=sa.Table('users',sa.MetaData(),autoload_with=connection)
    for row in converted:
        connection.execute(updated.update().where(updated.c.id==row['user_id']).values(capabilities=row['after']))
    created_operations=not bool(present)
    if created_operations:
        # Execute the immutable historical migration, not current ORM models.
        runpy.run_path(str(Path(__file__).with_name('0009_operations.py')))['upgrade']()
    connection.execute(ledger.insert().values(id='legacy_permissions_0013',
        source_revisions=list(context.config.attributes.get('qwoms_source_revisions',[])),target_revision=revision,
        created_at=datetime.now(timezone.utc),report={
            'executor':'database_migration','mapping_policy':'explicit-legacy-grants-only-v1',
            'permission_changes':converted,'legacy_authority':authority_rows,
            'operations_created_by_reconciliation_step':created_operations,'rollback':'Restore the verified pre-upgrade database and original-file backup; do not downgrade live data.'}))
    # All original initialization rows survive in the ledger. Canonical first-
    # owner protection uses serialized existing Administrator rows, not a marker.
    op.drop_table('system_authority')


def downgrade():
    connection=op.get_bind()
    count=connection.scalar(sa.text('SELECT count(*) FROM schema_reconciliations'))
    if count:
        raise RuntimeError('Legacy reconciliation requires restoring the verified pre-upgrade backup; destructive downgrade is refused')
    op.drop_table('schema_reconciliations')

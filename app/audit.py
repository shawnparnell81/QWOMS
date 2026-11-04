"""Append-only through application APIs; never record passwords, tokens, or message bodies."""
from .models import AuditEvent


def record(db, actor, action, entity_type, entity_id, changes=None):
    db.add(AuditEvent(actor_id=actor.id, action=action, entity_type=entity_type,
                      entity_id=str(entity_id), changes=changes or {}))

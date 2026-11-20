"""
Keep MEDIA_ROOT in step with the database.

Django deliberately does not remove the file behind a FileField when the row is
deleted , deleting a row in a transaction that later rolls back would otherwise
destroy the file for good. That safety leaves orphans, so clean them up here
instead, once the delete has actually happened.
"""

import logging
import os

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from core.models import InstanceDataFile, InstanceDatasetFile, UsecaseDataFile

log = logging.getLogger("core")


def _remove_file(field_file):
    if not field_file:
        return
    try:
        path = field_file.path
    except (ValueError, NotImplementedError):
        return  # not a local filesystem storage

    def cleanup():
        try:
            if os.path.isfile(path):
                os.remove(path)
                # Uploads live one directory per record, so the parent is now
                # empty; leave it only if something else put a file there.
                parent = os.path.dirname(path)
                if os.path.isdir(parent) and not os.listdir(parent):
                    os.rmdir(parent)
        except OSError as exc:
            log.warning("Could not remove %s: %s", path, exc)

    # Only once the delete is committed , a rolled-back transaction must not
    # take the file with it.
    transaction.on_commit(cleanup)


@receiver(post_delete, sender=UsecaseDataFile)
@receiver(post_delete, sender=InstanceDataFile)
@receiver(post_delete, sender=InstanceDatasetFile)
def delete_uploaded_file(sender, instance, **kwargs):
    _remove_file(instance.file)

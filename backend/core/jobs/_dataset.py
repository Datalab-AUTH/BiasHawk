"""Shared dataset loading for job handlers."""

import logging

import pandas as pd

from core.models import InstanceDatasetFile

log = logging.getLogger("core.jobs")


def load_dataset(instance, kind=InstanceDatasetFile.SOURCE):
    """
    Read an instance's CSV off disk into a DataFrame.

    Every analysis service in the old backend did this over HTTP against
    BACKEND_MEDIA_URL, then asserted the URL started with "http" and ended with
    the expected filename. Same process, same disk, so none of that is needed.
    """
    dataset = (
        InstanceDatasetFile.objects.filter(instance=instance, kind=kind)
        .order_by("-created_at")
        .first()
    )
    if dataset is None:
        raise ValueError(f"Instance {instance.id} has no {kind} dataset.")

    log.info("Reading %s for instance %s", dataset.file.name, instance.id)
    with dataset.file.open("rb") as handle:
        return pd.read_csv(handle), dataset

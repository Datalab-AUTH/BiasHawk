#!/usr/bin/env bash
#
# The job runner. Same image as the API, different command.
#
# It does not migrate , compose gates this container on the API being healthy,
# which happens after the API has migrated.
#
# `exec` makes runjobs PID 1, so if it dies the container dies and Docker's
# restart policy brings it back. The API is a separate container and is not
# affected.
#
set -euo pipefail

echo "==> Starting job runner (${JOB_THREADS:-8} threads)"
exec python manage.py runjobs

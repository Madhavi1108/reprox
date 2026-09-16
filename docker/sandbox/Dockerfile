# Reference image for REPROX's execution sandbox (Phase 17, spec section 46).
#
# NOT built or run in the development session that authored this file - no
# Docker daemon was available there. See docs/EXECUTION_SANDBOX.md for the
# verification limitation. Build/run manually once a daemon is available:
#   docker build -t reprox-sklearn-runner:latest -f docker/sandbox/Dockerfile .
#
# Runs as a non-root user; expects /workload (read-only) and /output
# (read-write) to be bind-mounted by app.sandbox.runner.SandboxRunner.
FROM python:3.11-slim

RUN pip install --no-cache-dir \
    scikit-learn==1.5.* \
    pandas==2.2.* \
    numpy==1.26.*

RUN useradd --create-home --uid 10001 sandbox
USER sandbox
WORKDIR /output

ENTRYPOINT ["python"]

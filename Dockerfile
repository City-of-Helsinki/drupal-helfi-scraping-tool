# Use an official Python runtime as a parent image
FROM python:3.14-alpine

# Set environment variables (e.g., to make Python not write .pyc files)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create and set working directory. The repository is bind mounted over it at
# runtime, so this is also the directory a run writes its results into.
WORKDIR /usr/src

# Install the tool, and with it the dependencies from pyproject.toml. The
# install is editable, so the mounted copy of the code is what actually runs and
# an edit takes effect without a rebuild. README and LICENSE are copied because
# the package metadata names them.
COPY pyproject.toml README.md LICENSE ./
COPY app ./app
RUN \
    set -eux; \
    apk add --no-cache --virtual .py_deps build-base python3-dev libffi-dev; \
    pip install --no-cache-dir -e .; \
    apk del .py_deps;

ENTRYPOINT ["scraping-tool"]

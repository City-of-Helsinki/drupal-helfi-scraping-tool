# Use an official Python runtime as a parent image
FROM python:3.14-alpine

# Set environment variables (e.g., to make Python not write .pyc files)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV XDG_CONFIG_HOME=/config
ENV XDG_DATA_HOME=/data
RUN mkdir -p /config /data && chmod 0777 /config /data

# The repository is bind mounted over working directory at
# runtime.
WORKDIR /usr/src

# Install the tool and dependencies from pyproject.toml.
COPY pyproject.toml README.md LICENSE ./
COPY app ./app
RUN \
    set -eux; \
    apk add --no-cache --virtual .py_deps build-base libffi-dev; \
    pip install --no-cache-dir -e .; \
    apk del .py_deps;

ENTRYPOINT ["scraping-tool"]

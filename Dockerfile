# Use an official Python runtime as a parent image
FROM python:3.14-alpine

# Set environment variables (e.g., to make Python not write .pyc files)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create and set working directory
WORKDIR /usr/src/app

# Install any needed packages specified in requirements.txt
COPY docker/requirements.txt ./
RUN \
    set -eux; \
    apk add --no-cache --virtual .py_deps build-base python3-dev libffi-dev; \
    pip install --no-cache-dir -r requirements.txt; \
    apk del .py_deps;

# The application itself is bind mounted over /usr/src/app at runtime.
ENTRYPOINT ["python", "/usr/src/app/cli.py"]

# Use an official Python runtime as a parent image
FROM python:3.11.4

# Set environment variables (e.g., to make Python not write .pyc files)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create and set working directory
WORKDIR /usr/src/app

# Install any needed packages specified in requirements.txt
COPY docker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entrypoint script and make it executable
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Copy the rest of the code into the image
COPY . .

# Set the entrypoint script as the default command to execute
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

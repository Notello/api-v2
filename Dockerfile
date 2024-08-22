# Use an official Python runtime as the base image
FROM python:3.11.4-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "6", "--threads", "4", "--worker-class", "gthread", "--max-requests", "1000", "--max-requests-jitter", "50", "app:app"]
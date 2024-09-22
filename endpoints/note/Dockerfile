# Include python 3.11
FROM python:3.11

# Set shell and noninteractive environment variables
SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash

# Take in github token
ARG ghtoken

# Copy the main file into the image

COPY main.py .

# Copy requirements file

COPY requirements.txt .

# Install python dependencies

RUN pip install -r requirements.txt

# Run main.py when the container launches

CMD ["python", "main.py"]

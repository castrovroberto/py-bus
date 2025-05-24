# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container at /usr/src/app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /usr/src/app
# This includes config.yaml if it's in the gateway directory
COPY . .

# Make port (if any directly exposed by gateway itself, usually not needed)
# EXPOSE 8080 

# Define environment variable
ENV PYTHONUNBUFFERED 1

# Run main.py when the container launches
# Default to using config.yaml from the current directory in the container
CMD ["python", "main.py", "--config", "config.yaml"] 
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container at /usr/src/app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV PYTHONUNBUFFERED 1

# Run Uvicorn server when the container launches
# CMD ["python", "main.py"] # This would run the if __name__ == "__main__": block
# For production, it's better to run uvicorn directly:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 
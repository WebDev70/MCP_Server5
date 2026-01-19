FROM python:3.12-slim

WORKDIR /app

# Install dependencies
RUN pip install fastapi uvicorn

# Copy app code
COPY app.py .
COPY fixtures/ fixtures/

# Expose port
EXPOSE 8081

# Run the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]

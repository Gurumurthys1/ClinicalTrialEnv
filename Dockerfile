FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Expose HF Spaces port
EXPOSE 7860

# Start server
CMD ["uvicorn", "clinical_trial_env.server.app:app", "--host", "0.0.0.0", "--port", "7860"]

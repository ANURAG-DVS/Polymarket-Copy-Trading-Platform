# ==============================================
# Dockerfile for Telegram Bot
# ==============================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

# Copy application code
COPY --chown=botuser:botuser . .

# Switch to non-root user
USER botuser

# Run bot
CMD ["python", "-m", "bot.main"]

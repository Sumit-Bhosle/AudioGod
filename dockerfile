# Use official Python base image
FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Set workdir
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (not needed for Telegram bot, but good practice)
EXPOSE 8080

# Run your bot
CMD ["python", "bot.py"]

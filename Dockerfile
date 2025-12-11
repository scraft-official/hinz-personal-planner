FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt ./

# Create a non-root user and group for running pip/installing packages
# Install packages into the user's local directory using --user so pip does not run as root
RUN useradd --create-home --shell /bin/bash app \
	&& mkdir -p /app

# Switch to non-root user for pip install to avoid running pip as root
USER app
ENV PATH=/home/app/.local/bin:$PATH

RUN pip install --user --no-cache-dir -r requirements.txt

# Switch back to root to copy application files and set ownership
USER root
COPY app ./app
RUN chown -R app:app /app

# Run as the non-root app user
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

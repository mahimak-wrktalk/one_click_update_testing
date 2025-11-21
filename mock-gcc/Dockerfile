FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mock_gcc.py .

RUN chmod +x mock_gcc.py

# Run as non-root user
RUN useradd -m -u 1000 gcc && \
    chown -R gcc:gcc /app
USER gcc

EXPOSE 5000

CMD ["python", "-u", "mock_gcc.py"]

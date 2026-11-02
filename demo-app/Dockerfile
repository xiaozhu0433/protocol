FROM python:3.12-slim

WORKDIR /app
COPY demo-app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY hormone /app/hormone
COPY memory /app/memory
COPY demo-app /app/demo-app

WORKDIR /app/demo-app
ENV HOST=0.0.0.0 PORT=8000 DEMO_DATA=/data
VOLUME ["/data"]
EXPOSE 8000
CMD ["python3", "app.py"]
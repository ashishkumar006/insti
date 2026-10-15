FROM python:3.11-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY web ./web
# Render/Koyeb/etc inject a dynamic PORT; default keeps local `docker run` working.
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8200}"]

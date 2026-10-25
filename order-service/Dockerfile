FROM python:3.13-slim
WORKDIR /app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app && mkdir /data && chown app:app /data
COPY --chown=app:app app.py common.py ./
USER 10001:10001
ENV HOST=0.0.0.0 PORT=8000 DB_PATH=/data/service.db PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=2)"]
CMD ["python", "app.py"]

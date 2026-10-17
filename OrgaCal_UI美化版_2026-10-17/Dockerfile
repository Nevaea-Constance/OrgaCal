FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 GRADIO_SERVER_PORT=7860 \
    GRADIO_ANALYTICS_ENABLED=False MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 7860
CMD ["python", "app.py"]

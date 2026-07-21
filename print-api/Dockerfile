# Imagem do CARA 2: API que so printa o que recebe
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# usuario nao-root (o container nao deve rodar como root)
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 9000

# checagem de saude da API
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health')" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]

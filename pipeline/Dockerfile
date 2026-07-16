# Imagem do orquestrador (pipeline). Roda uma vez e termina.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run_pipeline.py verify_infra.py ./

CMD ["python", "run_pipeline.py"]

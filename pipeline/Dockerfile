# Imagem do orquestrador (pipeline). Roda uma vez e termina.
# Job one-shot: nao expoe servico, entao nao ha HEALTHCHECK a checar.
#checkov:skip=CKV_DOCKER_2:job one-shot, sem servico HTTP para checar saude
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run_pipeline.py verify_infra.py ./

# usuario nao-root (o container nao deve rodar como root)
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

CMD ["python", "run_pipeline.py"]

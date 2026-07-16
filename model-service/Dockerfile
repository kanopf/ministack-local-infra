# Imagem do CARA 1: servico de inferencia
FROM python:3.12-slim

WORKDIR /app

# 1) instala dependencias primeiro (cache de camada melhor)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) treina o modelo NA HORA DO BUILD e "assa" o model.pkl na imagem
COPY train.py .
RUN python train.py

# 3) copia o app de serving
COPY app.py .

EXPOSE 8000

# sobe o servidor de inferencia
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

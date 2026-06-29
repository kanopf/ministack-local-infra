"""
print-api (CARA 2).

Faz uma coisa so: recebe um JSON em POST /results e PRINTA no log.
Simula um "consumidor final" da pipeline (poderia ser um dashboard,
um alerta, outra fila etc.).
"""
import json
from fastapi import FastAPI, Request

app = FastAPI(title="print-api", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/results")
async def results(request: Request):
    payload = await request.json()
    print("=" * 60, flush=True)
    print("[print-api] RESULTADO RECEBIDO:", flush=True)
    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    print("=" * 60, flush=True)
    return {"received": True}

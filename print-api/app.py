"""
print-api (CARA 2).

- POST /results : recebe um JSON, guarda em memoria e printa no log
- GET  /        : pagina HTML mostrando os resultados recebidos (pro navegador)
- GET  /results : os resultados recebidos, em JSON
- GET  /health  : checagem de saude
- GET  /docs    : Swagger UI (gerado automaticamente pelo FastAPI)
"""

import json
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="print-api", version="2.0.0")

# guarda em memoria tudo que chega (some quando o container reinicia)
_recebidos: list[dict] = []


@app.get("/health")
def health():
    return {"status": "ok", "total": len(_recebidos)}


@app.post("/results")
async def results(request: Request):
    payload = await request.json()
    registro = {
        "recebido_em": datetime.now().isoformat(timespec="seconds"),
        "payload": payload,
    }
    _recebidos.append(registro)

    print("=" * 60, flush=True)
    print("[print-api] RESULTADO RECEBIDO:", flush=True)
    print(json.dumps(payload, indent=2, ensure_ascii=False), flush=True)
    print("=" * 60, flush=True)
    return {"received": True, "total": len(_recebidos)}


@app.get("/results")
def listar():
    return _recebidos


@app.get("/", response_class=HTMLResponse)
def home():
    linhas = ""
    for r in _recebidos:
        p = r["payload"]
        linhas += (
            "<tr>"
            f"<td>{r['recebido_em']}</td>"
            f"<td>{p.get('id', '')}</td>"
            f"<td>{p.get('features', '')}</td>"
            f"<td><b>{p.get('prediction', '')}</b></td>"
            "</tr>"
        )
    if not linhas:
        linhas = (
            '<tr><td colspan="4">Nenhum resultado ainda. Rode a pipeline.</td></tr>'
        )

    return f"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="3">  <!-- recarrega a cada 3s -->
  <title>print-api &middot; resultados</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background:#0f172a; color:#e2e8f0; }}
    h1 {{ font-size: 1.4rem; }}
    .total {{ color:#38bdf8; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #334155; padding: .5rem .75rem; text-align: left; }}
    th {{ background:#1e293b; }}
    tr:nth-child(even) td {{ background:#162033; }}
    b {{ color:#4ade80; }}
    small {{ color:#94a3b8; }}
  </style>
</head>
<body>
  <h1>print-api &middot; <span class="total">{len(_recebidos)}</span> resultado(s) recebido(s)</h1>
  <small>Atualiza sozinho a cada 3s. JSON cru em <code>/results</code> &middot; Swagger em <code>/docs</code></small>
  <table>
    <thead>
      <tr><th>Recebido em</th><th>id</th><th>features</th><th>prediction</th></tr>
    </thead>
    <tbody>
      {linhas}
    </tbody>
  </table>
</body>
</html>"""

"""
Servico de inferencia (CARA 1).

Sobe um HTTP server com:
  GET  /health   -> checagem de saude
  POST /predict  -> recebe features e devolve a predicao

Carrega o model.pkl que foi treinado e "assado" na imagem (ver train.py).
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import joblib
import numpy as np

app = FastAPI(title="model-service", version="1.0.0")

# carrega o artefato uma unica vez, no startup
_bundle = joblib.load("model.pkl")
_model = _bundle["model"]
_n_features = _bundle["n_features"]


class PredictRequest(BaseModel):
    # lista de numeros, ex: [1.0, 2.0, 3.0]
    features: list[float] = Field(..., description="vetor de features")


class PredictResponse(BaseModel):
    prediction: float
    n_features: int


@app.get("/health")
def health():
    return {"status": "ok", "n_features": _n_features}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if len(req.features) != _n_features:
        raise HTTPException(
            status_code=400,
            detail=f"esperado {_n_features} features, recebido {len(req.features)}",
        )
    x = np.array(req.features, dtype=float).reshape(1, -1)
    y = float(_model.predict(x)[0])
    return PredictResponse(prediction=y, n_features=_n_features)

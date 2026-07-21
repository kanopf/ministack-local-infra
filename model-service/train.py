"""
Treina um modelo de predicao GENERICO para teste e salva em model.pkl.

Ideia: relacao linear sintetica  y = 3*x0 + 2*x1 - 1*x2 + ruido.
Nao importa o dominio real -- a graca aqui e ter um artefato de modelo
treinado, salvo em disco, que sera "assado" dentro da imagem Docker.
Esse e o padrao real de serving: treina offline -> salva artefato -> serve.
"""

import numpy as np
from sklearn.linear_model import LinearRegression
import joblib

# semente fixa => modelo reproduzivel a cada build
rng = np.random.default_rng(42)

# 500 amostras, 3 features
N_FEATURES = 3
X = rng.normal(size=(500, N_FEATURES))
coef_verdadeiro = np.array([3.0, 2.0, -1.0])
y = X @ coef_verdadeiro + rng.normal(scale=0.1, size=500)

modelo = LinearRegression()
modelo.fit(X, y)

print(f"[train] coeficientes aprendidos: {modelo.coef_}")
print(f"[train] intercepto: {modelo.intercept_:.4f}")
print(f"[train] R^2 no treino: {modelo.score(X, y):.4f}")

joblib.dump({"model": modelo, "n_features": N_FEATURES}, "model.pkl")
print("[train] modelo salvo em model.pkl")

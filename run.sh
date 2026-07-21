#!/usr/bin/env bash
#
# Sobe a infra inteira e roda o fluxo fim a fim, em UM comando.
# Uso (dentro do WSL):   bash run.sh
#
set -euo pipefail
cd "$(dirname "$0")" || exit 1

echo "==> 1/4  build + subir infra (ministack, model-service, print-api)"
docker compose up -d --build

echo "==> 2/4  aguardando o MiniStack ficar pronto..."
for _ in $(seq 1 30); do
  if curl -sf http://localhost:4566/_ministack/health >/dev/null 2>&1; then
    echo "    MiniStack pronto."
    break
  fi
  sleep 1
done

echo "==> 3/4  Terraform: criar bucket S3 + tabela DynamoDB + seed"
cd terraform || exit 1
terraform init -input=false >/dev/null
terraform apply -auto-approve
cd .. || exit 1

echo "==> 4/4  rodando a pipeline (one-shot)"
docker compose run --rm pipeline

echo
echo "================= LOGS DA PRINT-API ================="
docker compose logs print-api | tail -30
echo
echo "Pronto! Para derrubar tudo:  docker compose down"

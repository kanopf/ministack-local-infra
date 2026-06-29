"""
PIPELINE (orquestrador).

Fluxo:
  1. LE os dados da tabela DynamoDB (input-data) no MiniStack
  2. GRAVA o dado bruto no bucket S3 (raw/<id>.json)
  3. RODA a inferencia chamando o model-service (POST /predict)
  4. GRAVA a predicao no bucket S3 (predictions/<id>.json)
  5. ENVIA o resultado para a print-api (POST /results), que printa

Endpoints sao configuraveis por env var para funcionar tanto rodando
no host (localhost) quanto dentro da rede Docker (nome do container).
"""
import os
import json
import boto3
import requests

MINISTACK_ENDPOINT = os.environ.get("MINISTACK_ENDPOINT", "http://localhost:4566")
MODEL_URL = os.environ.get("MODEL_URL", "http://localhost:8000")
PRINT_API_URL = os.environ.get("PRINT_API_URL", "http://localhost:9000")

TABLE_NAME = os.environ.get("TABLE_NAME", "input-data")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "ml-predictions")

aws_common = dict(
    endpoint_url=MINISTACK_ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
s3 = boto3.client("s3", **aws_common)
ddb = boto3.client("dynamodb", **aws_common)


def put_json(key: str, obj: dict):
    """grava um dict como JSON no bucket S3."""
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(obj).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"  [s3] gravado s3://{BUCKET_NAME}/{key}")


def main():
    print(f"[pipeline] MiniStack : {MINISTACK_ENDPOINT}")
    print(f"[pipeline] modelo    : {MODEL_URL}")
    print(f"[pipeline] print-api : {PRINT_API_URL}")
    print(f"[pipeline] tabela    : {TABLE_NAME}  | bucket: {BUCKET_NAME}\n")

    # 1) le todas as linhas da tabela
    items = ddb.scan(TableName=TABLE_NAME).get("Items", [])
    print(f"[pipeline] {len(items)} linhas lidas da tabela\n")

    for it in items:
        rec_id = it["id"]["S"]
        features = json.loads(it["features"]["S"])  # ex: [1.0, 2.0, 3.0]
        print(f"[pipeline] processando {rec_id}  features={features}")

        # 2) grava o dado bruto no bucket
        put_json(f"raw/{rec_id}.json", {"id": rec_id, "features": features})

        # 3) roda a inferencia chamando o modelo
        r = requests.post(f"{MODEL_URL}/predict", json={"features": features}, timeout=10)
        r.raise_for_status()
        prediction = r.json()["prediction"]
        print(f"  [model] prediction={prediction:.4f}")

        # 4) grava a predicao no bucket
        result = {"id": rec_id, "features": features, "prediction": prediction}
        put_json(f"predictions/{rec_id}.json", result)

        # 5) envia o resultado para a print-api
        pr = requests.post(f"{PRINT_API_URL}/results", json=result, timeout=10)
        pr.raise_for_status()
        print(f"  [print-api] enviado (status {pr.status_code})\n")

    print("[pipeline] CONCLUIDO.")


if __name__ == "__main__":
    main()

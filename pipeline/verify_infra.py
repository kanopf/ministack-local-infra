"""Confere que o bucket e a tabela existem de verdade no MiniStack."""
import os
import boto3

# Dentro da rede Docker use http://ministack:4566 (nome do container);
# rodando direto no host use http://localhost:4566.
ENDPOINT = os.environ.get("MINISTACK_ENDPOINT", "http://localhost:4566")
common = dict(
    endpoint_url=ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

s3 = boto3.client("s3", **common)
ddb = boto3.client("dynamodb", **common)

print("=== S3 buckets ===")
for b in s3.list_buckets().get("Buckets", []):
    print(" -", b["Name"])

print("\n=== DynamoDB tabelas ===")
for t in ddb.list_tables().get("TableNames", []):
    print(" -", t)

print("\n=== Conteudo da tabela input-data ===")
resp = ddb.scan(TableName="input-data")
for item in resp.get("Items", []):
    print(" -", item["id"]["S"], "->", item["features"]["S"])

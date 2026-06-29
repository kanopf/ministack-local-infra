terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Provider AWS apontando para o MiniStack (porta unica 4566).
# Credenciais sao ficticias: localmente nao ha validacao real de SigV4.
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true # nao valida credenciais na AWS real
  skip_metadata_api_check     = true # nao tenta o endpoint de metadata da EC2
  skip_requesting_account_id  = true # nao chama STS para descobrir o account id
  s3_use_path_style           = true # http://host:4566/bucket em vez de http://bucket.host

  # redireciona CADA servico para o MiniStack
  endpoints {
    s3       = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
  }
}

# ---------------------------------------------------------------------------
# CARA 3 (parte 1): o BUCKET S3 onde vamos guardar os dados/resultados
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "predictions" {
  bucket = var.bucket_name
}

# ---------------------------------------------------------------------------
# A TABELA de entrada (a "tabela em algum banco" de onde a pipeline le)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "input_data" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST" # sem provisionar capacidade (modo on-demand)
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S" # string
  }
}

# Semeia algumas linhas na tabela via IaC.
# 'features' guarda um JSON (string) com o vetor de entrada do modelo.
locals {
  seed_items = {
    "rec-001" = "[1.0, 2.0, 3.0]"
    "rec-002" = "[0.0, 0.0, 0.0]"
    "rec-003" = "[5.0, -1.0, 2.0]"
    "rec-004" = "[-2.0, 4.0, 1.0]"
  }
}

resource "aws_dynamodb_table_item" "seed" {
  for_each   = local.seed_items
  table_name = aws_dynamodb_table.input_data.name
  hash_key   = aws_dynamodb_table.input_data.hash_key

  item = jsonencode({
    id       = { S = each.key }
    features = { S = each.value }
  })
}

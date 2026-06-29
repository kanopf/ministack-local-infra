variable "bucket_name" {
  description = "Nome do bucket S3 para guardar dados/predicoes"
  type        = string
  default     = "ml-predictions"
}

variable "table_name" {
  description = "Nome da tabela DynamoDB de entrada"
  type        = string
  default     = "input-data"
}

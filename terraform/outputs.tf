output "bucket_name" {
  description = "Bucket S3 criado"
  value       = aws_s3_bucket.predictions.bucket
}

output "table_name" {
  description = "Tabela DynamoDB criada"
  value       = aws_dynamodb_table.input_data.name
}

output "seeded_ids" {
  description = "IDs semeados na tabela"
  value       = keys(local.seed_items)
}

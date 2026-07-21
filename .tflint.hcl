# Configuracao do tflint compartilhada pela IDE e pelo CI (MegaLinter).
# Preset "recommended" do plugin terraform (built-in, sem download externo):
# valida required_version/providers, variaveis/outputs documentados e tipados,
# nomes em snake_case e declaracoes nao utilizadas.
plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

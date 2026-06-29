# ministack-local-infra

Lab de aprendizado **self-contained**: uma mini-infra de ML rodando 100%
local com [MiniStack](https://ministack.org/) (emulador AWS open-source).

Simula um fluxo típico: ler dados de uma tabela, gravar num bucket, rodar
inferência num modelo e entregar o resultado para um consumidor — tudo
sem custo e sem AWS de verdade.

## TL;DR — rodar tudo com um comando

Pré-requisito: **Docker** e **Terraform** disponíveis (ex.: dentro do WSL).

```bash
bash run.sh
```

Isso faz: build das imagens → sobe a infra → Terraform cria bucket/tabela →
roda a pipeline → mostra o que a print-api recebeu. Para derrubar:

```bash
docker compose down
```

## Arquitetura

```
   ┌────────────┐   1. lê da tabela (DynamoDB)
   │  MiniStack │◄──────────────┐
   │   :4566    │   2. grava no bucket (S3)
   │ S3+DynamoDB│◄───────────┐  │
   └────────────┘            │  │
                        ┌────┴──┴─────┐
   ┌────────────┐  3a   │  pipeline   │
   │   modelo   │◄──────┤ (orquestra) │
   │   :8000    │       └──────┬──────┘
   │ /predict   │              │ 3b
   └────────────┘              ▼
                        ┌────────────┐
                        │  print-api │ ← printa o resultado
                        │   :9000    │
                        └────────────┘
```

| Componente      | Papel                                            | Porta |
|-----------------|--------------------------------------------------|-------|
| `ministack`     | Emulador AWS (S3 + DynamoDB) numa porta só       | 4566  |
| `model-service` | CARA 1 — modelo scikit-learn servindo `/predict` | 8000  |
| `print-api`     | CARA 2 — recebe o resultado e printa             | 9000  |
| `pipeline`      | Orquestrador one-shot do fluxo                   | —     |

O modelo é genérico: regressão linear em dados sintéticos
(`y = 3·x0 + 2·x1 − 1·x2 + ruído`), treinada **no build** e "assada" na imagem.

## Estrutura do repositório

```
ministack-local-infra/
├── README.md
├── run.sh                  roda tudo em um comando
├── docker-compose.yml      builda e sobe ministack + os 3 caras
├── terraform/              IaC: bucket S3 + tabela DynamoDB + seed de dados
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── model-service/          CARA 1 — modelo
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── train.py            treina e salva model.pkl no build
│   └── app.py              FastAPI: /health e /predict
├── print-api/              CARA 2 — consumidor que printa
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py              FastAPI: /results
└── pipeline/               orquestrador
    ├── Dockerfile
    ├── requirements.txt
    ├── run_pipeline.py     o fluxo (tabela -> S3 -> modelo -> print-api)
    └── verify_infra.py     util: confere bucket/tabela
```

## Passo a passo manual (se quiser entender por dentro)

```bash
# 1) build + subir os 3 caras
docker compose up -d --build

# 2) criar bucket + tabela + seed
cd terraform && terraform init && terraform apply -auto-approve && cd ..

# 3) rodar a pipeline (job one-shot na rede do compose)
docker compose run --rm pipeline

# 4) ver o que a print-api recebeu
docker compose logs print-api

# (opcional) conferir a infra
docker compose run --rm pipeline python verify_infra.py
```

> Rodando no WSL com o repo num caminho com espaços? Use
> `wsl --cd "C:\...\ministack-local-infra" -- bash run.sh` para evitar
> problemas de quoting.

## Como funciona o MiniStack (resumo)
A AWS é só um conjunto de APIs HTTP. O MiniStack é um único servidor que
finge ser todos os serviços na porta **4566**. Os SDKs (boto3, Terraform)
identificam o serviço pelo nome embutido na assinatura **SigV4** do header
`Authorization`, e o MiniStack roteia internamente — por isso tudo cabe numa
porta. Credenciais são fictícias (`test`/`test`): localmente não há validação
real de assinatura. S3 e DynamoDB rodam em memória (rápidos e leves), então
ao dar `docker compose down` os dados somem — basta rodar o Terraform de novo.

## Limpeza
```bash
docker compose down
cd terraform && terraform destroy -auto-approve
```

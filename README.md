# ministack-local-infra

Lab de aprendizado **self-contained**: uma mini-infra de ML rodando 100%
local com [MiniStack](https://ministack.org/) (emulador AWS open-source).

Simula um fluxo típico: ler dados de uma tabela, gravar num bucket, rodar
inferência num modelo e entregar o resultado para um consumidor — tudo
sem custo e sem AWS de verdade.

> 📖 Quer entender **como tudo funciona por dentro** e o que cada passo faz?
> Veja [EXPLICACAO.md](EXPLICACAO.md) — explicação detalhada peça por peça.

## Como este lab está montado

Foi desenvolvido em **Windows + WSL2**: o **Docker roda dentro do WSL2**
(Ubuntu) e o **navegador do Windows acessa os serviços via `localhost`** —
o WSL2 encaminha automaticamente as portas publicadas para o Windows. Ou
seja, o WSL "hospeda" a infra e o Windows é só o cliente (browser/terminal).

Mas como dentro do WSL **é Linux**, o projeto roda **igual em Linux nativo**.
As duas formas estão documentadas abaixo.

## Pré-requisitos
- **Docker** (Engine + plugin `compose`) e **Terraform**.
- No Windows: tudo isso instalado **dentro do WSL2** (não precisa de Docker
  Desktop; Docker Engine nativo no WSL com systemd funciona).

## Rodar tudo com um comando

### Opção A — Windows + WSL2

A partir do PowerShell do Windows (o `--cd` evita problemas com o espaço em
"github repos"):

```powershell
wsl --cd "C:\Users\crist\OneDrive\Documentos\github repos\ministack-local-infra" -- bash run.sh
```

Ou: abra o terminal do Ubuntu (WSL), navegue até o repo em `/mnt/c/...` e
rode `bash run.sh`.

### Opção B — Linux nativo

Clone o repo em qualquer lugar e rode:

```bash
git clone <url-do-repo> ministack-local-infra
cd ministack-local-infra
bash run.sh
```

> Em ambos os casos o `run.sh` faz: build das imagens → sobe a infra →
> Terraform cria bucket/tabela/seed → roda a pipeline → mostra o que a
> print-api recebeu.

Para derrubar:
```bash
docker compose down
```

## Acessar no navegador

Depois de subir, abra no navegador (no Windows **ou** no Linux, sempre
`localhost` — no WSL2 o encaminhamento é automático):

| URL                                         | O que mostra                                  |
|---------------------------------------------|-----------------------------------------------|
| http://localhost:9000/                      | **Tela da print-api**: tabela de resultados (auto-atualiza a cada 3s) |
| http://localhost:9000/results               | Resultados recebidos em JSON                  |
| http://localhost:9000/docs                  | Swagger UI da print-api                       |
| http://localhost:8000/docs                  | Swagger UI do modelo (testar `/predict` ali)  |
| http://localhost:4566/_ministack/health     | Status do MiniStack                           |

> Rode a pipeline de novo com a tela `localhost:9000` aberta para ver os
> resultados aparecerem ao vivo:
> ```bash
> docker compose run --rm pipeline
> ```

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
                        │  print-api │ ← recebe, guarda e mostra no navegador
                        │   :9000    │
                        └────────────┘
```

| Componente      | Papel                                            | Porta |
|-----------------|--------------------------------------------------|-------|
| `ministack`     | Emulador AWS (S3 + DynamoDB) numa porta só       | 4566  |
| `model-service` | CARA 1 — modelo scikit-learn servindo `/predict` | 8000  |
| `print-api`     | CARA 2 — recebe o resultado, guarda e exibe      | 9000  |
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
├── print-api/              CARA 2 — consumidor que recebe e exibe
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py              FastAPI: / (HTML), /results, POST /results
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

# 4) ver o que a print-api recebeu (log) ou abrir http://localhost:9000/
docker compose logs print-api

# (opcional) conferir a infra
docker compose run --rm pipeline python verify_infra.py
```

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

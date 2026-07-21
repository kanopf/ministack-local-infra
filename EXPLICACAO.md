# Como tudo funciona — explicação detalhada

Este documento explica, em profundidade, **cada peça** deste lab e **o que
cada passo faz**. A ordem é de baixo pra cima: ambiente → MiniStack → rede →
compose → Terraform → modelo → print-api → pipeline → `run.sh` → o fluxo
amarrado → ciclo de vida.

---

## 1. O ambiente: WSL2 + Docker + os caminhos

**Por que WSL.** Docker roda nativo em Linux. No Windows, o WSL2 te dá um
kernel Linux real, e o Docker Engine roda *dentro* dele. Tudo (build de
imagem, containers, rede) acontece nesse Linux. Em Linux nativo é idêntico,
só que sem a camada WSL.

**O problema dos espaços no caminho.** O repo fica em
`...\github repos\ministack-local-infra` — há um espaço em "github repos".
Ao mandar comandos do Windows (PowerShell) → WSL → bash, as aspas se perdem
no meio do caminho e o `cd` quebra em "github". A solução é o flag
**`wsl --cd "<caminho>"`**: ele recebe o caminho como **um argumento único**
e entra na pasta certa, sem o bash ter que interpretar o espaço.

**`/mnt/c`.** Dentro do WSL, o disco `C:` aparece montado em `/mnt/c`. Por
isso o `docker compose` rodando no WSL consegue ler arquivos que estão
fisicamente no Windows.

**`localhost` encaminhado.** O WSL2 encaminha automaticamente as portas
publicadas (ex.: `4566`, `8000`, `9000`) para o `localhost` do Windows — por
isso o navegador do Windows acessa os serviços sem configuração extra.

---

## 2. MiniStack — o coração

**Conceito.** A AWS de verdade é só um monte de **APIs HTTP**. Quando o boto3
faz `s3.create_bucket(...)`, ele envia um `PUT` HTTP assinado. O MiniStack é
**um único servidor HTTP** que finge ser *todos* os serviços AWS ao mesmo
tempo, escutando na **porta 4566**.

**Roteamento numa porta só (o truque do SigV4).** A AWS real separa serviços
por hostname (`s3.amazonaws.com`, `dynamodb.amazonaws.com`). O MiniStack não
— ele descobre qual serviço você quer lendo o **nome do serviço embutido na
assinatura SigV4**, que vai no header `Authorization`:

```text
Authorization: AWS4-HMAC-SHA256 Credential=test/20260629/us-east-1/s3/aws4_request, ...
                                                              ▲▲
                                          o "s3" aqui diz ao MiniStack: é o serviço S3
```

Por isso S3, DynamoDB e tudo mais cabem na mesma porta.

**Credenciais fictícias.** Usamos `access_key="test"`, `secret="test"`.
Localmente o MiniStack **não valida** a assinatura criptograficamente — ele
só precisa que o SDK *gere* uma assinatura no formato certo (pra extrair o
nome do serviço). Por isso qualquer credencial "funciona".

**Em memória.** Com `SERVICES=s3,dynamodb`, esses dois rodam **na RAM** do
container. Rápido e leve — mas **volátil**: `docker compose down` apaga
buckets e tabelas. (É por isso que o Terraform precisa rodar de novo após um
down — veja seções 6 e 11.)

**Endpoint interno.** `http://localhost:4566/_ministack/health` não existe na
AWS real — é uma extensão do MiniStack que retorna quais serviços estão
`available`. O `run.sh` usa ela pra saber quando o MiniStack ficou pronto.

---

## 3. Rede Docker — como os caras se acham

Quando o Compose cria a rede `ministack-net`, ele liga um **DNS interno**:
cada container vira um *hostname* igual ao seu nome. Então, **de dentro da
rede**:

- `http://ministack:4566` → o container do MiniStack
- `http://model-service:8000` → o modelo
- `http://print-api:9000` → a print-api

**`localhost` vs nome do container** (a pegadinha mais importante):

- Rodando **no host (WSL/Linux)**: você fala com `http://localhost:4566`
  (porque a porta foi mapeada — veja seção 5).
- Rodando **dentro de um container** na rede: `localhost` é o *próprio*
  container, então você precisa do nome: `http://ministack:4566`.

Por isso a pipeline lê o endpoint de uma **variável de ambiente**
(`MINISTACK_ENDPOINT`): no compose recebe `http://ministack:4566`; rodando
direto no host, o default é `localhost`.

---

## 4. `docker-compose.yml` — linha a linha

```yaml
services:
  ministack:
    image: ministackorg/ministack   # imagem pronta do Docker Hub (não buildamos)
    container_name: ministack        # nome fixo => vira o hostname na rede
    ports:
      - "4566:4566"                  # HOST:CONTAINER — expõe a porta pro host
    environment:
      - SERVICES=s3,dynamodb         # liga só esses serviços (mais leve)
```

- **`ports: "4566:4566"`** = *port mapping*. Lado esquerdo é a porta no host,
  direito é dentro do container. É isso que faz o `localhost:4566` funcionar
  fora da rede Docker (Terraform e o `curl` do `run.sh` usam isso).

```yaml
  model-service:
    build: ./model-service           # builda a imagem A PARTIR dessa pasta do repo
    image: model-service:1.0         # nome/tag dado à imagem buildada
    container_name: model-service
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 5s
      timeout: 3s
      retries: 10
```

- **`build:` vs `image:`** — `build: ./pasta` faz o Compose **construir a
  imagem do próprio repo**. É o que torna o projeto "clona e roda".
- **`healthcheck`** — comando que o Compose roda periodicamente *dentro* do
  container pra marcar `healthy`. Usamos `python urllib` (não `curl`) porque
  a imagem é Python e tem `python`, mas pode não ter `curl`. (Foi por isso
  que o MiniStack aparecia "unhealthy" no começo: o healthcheck dele tentava
  `curl`, ausente naquela imagem; removemos.)

```yaml
  print-api:
    build: ./print-api
    image: print-api:1.0
    container_name: print-api
    ports:
      - "9000:9000"
```

```yaml
  pipeline:
    build: ./pipeline
    image: pipeline:1.0
    profiles: ["tools"]              # NÃO sobe no 'docker compose up'
    environment:
      - MINISTACK_ENDPOINT=http://ministack:4566
      - MODEL_URL=http://model-service:8000
      - PRINT_API_URL=http://print-api:9000
    depends_on:
      - ministack
      - model-service
      - print-api
```

- **`profiles: ["tools"]`** — serviços com profile **não sobem** no `up`
  normal. A pipeline é um *job* (roda e morre), não um serviço de pé. Você a
  dispara com `docker compose run --rm pipeline` (o `--rm` apaga o container
  depois).
- **`environment`** — injeta os endpoints com os **nomes dos containers**
  (porque a pipeline roda *dentro* da rede).
- **`depends_on`** — garante a *ordem de partida*. Atenção: ele espera o
  container **iniciar**, não ficar pronto — por isso o `run.sh` ainda faz um
  *wait* explícito no health.

```yaml
networks:
  default:
    name: ministack-net              # nomeia a rede default
```

- Todos os serviços, sem `networks:` próprio, entram nessa rede. Demos um
  **nome fixo** porque a usamos manualmente em alguns `docker run`.

---

## 5. Terraform — a infra como código

O Terraform é declarativo: você descreve o **estado desejado** e ele faz o
alvo (aqui, o MiniStack) bater com isso.

### `main.tf` — provider

```hcl
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true   # não liga pra AWS real validar credenciais
  skip_metadata_api_check     = true   # não tenta o endpoint de metadata da EC2
  skip_requesting_account_id  = true   # não chama o STS pra descobrir o account id
  s3_use_path_style           = true   # URL no formato host/bucket (não bucket.host)
  endpoints {
    s3       = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
  }
}
```

- Os **`skip_*`** desligam chamadas que o provider AWS faz pra AWS de verdade
  (validar credencial, buscar account id via STS, checar metadata da EC2).
  Como é tudo local e fake, essas chamadas falhariam/travariam — então
  pulamos.
- **`s3_use_path_style = true`** — por padrão o S3 usa "virtual-host style"
  (`meu-bucket.s3.amazonaws.com`), que não resolve em DNS local. Com
  path-style vira `http://localhost:4566/meu-bucket`, que funciona.
- **`endpoints { ... }`** — o ponto-chave: redireciona cada serviço pro
  MiniStack. Como o Terraform roda **no host**, usa `localhost:4566`.

### `main.tf` — recursos

```hcl
resource "aws_s3_bucket" "predictions" {
  bucket = var.bucket_name          # "ml-predictions"
}

resource "aws_dynamodb_table" "input_data" {
  name         = var.table_name     # "input-data"
  billing_mode = "PAY_PER_REQUEST"  # modo on-demand: sem provisionar capacidade
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"                       # S = String
  }
}
```

- No DynamoDB você só declara os atributos que fazem parte da **chave**
  (`id`). Os outros campos (como `features`) são *schemaless* — você grava o
  que quiser por item.
- **`PAY_PER_REQUEST`** evita declarar capacidade de leitura/escrita.

### `main.tf` — seed dos dados

```hcl
locals {
  seed_items = {
    "rec-001" = "[1.0, 2.0, 3.0]"
    "rec-002" = "[0.0, 0.0, 0.0]"
    "rec-003" = "[5.0, -1.0, 2.0]"
    "rec-004" = "[-2.0, 4.0, 1.0]"
  }
}

resource "aws_dynamodb_table_item" "seed" {
  for_each   = local.seed_items                      # 1 recurso por entrada do mapa
  table_name = aws_dynamodb_table.input_data.name
  hash_key   = aws_dynamodb_table.input_data.hash_key
  item = jsonencode({
    id       = { S = each.key }                      # "rec-001"
    features = { S = each.value }                    # "[1.0, 2.0, 3.0]"
  })
}
```

- **`locals`** = valores nomeados reutilizáveis (aqui, um mapa id→features).
- **`for_each`** = cria um recurso por entrada do mapa; `each.key`/`each.value`
  são a chave e o valor. Foi assim que semeamos as 4 linhas via IaC.
- **`jsonencode` + `{ S = ... }`** — o DynamoDB representa cada atributo com
  seu **tipo** explícito: `S` = string, `N` = número, etc. Aqui `features` é
  uma *string* contendo um JSON (`"[1.0, 2.0, 3.0]"`); a pipeline depois faz
  `json.loads` pra virar lista.
- **Referência implícita = dependência.** Como o item referencia
  `aws_dynamodb_table.input_data.name`, o Terraform cria a **tabela antes**
  dos itens.

### `variables.tf` e `outputs.tf`

- **`variables.tf`** — parametriza nomes (bucket/tabela) com `default`, dá pra
  trocar sem editar o `main.tf`.
- **`outputs.tf`** — imprime valores úteis no fim do apply (`bucket_name`,
  `table_name`, `seeded_ids`).

### `terraform init` e `terraform apply`

- **`init`** baixa o *provider* AWS (o plugin que fala com a API) pra
  `.terraform/` e grava o `.terraform.lock.hcl` (fixa a versão). Roda uma vez.
- **`apply -auto-approve`** calcula o diff (desejado × atual) e executa sem
  pedir confirmação.

### O **state** e o "drift" no down

O Terraform guarda o que criou num **`terraform.tfstate`** (em disco). Aqui há
uma sutileza do lab:

- O MiniStack guarda dados **em memória**; o `tfstate` fica **em disco**.
- `docker compose down` zera o MiniStack (bucket/tabela somem), **mas o
  `tfstate` continua dizendo que existem** → "drift".
- Por padrão, o `apply` faz um **refresh** antes: consulta o MiniStack, vê
  que o bucket sumiu, tira do state e **recria**. Por isso funciona mesmo
  depois de um `down -v`.
- O `.gitignore` ignora `.terraform/` e `*.tfstate*` — locais/efêmeros.

---

## 6. O modelo (model-service)

### `train.py` — treina no build

```python
rng = np.random.default_rng(42)            # semente fixa => reprodutível
X = rng.normal(size=(500, 3))              # 500 amostras, 3 features
coef = np.array([3.0, 2.0, -1.0])
y = X @ coef + rng.normal(scale=0.1, size=500)   # y = 3·x0 + 2·x1 - 1·x2 + ruído
modelo = LinearRegression().fit(X, y)
joblib.dump({"model": modelo, "n_features": 3}, "model.pkl")
```

- Cria dados sintéticos com uma relação linear conhecida e treina uma
  regressão linear. **Não importa o domínio** — a ideia é ter um artefato de
  modelo real (`model.pkl`) salvo em disco.
- **Padrão treina-no-build:** o `Dockerfile` roda `python train.py` durante o
  build, então o `model.pkl` fica **"assado" dentro da imagem**. É o padrão
  real de serving (treina offline → salva artefato → serve), só que aqui o
  "offline" acontece no build.

### `app.py` — serve a inferência

```python
_bundle = joblib.load("model.pkl")     # carrega o artefato 1x, no startup
_model = _bundle["model"]

@app.post("/predict")
def predict(req: PredictRequest):       # req.features = [1.0, 2.0, 3.0]
    x = np.array(req.features).reshape(1, -1)
    y = float(_model.predict(x)[0])
    return {"prediction": y, "n_features": 3}
```

- `GET /health` → checagem de saúde (usada no healthcheck do compose).
- `POST /predict` → recebe `{"features": [...]}`, valida o tamanho, roda
  `model.predict` e devolve `{"prediction": ...}`.
- O modelo é carregado **uma vez** no startup (não a cada request) — eficiente.

### `Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # deps primeiro (cache de camada)
COPY train.py .
RUN python train.py                                   # treina e "assa" o model.pkl
COPY app.py .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- A ordem (deps → treino → app) é proposital: como as deps mudam menos que o
  código, ficam numa camada cacheada e o rebuild fica rápido.

---

## 7. A print-api (consumidor)

`app.py` guarda em memória tudo que recebe e expõe isso para o navegador:

```python
_recebidos: list[dict] = []            # acumula os resultados (some no restart)

@app.post("/results")                  # a pipeline manda pra cá
async def results(request: Request):
    payload = await request.json()
    _recebidos.append({"recebido_em": ..., "payload": payload})
    print(...)                         # também printa no log do container
    return {"received": True, "total": len(_recebidos)}

@app.get("/results")                   # mesma lista, em JSON
def listar(): return _recebidos

@app.get("/", response_class=HTMLResponse)   # uma TELA pro navegador
def home(): return "<html>...tabela com os resultados...</html>"
```

- **Por que existe um `GET /`**: o navegador faz **GET**. Antes só havia
  `POST /results`, então abrir no browser não mostrava nada. O `GET /` monta
  uma tabela HTML com os resultados e usa
  `<meta http-equiv="refresh" content="3">` pra recarregar sozinho a cada 3s.
- **`GET /docs`** vem de graça do FastAPI (Swagger UI), onde dá pra disparar
  o `POST` manualmente.
- Os resultados ficam **em memória do container** — reinício zera a lista.

---

## 8. A pipeline (a cola / orquestração)

`run_pipeline.py` amarra todo mundo. Cria dois clientes boto3 apontados pro
MiniStack:

```python
aws_common = dict(
    endpoint_url=MINISTACK_ENDPOINT,   # http://ministack:4566 (dentro da rede)
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)
s3  = boto3.client("s3", **aws_common)
ddb = boto3.client("dynamodb", **aws_common)
```

O `endpoint_url` é a única coisa diferente de falar com a AWS real — o resto
do código boto3 é idêntico ao de produção.

**1) Lê a tabela:**
```python
items = ddb.scan(TableName=TABLE_NAME).get("Items", [])
```
`scan` lê todas as linhas. Cada item vem no formato tipado do DynamoDB:
```python
{"id": {"S": "rec-001"}, "features": {"S": "[1.0, 2.0, 3.0]"}}
```
Por isso o código faz `it["id"]["S"]` e `json.loads(it["features"]["S"])`.

**2) Grava o dado bruto no S3:**
```python
s3.put_object(Bucket=BUCKET_NAME, Key=f"raw/{rec_id}.json", Body=..., ContentType="application/json")
```
O S3 **não tem pastas de verdade** — `raw/` e `predictions/` são só prefixos
no nome da chave (as ferramentas mostram como se fossem pastas).

**3) Chama o modelo:**
```python
r = requests.post(f"{MODEL_URL}/predict", json={"features": features})
prediction = r.json()["prediction"]
```

**4) Grava a predição no S3** (`predictions/<id>.json`) — mesmo `put_object`.

**5) Envia pra print-api:**
```python
requests.post(f"{PRINT_API_URL}/results", json=result)
```

Tudo num loop por linha. No fim: 4 linhas × 2 objetos = **8 objetos** no
bucket.

**Por que rodar a pipeline em container** (e não no Python do host): instalar
libs no Python do sistema exige `venv`/sudo. Empacotando como imagem, as deps
(`boto3`, `requests`) já vêm prontas, e o container entra na `ministack-net` e
enxerga todos pelo nome. Zero dependência do host.

---

## 9. `run.sh` — o "um comando"

```bash
set -euo pipefail            # aborta em erro, var indefinida, e erro no meio de pipe
cd "$(dirname "$0")"         # entra na pasta do próprio script (raiz do repo)
```

**Passo 1 — build + up:**
```bash
docker compose up -d --build
```
`-d` = detached; `--build` = (re)constrói as imagens antes de subir. Sobe
ministack, model-service e print-api (a pipeline **não**, por causa do
profile).

**Passo 2 — espera o MiniStack ficar pronto:**
```bash
for i in $(seq 1 30); do
  if curl -sf http://localhost:4566/_ministack/health >/dev/null 2>&1; then break; fi
  sleep 1
done
```
*Polling* até o `/health` responder (resolve a corrida: `depends_on` só
garante que o container iniciou, não que a API responde). `curl` aqui é do
host; usa `localhost` porque estamos fora da rede.

**Passo 3 — Terraform:**
```bash
cd terraform
terraform init -input=false >/dev/null   # init silencioso, sem prompts
terraform apply -auto-approve
cd ..
```

**Passo 4 — roda a pipeline e mostra o resultado:**
```bash
docker compose run --rm pipeline          # dispara o job one-shot
docker compose logs print-api | tail -30  # mostra o que a print-api recebeu
```

---

## 10. O fluxo inteiro amarrado

```text
você: bash run.sh
   │
   ├─(1) docker compose up -d --build
   │        → sobe ministack(:4566), model-service(:8000), print-api(:9000) na rede ministack-net
   │
   ├─(2) espera /_ministack/health responder "available"
   │
   ├─(3) terraform apply
   │        → provider AWS fala http://localhost:4566
   │        → cria bucket "ml-predictions" + tabela "input-data" + 4 itens (seed)
   │
   └─(4) docker compose run --rm pipeline
            → dentro da rede, fala ministack:4566 / model-service:8000 / print-api:9000
            → scan da tabela → grava raw/ no S3 → inferência → grava predictions/ no S3 → POST pra print-api
            → print-api guarda e printa cada resultado (visível em http://localhost:9000/)
```

---

## 11. Ciclo de vida e limpeza

Como S3 e DynamoDB são em memória:

- `docker compose down` → para os containers; **dados somem**.
- Subir de novo → MiniStack vazio → roda o Terraform de novo (detecta o drift
  e recria tudo).
- `terraform destroy` → remove o que o Terraform criou e zera o `tfstate`.
- A lista de resultados da print-api também é em memória → reinício zera; é só
  rodar a pipeline de novo.

---

## 12. Acesso pelo navegador

O WSL2 encaminha `localhost` pro Windows (em Linux nativo é direto):

| URL                                       | Mostra                                    |
|-------------------------------------------|-------------------------------------------|
| <http://localhost:9000/>                  | Tela da print-api (tabela, auto-refresh)  |
| <http://localhost:9000/results>           | Resultados em JSON                        |
| <http://localhost:9000/docs>              | Swagger UI da print-api                   |
| <http://localhost:8000/docs>              | Swagger UI do modelo (testar `/predict`)  |
| <http://localhost:4566/_ministack/health> | Status do MiniStack                       |

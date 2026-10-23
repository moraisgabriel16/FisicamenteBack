# FísicaMente — Back-end

API Python/FastAPI para acompanhamento escolar, com SQLAlchemy, PostgreSQL/SQLite, senhas Argon2, sessões revogáveis e dados sensíveis cifrados.

**Front-end:** [moraisgabriel16/Fisicamente](https://github.com/moraisgabriel16/Fisicamente).

## Executar localmente

Requisitos: Python 3.12 ou superior. Execute na raiz deste repositório:

```sh
python -m venv .venv
```

Ative o ambiente (`.venv\Scripts\Activate.ps1` no PowerShell ou `source .venv/bin/activate` no Linux/macOS), então:

```sh
pip install -r backend/requirements.txt
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Documentação interativa: http://127.0.0.1:8000/docs. Saúde: `/api/v1/health`.

O código permanece no pacote `backend/` para manter importações, testes e migrações consistentes. Este repositório não contém front-end nem dados locais.

## Configuração

- `DATABASE_URL`: padrão SQLite em `backend/data/fisicamente.db`; para PostgreSQL, `postgresql+psycopg://usuario:senha@host/banco`.
- `APP_URL`: origem exata do front, padrão `http://127.0.0.1:5186`.
- `APP_ENV=production`: exige `ENCRYPTION_KEY`, usa cookies Secure e desabilita os links de desenvolvimento.
- `ENCRYPTION_KEY`: gere com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Guarde em segredo. A chave é indispensável para recuperar saúde e anexos cifrados.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`: envio por STARTTLS.

O processo Python lê variáveis de ambiente. O `.env` é carregado automaticamente pelo Docker Compose, não pelo comando Uvicorn. Sem SMTP, os e-mails ficam na caixa de saída local e o cadastro de desenvolvimento apresenta seu link de confirmação.

## Docker

Copie `.env.example` para `.env`, defina senha e chave e execute:

```sh
docker compose up --build -d
```

Para incluir o front, clone ambos os repositórios em pastas irmãs com os nomes `Fisicamente` e `FisicamenteBack`, e execute na pasta do back:

```sh
docker compose --profile full up --build -d
```

Os contêineres foram preparados, mas não testados no ambiente de desenvolvimento original, que não tinha Docker.

## Testes

```sh
python -m pytest backend/tests -q
```

Os testes usam um banco temporário e dados fictícios. Cobrem autenticação, autorização por perfil/escola, avaliações idempotentes e atômicas, criptografia, relatórios, importação, alertas, módulos operacionais e correções com histórico.

## Estado do produto

Os módulos têm implementação funcional local. Não foram publicados serviços de API, banco ou e-mail por este repositório. A implantação requer HTTPS, configuração dos serviços e homologação. Veja [IMPLEMENTACAO.md](IMPLEMENTACAO.md) para o escopo funcional e as limitações; as instruções de execução deste README prevalecem sobre os caminhos do antigo monorepo citados naquele documento.

Não há banco, chaves, anexos, `.env` real ou contas de demonstração prontas neste repositório. Crie a escola pelo cadastro do front-end.

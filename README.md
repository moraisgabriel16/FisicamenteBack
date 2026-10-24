# FísicaMente — Back-end

API Python/FastAPI para acompanhamento escolar, com SQLAlchemy, PostgreSQL/SQLite, senhas Argon2, sessões revogáveis e dados sensíveis cifrados.

**Front-end:** [moraisgabriel16/Fisicamente](https://github.com/moraisgabriel16/Fisicamente).

## Publicação online

- Aplicação: https://fisicamente-sigma.vercel.app
- Cadastro: https://fisicamente-sigma.vercel.app/cadastro
- Saúde da API: https://fisicamenteback.vercel.app/api/v1/health

API publicada na Vercel e conectada ao PostgreSQL Neon dedicado `fisicamente-postgres`. O cadastro inicial é imediato, com `REQUIRE_EMAIL_VERIFICATION=false`, por escolha do proprietário. Confirmação e recuperação por e-mail dependem da configuração posterior do envio. A chave de criptografia e as credenciais do banco ficam nas variáveis protegidas da hospedagem, fora do Git.

O fluxo online foi validado com dados fictícios isolados: cadastro, login, convite, turma, aluno, avaliação idempotente, consulta após nova sessão e geração de PDF.

O módulo de envios agendados fica oculto na Vercel até existir um executor apropriado. Os demais módulos usam chamadas normais à API e armazenamento no banco.

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
- `REQUIRE_EMAIL_VERIFICATION`: padrão `true`. Na primeira publicação de testes, `false` permite entrar após o cadastro, mantendo o e-mail identificado como não confirmado. A recuperação por e-mail depende de configurar SMTP. Gestores podem copiar links de convite para compartilhar individualmente.

## Vercel e banco persistente

Importe o repositório como projeto FastAPI. `app.py` é o ponto de entrada e `requirements.txt` da raiz carrega as dependências. Configure `APP_ENV=production`, `APP_URL` com a origem do front, uma chave Fernet exclusiva em `ENCRYPTION_KEY` e conecte o PostgreSQL do Neon ao projeto (variável `DATABASE_URL` ou `POSTGRES_URL`).

O servidor recusa usar SQLite na Vercel/produção. Novos anexos são cifrados e persistidos no PostgreSQL, sem depender de arquivos temporários. O worker contínuo é desativado na Vercel; os agendamentos e envio de e-mails em segundo plano exigem configurar um executor externo antes de utilizá-los nessa hospedagem.

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

Os módulos têm implementação funcional local e online. A API e o PostgreSQL estão publicados; o envio de e-mails ainda não foi configurado. Veja [IMPLEMENTACAO.md](IMPLEMENTACAO.md) para o escopo funcional e as limitações; as informações atuais de publicação deste README prevalecem sobre o relato da entrega inicial naquele documento.

Não há banco, chaves, anexos, `.env` real ou contas de demonstração prontas neste repositório. Crie a escola pelo cadastro do front-end.

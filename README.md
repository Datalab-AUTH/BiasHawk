# BiasHawk

AI fairness, data quality and NIST AI RMF risk assessment. Upload documentation
and datasets for an AI system, and BiasHawk profiles the data, detects bias,
tracks drift, and produces compliance reports.

## Layout

```
backend/
  config/         Django project , settings, root urls, wsgi
  core/
    models.py     User, Usecase, Instance, files, Job, chunks
    views.py      the API
    jobs/         one module per analysis, registered by kind
    analysis/     pure pandas: quality, bias, drift, governance, sensitive features
    rag/          chunking, embeddings, pgvector retrieval
    agents/       metadata extraction schemas and pipeline
    risk/         the NIST risk assessment agents
    llm.py        the only Open WebUI client
    reports.py    Markdown -> PDF
frontend/         Next.js
docker/           container entrypoints
Dockerfile.backend    one image, two roles
compose.yml       postgres + api + worker + frontend
```

## Architecture

Four containers, two images.

| Container | Role |
|---|---|
| `postgres` | Everything: application tables, job queue, and vector embeddings (pgvector) |
| `api` | Gunicorn. Owns schema changes , migrates, collects static, ensures the superuser, then serves |
| `worker` | `manage.py runjobs`: eight threads running queued analysis |
| `frontend` | Next.js |

`api` and `worker` are **the same image** with different entrypoints, chosen in
`compose.yml`. Every analysis is a function in `backend/core/jobs/`, registered
in a dict and called in-process by the worker threads , none of them is a
separate service.

The worker waits on the API's healthcheck, so migrations are always applied
before jobs start and the two never race. If either container dies the other is
unaffected; Docker restarts only the one that failed.

## Jobs

Long-running analysis is queued in Postgres. Enqueueing returns `202`
immediately; the runner claims the row and the client polls.

```
POST /api/instances/<id>/jobs   {"kind": "data_quality"}   -> 202 + job id
GET  /api/jobs/<id>                                        -> status, result, error
GET  /api/instances/<id>/jobs?kind=data_quality            -> history, newest first
```

Each runner thread claims work with `SELECT … FOR UPDATE SKIP LOCKED`, so
threads never block each other and no row is ever claimed twice. Re-requesting
an analysis already queued or running returns `200` with the job in flight
rather than queueing a duplicate.

A handler takes the `Job`, writes its results to the model, and raises on
failure. The runner records the traceback, retries up to `JOB_MAX_ATTEMPTS`,
then marks the job failed and writes an `ErrorLog` row. A job whose worker dies
mid-run returns to the queue once its lock is older than `JOB_STALE_SECONDS`.

### Job kinds

| Kind | Needs | Writes |
|---|---|---|
| `rag_ingest` | uploaded documents | `DocumentChunk` rows |
| `usecase_extract` | a completed `rag_ingest` | `Usecase.metadata` |
| `instance_extract` | a completed `rag_ingest` | `Instance.metadata` |
| `data_governance` | a source dataset | `data_profile_description` |
| `data_quality` | a source dataset | `quality_metrics`, `quality_warnings`, `data_quality_report` |
| `sensitive_features` | a source dataset | `dataset_sensitive_features` |
| `bias_assessment` | `label`, `favorable_outcome` in the payload | `analysis_results`, `metrics_report`, `warnings_report` |
| `bias_report` | a completed `bias_assessment` | `final_bias_report` |
| `drift` | `initial_instance` in the payload | an `InstanceDataDrift` row |
| `risk_assessment` | `data_quality` and/or `bias_assessment` | `nist_risk_report`, `nist_risk_report_data` |

`bias_assessment` takes its sensitive features from the payload, or falls back
to whatever `sensitive_features` detected. `drift` always compares data
distributions; it adds the bias-drift half only when both instances have been
through `bias_assessment`.

```bash
curl -X POST localhost:8000/api/instances/<id>/jobs \
  -H 'Content-Type: application/json' -H "X-CSRFToken: $TOKEN" \
  -d '{"kind":"bias_assessment","payload":{"label":"risk","favorable_outcome":"good"}}'
```

## Auth

Email/password, Google and GitHub, via `django-allauth` in headless mode. A
Django **session cookie**, not a bearer token: the frontend and API are
same-site in dev and production, so the cookie reaches both.

| Endpoint | Purpose |
|---|---|
| `GET /api/csrf` | Token + cookie. Call before any unsafe request. |
| `GET /api/me` | The signed-in user. |
| `POST /_allauth/browser/v1/auth/signup` | Email/password sign-up. |
| `POST /_allauth/browser/v1/auth/login` | Email/password sign-in. |
| `DELETE /_allauth/browser/v1/auth/session` | Sign out. |
| `POST /_allauth/browser/v1/auth/provider/redirect` | Start Google/GitHub login. |
| `GET /_allauth/browser/v1/config` | Which providers are enabled. |

Every unsafe request needs the `X-CSRFToken` header echoing the `csrftoken`
cookie, and `credentials: "include"`.

DRF defaults to `IsAuthenticated`; endpoints opt out explicitly with a comment
saying why (see `core/views.py:HealthView`). Domain querysets are scoped to the
owner at the **manager** , `Usecase.objects.for_user(...)` , so a view cannot
forget to filter. Another account's object is absent rather than forbidden: the
lookup returns 404 without confirming the UUID exists.

### OAuth redirect URIs

The callback lands on Django. Register these with the providers:

```
http://localhost:8000/accounts/google/login/callback/
http://localhost:8000/accounts/github/login/callback/
```

Social login returns `error=unknown` until they are.

### Email verification

`ACCOUNT_EMAIL_VERIFICATION` defaults to `none`, because no SMTP provider is
configured. Set it to `mandatory` once mail is wired up.

## RAG

Documents (PDF, DOCX, TXT, MD) are uploaded to a use case or an instance, then
ingested by `rag_ingest`: loaded, chunked, embedded, and stored as
`DocumentChunk` rows with a pgvector column.

```
POST /api/usecases/<id>/files            multipart, one document
POST /api/usecases/<id>/jobs             {"kind": "rag_ingest"}
POST /api/usecases/<id>/rag/query        {"query": "..."}  -> answer + sources
POST /api/instances/<id>/rag/query       instance docs plus its use case's
```

Querying is synchronous , retrieval plus one completion, a few seconds.

Embeddings run on Open WebUI, on the server's GPU , no embedding model is
loaded into the API or worker process. Only the cross-encoder reranker is still
in-process on CPU, because Open WebUI exposes no reranking endpoint; it is
cached in the `hf_cache` volume so it downloads once.

**Retrieval settings that matter.** `RAG_TOP_K` (30) is the candidate pool
fetched by vector distance; `RAG_TOP_N_RERANK` (3) is what the cross-encoder
keeps. Fetch wide, then rank precisely , a relevant chunk at vector rank 13
never reaches a reranker that only sees 10 candidates.

`RAG_USE_HYDE` is **off**. HyDE embeds a hypothetical answer instead of the
question. It helps on broad thematic queries and actively hurts factual lookup:
asked which organisation provides a system, the model invents a plausible name,
and embedding that fabrication pulls retrieval to the wrong document entirely.

Embeddings are served by Open WebUI , the same base URL, key and client as
chat , so no embedding model is loaded into the API or worker process. Only the
cross-encoder reranker still runs in-process, because Open WebUI exposes no
reranking endpoint.

Changing `OPENWEBUI_EMBED_MODEL` changes the vector width and invalidates every
stored chunk. `manage.py check_embeddings` says so before inserts start failing;
it now also proves the model is reachable.

## Metadata extraction

`usecase_extract` and `instance_extract` read the ingested documents and fill
the compliance records the dashboard renders , `AISystemDocumentation` (25
questions) and `AIDataComplianceForm` (21), both in `core/agents/schemas.py`.

Each question drives **retrieval only** , embed, search, rerank, no completion ,
and the deduplicated passages go to a single call that fills the schema from the
source text.

Every schema field has a default (`"unknown"`, `false`, `["unknown"]`), so a
partial answer degrades per-field instead of failing validation outright. A
reply that still fails validation is retried once with the errors fed back.

Note for the frontend: `user_groups`, `oversight_procedures`, `user_training`,
`auditability`, `explainability_techniques` and `security_measures` are
**arrays of strings**, not strings.

## Risk assessment

`risk_assessment` gathers everything the earlier jobs produced for an instance ,
extracted system documentation, quality metrics, bias results and any drift
record , and runs seven agents over it in order: governance, quality, bias and
drift analysis, NIST mapping, prioritisation, then synthesis into the report.

Six are pure Python that reshape metrics into findings; only synthesis calls an
LLM, twice, to add NIST commentary. The chain is a `for` loop in
`core/risk/pipeline.py`.

NIST AI RMF guidance is retrieved from `NistChunk`, a pgvector table embedded
once from the corpus committed at `backend/core/data/`.

The report covers all four NIST functions plus a risk dashboard, intersectional
fairness analysis, and EU AI Act compliance, and is stored on the instance as
`nist_risk_report` with structured findings in `nist_risk_report_data`.

## Report PDFs

```
GET /api/instances/<id>/reports/<slug>/pdf
GET /api/drift/<id>/pdf
```

Slugs: `risk`, `data-governance`, `data-quality`, `bias-metrics`,
`bias-warnings`, `bias-final`. A report that has not been generated yet returns
404 rather than an empty document.

Rendering is ReportLab , pure Python, so no pango, cairo or wkhtmltopdf in the
image.

## LLM

Every LLM call goes through `core/llm.py`, which talks to Open WebUI's
OpenAI-compatible API. There is no provider switch and no `OPENAI_API_KEY`.
A call that fails after its retries raises, so the job is recorded as failed and
retried , rather than writing an apology into a report.

## Enviroment Variables

Two files, both gitignored, neither committed:

- **`.env`** , local development. Read by python-dotenv in
  `backend/config/settings.py` and by `frontend/next.config.ts`, so backend and
  frontend share one file.
- **`docker.env`** , `docker compose up`. Injected as real environment
  variables, which take precedence over `.env`; `.env` is excluded from the
  images by `.dockerignore`, so containers never read it.

`compose.yml` deliberately contains no `${VAR}` substitution , Compose would
resolve those from `.env`, and Docker's configuration comes from `docker.env`
only.


#### `postgres`

| Variable | Required | Notes |
|---|---|---|
| `POSTGRES_DB` | yes | Must equal `DB_NAME` on `api` and `worker`. |
| `POSTGRES_USER` | yes | Must equal `DB_USER`. Also read by the compose healthcheck, so it has to stay in the container's environment after the first boot, not just at initdb. |
| `POSTGRES_PASSWORD` | yes | Must equal `DB_PASSWORD`. |

These take effect at **first** boot only. On an existing `postgres_data` volume
initdb is skipped, so changing them locks the API out rather than changing the
credentials , alter the role in SQL, or start from a fresh volume.

#### `api`

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DEBUG` | yes | `False` | Anything but `false` in production. Turning it off is what makes `DJANGO_SECRET_KEY` required and switches on secure cookies and HSTS. |
| `DJANGO_SECRET_KEY` | yes when `DEBUG=false` | , | Startup raises without it. |
| `ALLOWED_HOSTS` | yes | `localhost,127.0.0.1` | Comma-separated. The API's own hostnames: the host in `NEXT_PUBLIC_API_BASE_URL`, plus whatever the load balancer's health check sends. |
| `FRONTEND_URLS` | yes | `http://localhost:3000` | Comma-separated, full `scheme://host[:port]`. Drives CORS, CSRF trust, and the allauth redirect URLs. |
| `COOKIE_DOMAIN` | prod | unset | The shared parent, e.g. `.biashawk.example`, so the session cookie the API sets reaches the frontend host. Leave unset when both are on one host. |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | yes | , | Startup raises without them. |
| `DB_HOST` | yes | `127.0.0.1` | Postgres' service name or hostname, not localhost. |
| `DB_PORT` | yes | `5432` | The container port. `5442` is the host-side publish only. |
| `DB_CONN_MAX_AGE` | no | `60` | Seconds a connection is reused. |
| `MEDIA_ROOT` | no | `backend/media` | Uploads land here. Must point at the same volume as the worker's. |
| `TIME_ZONE` | no | `Europe/Athens` | |
| `LOG_LEVEL` | no | `INFO` | Level of the `core` logger. |
| `SESSION_COOKIE_AGE` | no | `604800` | Seconds , 7 days. |
| `SECURE_HSTS_SECONDS` | no | `2592000` | Applied only when `DEBUG=false`. |
| `ACCOUNT_EMAIL_VERIFICATION` | no | `none` | Set to `mandatory` once SMTP exists. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | optional | unset | The provider registers only when both are present; absent means the button is simply not offered. |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | optional | unset | Same. |
| `SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD` | optional | unset | Read by `manage.py initialize_superuser` in the entrypoint. Either one unset skips the step; it never overwrites an existing account. |
| `GUNICORN_WORKERS` | no | `4` | Read by `docker/api-entrypoint.sh`, not by Django. Not in `docker.env` today. |
| `OPENWEBUI_BASE_URL` | yes | `""` | Needed here as well as on the worker , `/rag/query` calls the LLM in this process. |
| `OPENWEBUI_API_KEY` | yes | `""` | |
| `OPENWEBUI_CHAT_MODEL` | no | `datalab-1:latest` | The `:latest` tag is part of the id , Open WebUI answers `Model not found` without it. |
| `OPENWEBUI_TIMEOUT` | no | `180` | Seconds. |
| `OPENWEBUI_EMBED_MODEL` | no | `nomic-embed-text:v1.5` | Served by Open WebUI on the server's GPU. Must equal the worker's. |
| `RERANKER_MODEL` | no | `cross-encoder/ms-marco-MiniLM-L-6-v2` | |
| `EMBEDDING_DIM` | yes | `768` | Must equal the worker's , it is the declared width of the pgvector column. |
| `RAG_TOP_K` | no | `30` | |
| `RAG_TOP_N_RERANK` | no | `3` | |
| `RAG_USE_HYDE` | no | `false` | |

Not needed: `JOB_*`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `POSTGRES_*`.

#### `worker`

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DEBUG` | yes | `False` | Keep identical to the API's. |
| `DJANGO_SECRET_KEY` | yes when `DEBUG=false` | , | An import-time requirement in `settings.py`. The worker verifies no signatures, but the setting still has to be present. |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | yes | , | |
| `DB_HOST` | yes | `127.0.0.1` | |
| `DB_PORT` | yes | `5432` | |
| `DB_CONN_MAX_AGE` | no | `60` | Each runner thread holds its own connection. |
| `MEDIA_ROOT` | no | `backend/media` | The same volume the API writes uploads to , jobs read the files back from here. |
| `TIME_ZONE` | no | `Europe/Athens` | |
| `LOG_LEVEL` | no | `INFO` | |
| `JOB_THREADS` | no | `8` | Concurrent runner threads. |
| `JOB_POLL_SECONDS` | no | `2` | Idle poll interval. |
| `JOB_MAX_ATTEMPTS` | no | `3` | Attempts before a job is marked failed. |
| `JOB_STALE_SECONDS` | no | `1800` | A lock older than this is treated as a dead worker and the job returns to the queue. Not in `docker.env` today. |
| `OPENWEBUI_BASE_URL` | yes | `""` | |
| `OPENWEBUI_API_KEY` | yes | `""` | |
| `OPENWEBUI_CHAT_MODEL` | no | `datalab-1:latest` | The `:latest` tag is part of the id , Open WebUI answers `Model not found` without it. |
| `OPENWEBUI_TIMEOUT` | no | `180` | Seconds. Long jobs make this the one that matters. |
| `OPENWEBUI_EMBED_MODEL` | no | `nomic-embed-text:v1.5` | Served by Open WebUI on the server's GPU. Must equal the API's. |
| `RERANKER_MODEL` | no | `cross-encoder/ms-marco-MiniLM-L-6-v2` | |
| `EMBEDDING_DIM` | yes | `768` | Must equal the API's. |
| `CHUNK_SIZE` | no | `1000` | Ingestion only , worker-only. |
| `CHUNK_OVERLAP` | no | `200` | Ingestion only , worker-only. |
| `RAG_TOP_K` | no | `30` | The extraction agents retrieve per question. |
| `RAG_TOP_N_RERANK` | no | `3` | |
| `RAG_USE_HYDE` | no | `false` | |

Not needed: `ALLOWED_HOSTS`, `FRONTEND_URLS`, `COOKIE_DOMAIN`,
`SESSION_COOKIE_AGE`, `SECURE_HSTS_SECONDS`, `ACCOUNT_EMAIL_VERIFICATION`,
`GUNICORN_WORKERS`, `GOOGLE_*`, `GITHUB_*`, `SUPERUSER_*`, `POSTGRES_*`. The
first few are still read by `settings.py` in this process, but nothing here
serves a request, so their defaults are never consulted.

#### `frontend`

One variable, and it is a **build argument, not a runtime one**.

| Variable | Where | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | build | `NEXT_PUBLIC_*` is inlined into the client bundle by `next build`. It is passed as the `args:` entry under `frontend.build` in `compose.yml` and as `ARG`/`ENV` in `Dockerfile.frontend`. Setting it in the runtime environment of the built container changes nothing , the value is already compiled in. Rebuild to change it. |

The runner stage sets `NODE_ENV`, `PORT`, `HOSTNAME` and
`NEXT_TELEMETRY_DISABLED` itself; override `PORT` / `HOSTNAME` only if the
container has to listen somewhere else. Nothing else under `frontend/` reads
`process.env` , the only two call sites are `next.config.ts` and `lib/api.ts`,
both for this one variable.

So the frontend container takes **no secrets file at all**: `compose.yml` gives
it no `env_file`, so none of the backend's secrets reach the Node process.

### Values that have to agree across containers

| Value | Where |
|---|---|
| database name, user, password | `POSTGRES_*` on `postgres` ↔ `DB_*` on `api` and `worker` |
| `OPENWEBUI_EMBED_MODEL` + `EMBEDDING_DIM` | `api` ↔ `worker`. The worker writes the vectors and the API queries them against a column whose width is fixed at migration time. Changing the model changes that width and invalidates every stored chunk , `manage.py check_embeddings` says so before inserts start failing. |
| `MEDIA_ROOT` | `api` ↔ `worker`, and the same mounted volume. The API writes uploads; the worker reads them. |
| `DEBUG` | `api` ↔ `worker` |
| API hostname | the host in the frontend's build-time `NEXT_PUBLIC_API_BASE_URL` has to appear in the API's `ALLOWED_HOSTS` |
| frontend origin | the browser origin serving the frontend has to appear in the API's `FRONTEND_URLS`, or CORS and CSRF both reject it |

`DJANGO_SECRET_KEY` must be set on both `api` and `worker`, but the two need not
be equal , nothing in the worker verifies a signature. Keep them equal anyway;
there is no reason to rotate two.

### Secrets

The only real secrets are `DJANGO_SECRET_KEY`, `DB_PASSWORD` /
`POSTGRES_PASSWORD`, `OPENWEBUI_API_KEY`, `GOOGLE_CLIENT_SECRET`,
`GITHUB_CLIENT_SECRET` and `SUPERUSER_PASSWORD`. Split by container: `postgres`
holds one, `api` holds all six, `worker` holds three (`DJANGO_SECRET_KEY`,
`DB_PASSWORD`, `OPENWEBUI_API_KEY`), and `frontend` holds none.

Never reuse development values in production. Generate a fresh
`DJANGO_SECRET_KEY` and database password, issue a dedicated Open WebUI key, and
create separate OAuth client secrets in the Google and GitHub consoles. Leave
`SUPERUSER_EMAIL` / `SUPERUSER_PASSWORD` unset in production, or set a strong,
unique password; `initialize_superuser` never overwrites an existing account.

## Running

Everything in Docker:

```bash
docker compose up -d --build
```

- API , http://localhost:8000/api/health
- Admin , http://localhost:8000/admin/
- Frontend , http://localhost:3000
- Postgres , `localhost:5442`

Backend against the compose Postgres, with autoreload:

```bash
docker compose up -d postgres
```

```bash
cd backend && python manage.py runserver
```

The job runner is a second process in local development:

```bash
cd backend && python manage.py runjobs --threads 8
```

Frontend:

```bash
cd frontend && npm run dev
```

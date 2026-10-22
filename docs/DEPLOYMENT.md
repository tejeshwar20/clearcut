# Deployment

## Production Server

Python 3.11 or newer is required. From the repository root:

```powershell
python -m pip install -r requirements.txt
python serve.py
```

Open http://127.0.0.1:8080. Waitress runs on Windows and Linux with eight worker
threads, no debugger, bounded uploads, and request rate limits. `PORT`, `HOST`,
and `CLEARCUT_THREADS` configure the listener. Keep the production listener
behind a firewall and TLS reverse proxy.

On an empty database, startup imports `data/catalog_seed.json`, containing 100
generated reports and citations, not original review prose. Existing data is
never overwritten. `CLEARCUT_REPORT_DB` selects a writable persistent location;
`CLEARCUT_SEED_PATH` selects another seed. SQLite deployment is intended for one
application instance. Do not share a SQLite file between scaled containers or
use ephemeral storage for data that must survive redeployment.

## Optional Editorial Model

Default `CLEARCUT_WRITER=local` needs no key or model download. It writes from
aspect verdicts and controlled, spoiler-screened observations. It cannot
produce detailed prose when the source evidence is sparse.

For model-assisted prose, configure the host's environment/secret settings:

| Setting | Value |
| --- | --- |
| `CLEARCUT_WRITER` | `openai` |
| `CLEARCUT_MODEL` | `gpt-4.1-mini`, or a compatible structured-output model |
| `OPENAI_API_KEY` | Your key, entered directly in the host's secret settings |

Do not paste keys into chat, source code, Docker build arguments, or Git. The
example environment file is a reference; Python does not automatically load it.
Docker can load a private environment file with `--env-file`.
Set provider-side spending limits before exposing a public deployment. Fresh
generation costs money; cached reports do not call the model. After enabling
the provider, use Refresh to regenerate an existing title.

Only categorical findings and controlled plot-free descriptions are sent to
the provider, not original reviews, synopses, or user identifiers. Output needs
known evidence references and passes structural, spoiler-cue, and unverified-
detail checks. Timeout or invalid output uses local fallback. Missing model
credentials mark readiness as failed when model mode is explicitly required.
References are grounding aids, not proof that every generated claim is entailed.
Human review is still required before a public launch.

The live model has **not** been exercised here because no key was supplied.
Mocked provider tests verify success/failure handling and validation, not live
model writing quality.

## Docker

```powershell
docker build -t clearcut .
docker run --rm -p 8080:8080 --mount source=clearcut-data,target=/data clearcut
```

The image runs as a non-root user and includes a health check. A named volume
persists SQLite; the safe seed is included in the image. Local databases,
environment files, and test artifacts are excluded. Supply secrets at runtime,
for example with `--env-file .env`, never while building.

The image was not built/run here: Docker CLI is installed, but its engine is
stopped. Start Docker Desktop before running these commands.
On a container host, use `python serve.py`, port `8080` (or its supplied `PORT`),
`/readyz` for readiness, and a persistent writable mount at `/data` with
`CLEARCUT_REPORT_DB=/data/clearcut.sqlite3`. TLS, domain routing, hosting
credentials, and network policy belong to the host.

## Operations

- `/healthz`: process liveness, with no external dependency calls.
- `/readyz`: database access and required writer configuration. It does not
  spend model tokens or certify upstream availability.
- Fresh movie analysis: 10 requests/minute/client; manual analysis and import:
  20/minute; search: 60/minute. Responses include rate-limit headers.
- Default rate storage is process-local memory, suitable for one Waitress
  process. Set `CLEARCUT_RATE_STORAGE` to a Redis URI for shared limits; keep
  credentials in host secrets. Redis itself was not live-tested here.
- Do not enable `CLEARCUT_TRUST_PROXY=1` unless one trusted reverse proxy is
  the only route to the app. Set `CLEARCUT_PROXY_IP` to that proxy's exact IP
  address; empty or wildcard values are rejected. Waitress accepts client-
  identity headers only from that address. Default is disabled.
- Upstream retrieval has time and size bounds. Cached reports work during
  source failures. Refresh is explicit, not continuous polling; access-denied
  and rate-limited pages are not bypassed.
- Original review text is transient. Back up SQLite and the safe seed, not raw
  review corpora. Source licenses and attribution still apply.

Refresh the catalog and deployment seed:

```powershell
python build_catalog.py --limit 100 --workers 1 --refresh
python build_catalog.py --export-seed data/catalog_seed.json
python -m pytest -q
```

With model mode enabled, bulk refresh may make one paid model request per
admitted title. The bundled seed used local mode and zero model calls.
This is a tested single-instance server configuration, not high availability,
perfect spoiler detection, or externally audited language quality. Load testing,
independent review-quality evaluation, backups, TLS, monitoring, and source/
provider licensing review remain public-launch requirements.
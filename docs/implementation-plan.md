# Implementation Plan — UDN NBA 焦點新聞 Scraper

## Tech Stack

- **Backend:** Django, Django REST Framework, Django Channels
- **Database:** PostgreSQL
- **Cache / Broker:** Redis
- **Task Queue:** Celery + Celery Beat
- **Containerization:** Docker, Docker Compose
- **Frontend:** HTML + JavaScript (fetch API)

---

## Data Model: `News`

| Field              | Type                          | Notes                                          |
| ------------------ | ----------------------------- | ---------------------------------------------- |
| `id`               | `AutoField` (PK)             | Django default                                 |
| `title`            | `CharField(max_length=500)`   |                                                |
| `author`           | `CharField(max_length=200)`   | `blank=True` — some articles may omit author   |
| `published_at`     | `DateTimeField`               | Original publish time from UDN                 |
| `source_name`      | `CharField(max_length=100)`   | e.g. "聯合報"                                  |
| `source_url`       | `URLField(unique=True)`       | Deduplication key                              |
| `content`          | `TextField`                   | Sanitized HTML                                 |
| `hero_image_url`   | `URLField`                    | `blank=True`                                   |
| `hero_image_caption` | `CharField(max_length=300)` | `blank=True`                                   |
| `created_at`       | `DateTimeField(auto_now_add)` | When we scraped it                             |
| `updated_at`       | `DateTimeField(auto_now)`     | When our record was last modified              |

Indexes: `published_at` (ordering), `source_url` (unique, dedup lookups).

---

## Phase 1 — Project Scaffolding & Docker Compose

### Goal

Get a running Django project inside Docker with PostgreSQL connected.

### Tasks

1. Create Django project (`config/`) and app (`news/`).
2. Write `Dockerfile` for the Django app (Python 3.12, pip install).
3. Write `docker-compose.yml` with two services:
   - `web` — Django dev server (port 8000)
   - `db` — PostgreSQL 16
4. Create `.env.example` with:
   - `DJANGO_SECRET_KEY`
   - `DATABASE_URL` or individual `POSTGRES_*` vars
   - `DEBUG=True`
5. Configure `settings.py`:
   - Read config from environment variables.
   - Set `DATABASES` to use PostgreSQL.
   - Set `ALLOWED_HOSTS`.
6. Run initial migrations and create a superuser.

### Done When

- `docker compose up` starts both services.
- Django connects to PostgreSQL — migrations run cleanly.
- Admin page (`/admin/`) is accessible and login works.

---

## Phase 2 — News Model

### Goal

Define the `News` model so all subsequent work (scraper, API, frontend) builds on a stable schema.

### Tasks

1. Create `News` model in `news/models.py` with the fields listed above.
2. Add `Meta`:
   - `ordering = ['-published_at']`
   - `indexes` on `published_at`.
3. Register the model in `news/admin.py` with a basic `ModelAdmin` (list display, search fields).
4. Run `makemigrations` and `migrate`.

### Done When

- Can create, edit, and view a `News` object in Django admin.
- `source_url` uniqueness constraint is enforced (inserting a duplicate raises `IntegrityError`).

---

## Phase 3 — Manual Scraper (Management Command)

### Goal

Scrape the "焦點新聞" carousel from `http://tw-nba.udn.com/nba/index`, follow each article link, extract full content, and save to DB.

### Tasks

1. Add `requests` and `beautifulsoup4` to dependencies.
2. Create `news/management/commands/scrape_news.py`.
3. Implement two-step scraping:
   - **Step 1 — Index page:** Fetch the index page, parse the carousel section to extract article URLs and basic metadata (title, thumbnail).
   - **Step 2 — Article pages:** For each URL, fetch the article page and extract: title, author, published_at, content (sanitized HTML), hero image URL, hero image caption, source name.
4. Deduplication: Before saving, check if `source_url` already exists. Skip if it does.
5. Error handling: Log and continue on per-article failures (don't let one broken article stop the whole batch).
6. Add a small delay between requests (1-2 seconds) for politeness.

### Scraping Details (SSR)

The site is server-side rendered, so `requests` + `BeautifulSoup` is sufficient — no headless browser needed.

- Target: the carousel/slider block in the "焦點新聞" section of the index page.
- Inspect the DOM to identify the correct container and link selectors.
- For article pages: extract the main article body, strip unwanted elements (ads, related articles, navigation), keep meaningful HTML structure (paragraphs, images, blockquotes).

### Done When

- `docker compose exec web python manage.py scrape_news` populates the DB with real articles.
- Running it again does NOT create duplicates.
- Each article has all fields filled (where available from the source).

---

## Phase 4 — REST API (DRF)

### Goal

Expose the news data via a clean REST API with list and detail endpoints.

### Tasks

1. Add `djangorestframework` to dependencies.
2. Create two serializers in `news/serializers.py`:
   - `NewsListSerializer` — lightweight fields: `id`, `title`, `author`, `published_at`, `hero_image_url`. Excludes `content` for performance.
   - `NewsDetailSerializer` — all fields including `content`.
3. Create a `NewsViewSet` in `news/views.py` (or use `ListAPIView` / `RetrieveAPIView`):
   - `GET /api/news/` — paginated list, ordered by `-published_at`.
   - `GET /api/news/<id>/` — single article with full content.
4. Configure pagination in DRF settings (e.g., `PageNumberPagination`, page size 10).
5. Wire up URL routing in `news/urls.py` and include in `config/urls.py`.
6. Write basic API tests:
   - List endpoint returns paginated results.
   - Detail endpoint returns the correct article with all fields.
   - 404 for non-existent article ID.

### Done When

- `GET /api/news/` returns a paginated JSON response with articles.
- `GET /api/news/<id>/` returns a single article with full content.
- Responses are well-structured, fields match the model.

---

## Phase 5 — Frontend (HTML + AJAX)

### Goal

Build two minimal pages that consume the DRF API via JavaScript `fetch()`.

### Tasks

1. Create Django views that serve HTML templates (or static HTML):
   - `/` or `/news/` — News list page.
   - `/news/<id>/` — News detail page.
2. **List page:**
   - On load, fetch `GET /api/news/` and render article cards (title, author, date, thumbnail).
   - Pagination controls (previous / next) that fetch the appropriate page from the API.
   - Each card links to the detail page.
3. **Detail page:**
   - On load, fetch `GET /api/news/<id>/` and render: title, author, date, hero image, full HTML content.
   - Back button to return to the list.
4. Minimal styling — clean, readable, functional. No CSS framework required but basic layout should be pleasant.

### Done When

- User can open the list page and see scraped articles.
- User can click an article and see its full content.
- Pagination works correctly on the list page.

---

## Phase 6 — README & Cleanup (Submittable Checkpoint)

### Goal

Make the repo clean, documented, and ready for review. After this phase, the project is a complete, submittable take-home assignment covering all basic requirements.

### Tasks

1. Write a comprehensive `README.md`:
   - Project overview.
   - How to run: `docker compose up` + any setup steps.
   - Environment variables (reference `.env.example`).
   - How to run the scraper manually.
   - API endpoint documentation (list + detail, request/response examples).
   - Project structure overview.
2. Clean up code:
   - Remove dead code, leftover comments, debug prints.
   - Ensure consistent code style.
3. Add basic tests if not yet done:
   - Model: creation, uniqueness constraint.
   - API: list pagination, detail response.
   - Scraper: parser extracts fields from a sample HTML fixture.
4. Verify end-to-end: `docker compose up` → run scraper → open browser → list page works → detail page works.

### Done When

- A reviewer can clone the repo, read the README, run `docker compose up`, and see everything work without asking questions.
- This is the **minimum viable submission** — all basic requirements are met.

---

## Phase 7 — Celery + Redis: Scheduled Scraping (Advanced)

### Goal

Automate the scraper to run on a schedule using Celery Beat.

### Tasks

1. Add `celery`, `redis`, `django-celery-beat` (or hardcoded schedule) to dependencies.
2. Add services to `docker-compose.yml`:
   - `redis` — Redis 7.
   - `celery_worker` — runs Celery worker (same Django image).
   - `celery_beat` — runs Celery Beat scheduler (same Django image).
3. Configure Celery in `config/celery.py`:
   - Broker: `redis://redis:6379/0`
   - Result backend: Redis (or disabled if not needed).
4. Create Celery task `news/tasks.py`:
   - `scrape_news_task` — wraps the existing scraper logic from the management command.
5. Configure Beat schedule: run `scrape_news_task` every N minutes (e.g., 10 minutes).
6. Ensure the management command still works independently (reuse shared scraper logic).

### Done When

- `docker compose up` starts all 5 services (web, db, redis, worker, beat).
- New articles are scraped automatically on schedule without manual intervention.
- Logs show the periodic task executing and reporting results (new articles found / skipped duplicates).

---

## Phase 8 — WebSocket: Real-Time Notifications (Advanced)

### Goal

Notify the frontend immediately when new articles are scraped, without requiring a page refresh.

### Tasks

1. Add `channels` and `channels-redis` to dependencies.
2. Switch Django from WSGI to ASGI:
   - Create `config/asgi.py` with Channels routing.
   - Update `docker-compose.yml` web service to use Daphne or Uvicorn instead of the default runserver/Gunicorn.
3. Create a WebSocket consumer `news/consumers.py`:
   - `NewsConsumer` — on connect, join a group `news_updates`; on disconnect, leave group.
4. Configure channel layer in `settings.py` to use Redis.
5. In the Celery scrape task (`news/tasks.py`):
   - After saving a new article, send a message to the `news_updates` group via the channel layer.
   - Use `async_to_sync(channel_layer.group_send)` since Celery tasks are synchronous.
   - Message payload: article `id`, `title`, `published_at` (enough for the frontend to show a notification or prepend to the list).
6. Update the frontend list page:
   - On page load, open a WebSocket connection to `ws://<host>/ws/news/`.
   - On receiving a message, show a notification (e.g., a banner "N new articles available") or auto-prepend the new article to the list.

### Done When

- When the scraper finds and saves a new article, the frontend list page receives the notification in real time.
- No page refresh required — the user sees a prompt or the list updates automatically.

---

## Phase 9 — Performance Optimization: 100 QPS (Advanced)

### Goal

Ensure the news list API can handle at least 100 requests per second.

### Tasks

1. **Redis caching on the list API:**
   - Use `django-redis` as the cache backend.
   - Cache the list API response with a short TTL (e.g., 30-60 seconds).
   - Invalidate the cache when the scraper saves a new article (same event that triggers WebSocket notification).
2. **Database optimization:**
   - Confirm DB index on `published_at` exists.
   - Use `only()` or `defer()` to avoid loading `content` in list queries if the serializer doesn't already exclude it.
3. **Serialization optimization:**
   - `NewsListSerializer` should already exclude `content` (done in Phase 4).
   - Verify no unnecessary joins or N+1 queries.
4. **Web server:**
   - Run with Gunicorn + Uvicorn workers (or Daphne) with multiple worker processes.
   - Configure in `docker-compose.yml`.
5. **Pressure test:**
   - Add `locust` or use `wrk` to run a load test against the list endpoint.
   - Target: sustain 100 QPS with acceptable latency (p95 < 500ms).
   - Document the results.

### Done When

- Pressure test shows the list API sustains 100+ QPS.
- Optimizations are documented (what was done and why).

---

## Phase 10 — Deployment (Skipped for Now)

Deferred. The Docker Compose setup is deployment-ready; a real deployment would add:
- Nginx reverse proxy, production ASGI server, SSL, managed database, CI/CD.

---

## Priority & Time Management

| Priority   | Phases     | Status                     |
| ---------- | ---------- | -------------------------- |
| **Must do** | 1 → 6     | Covers all basic requirements, submittable. |
| **Should do** | 7        | Scheduled scraping — strongest advanced signal for backend role. |
| **Nice to have** | 8, 9 | WebSocket + performance — do if time allows. |
| **Skip**   | 10         | Deployment deferred.       |

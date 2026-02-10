# Product Requirements Document: ESG Newsletter Aggregation System

**Version:** 1.0
**Author:** Derived from ESG Newsletter System v07/v08 by Max Polwin
**Date:** 2026-02-10
**Status:** Reference Specification

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Module Specifications](#3-module-specifications)
4. [Data Models](#4-data-models)
5. [External API Integrations](#5-external-api-integrations)
6. [Keyword Configuration](#6-keyword-configuration)
7. [HTML Report Generation](#7-html-report-generation)
8. [Email Distribution](#8-email-distribution)
9. [Data Persistence & Deduplication](#9-data-persistence--deduplication)
10. [File Management & Cleanup](#10-file-management--cleanup)
11. [Configuration & Environment](#11-configuration--environment)
12. [Error Handling & Resilience](#12-error-handling--resilience)
13. [Logging & Observability](#13-logging--observability)
14. [Dependencies](#14-dependencies)
15. [Deployment](#15-deployment)
16. [Security Considerations](#16-security-considerations)
17. [Directory Structure](#17-directory-structure)
18. [Appendix: RSS Feed Sources](#appendix-a-rss-feed-source-categories)
19. [Appendix: Trusted Email Senders](#appendix-b-trusted-email-sender-categories)

---

## 1. Overview

### 1.1 Purpose

The ESG Newsletter Aggregation System is an automated content curation pipeline that monitors 700+ sources for Environmental, Social, and Governance (ESG) content. It aggregates articles, papers, podcasts, and videos, then generates a professional HTML email newsletter delivered to configured recipients.

### 1.2 Problem Statement

ESG professionals must track regulatory changes, academic research, and market developments across hundreds of fragmented sources. Manual monitoring is impractical at this scale. This system automates daily aggregation, deduplication, and delivery of relevant ESG content.

### 1.3 Core Capabilities

| Capability | Description |
|---|---|
| Multi-source aggregation | RSS feeds (700+), email newsletters (150+ trusted senders), academic papers, podcasts, YouTube videos |
| Keyword-based filtering | 40+ positive ESG keywords with negative keyword exclusion |
| Content deduplication | SQLite-backed 30-day deduplication window prevents repeat content |
| AI-powered summaries | Mistral AI generates executive summaries for each newsletter |
| HTML report generation | Professional responsive email with keyword visualizations and article cards |
| Automated email delivery | SMTP-SSL delivery to multiple recipients with attachments |
| Self-maintaining | Automatic log rotation, file cleanup, and feed health tracking |

### 1.4 Execution Model

The system runs as a **batch job**, typically scheduled daily via cron. A single invocation of `main.py` performs the full pipeline: cleanup, aggregation across all 5 source types, report generation, and email delivery.

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
                        ┌──────────────┐
                        │   main.py    │
                        │ (Orchestrator)│
                        └──────┬───────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
   │  Processors  │   │   Output     │   │  Maintenance │
   │              │   │              │   │              │
   │ academic_    │   │ html_        │   │ cleanup_     │
   │  processor   │   │  generator   │   │  files       │
   │ rss_         │   │ email_       │   │ email_       │
   │  processor   │   │  sender      │   │  dedup       │
   │ podcast_     │   │ mistral      │   │ content_     │
   │  processor   │   │  (AI summary)│   │  storage     │
   │ youtube_     │   │              │   │              │
   │  processor   │   │              │   │              │
   │ email_       │   │              │   │              │
   │  processor   │   │              │   │              │
   └─────────────┘   └──────────────┘   └──────────────┘
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │   Shared Layer       │
                    │ config.py            │
                    │ keywords_config.py   │
                    │ utils.py             │
                    │ browser_setup.py     │
                    └─────────────────────┘
```

### 2.2 Processing Pipeline (Execution Order)

The pipeline executes sequentially in this fixed order:

| Step | Module | Description |
|------|--------|-------------|
| 1 | `cleanup_files.py` | Remove stale logs, HTML files, and attachments |
| 2 | `academic_processor.py` | Search Semantic Scholar for academic papers |
| 3 | `rss_processor.py` | Fetch and filter 700+ RSS feeds |
| 4 | `podcast_processor.py` | Search Spotify for podcast episodes |
| 5 | `youtube_processor.py` | Search YouTube Data API for videos |
| 6 | `email_processor.py` | Fetch and filter email newsletters via IMAP |
| 7 | (combine) | Merge all articles and keyword counts |
| 8 | `html_generator.py` | Generate HTML report with AI summary |
| 9 | `email_sender.py` | Deliver report via SMTP-SSL |

### 2.3 Data Flow

Each processor returns a tuple: `(articles: list[dict], keyword_counts: dict[str, int])`.

After all processors complete:
- All article lists are concatenated into a single list.
- All keyword count dicts are merged by summing counts per keyword.
- The combined data feeds into `html_generator.generate_html()`.
- The email processor also returns `attachments: list[str]` (file paths).
- If total articles > 0, the report is generated and emailed. Otherwise, no email is sent.

---

## 3. Module Specifications

### 3.1 Academic Processor (`academic_processor.py`)

**Purpose:** Search Semantic Scholar for peer-reviewed papers matching ESG keywords.

**Entry Point:** `process_academic_papers() -> (list[dict], dict[str, int])`

**Behavior:**
1. Iterate over each keyword from `keywords_config.py`.
2. Call Semantic Scholar API: `GET https://api.semanticscholar.org/graph/v1/paper/search` with query=keyword, limit=200.
3. For each paper, fetch detailed metadata (authors, abstract, citation count, venue, fields of study).
4. If no abstract is available from the API, attempt PDF extraction via `PyPDF2`.
5. If PDF extraction fails, generate a fallback abstract using the Perplexity AI API.
6. Filter results using positive and negative keyword matching.
7. Return up to 10 papers per keyword.

**Constraints:**
- **Rate limiting:** Minimum 5 seconds between Semantic Scholar API calls.
- **Perplexity rate limiting:** Minimum 2.0 seconds between calls.
- **Maximum execution time:** 2.5 hours total.
- **Max papers per keyword:** 10.
- **Max papers searched per keyword:** 200.

**Output Article Fields:**
- `id`, `title`, `url`, `snippet` (abstract), `abstract_source` ("api" | "fallback" | "pdf"), `authors`, `venue`, `citation_count`, `source_type` = "academic", `date`, `keywords_found`

---

### 3.2 RSS Processor (`rss_processor.py`)

**Purpose:** Fetch and filter articles from 700+ RSS feeds.

**Entry Point:** `process_rss_feeds() -> (list[dict], dict[str, int])`

**Behavior:**
1. Iterate over all RSS feed URLs defined in `config.RSS_FEEDS`.
2. For each feed, fetch via `feedparser` with `requests` as HTTP backend.
3. Extract articles published within the last 24 hours (`TIME_THRESHOLD`).
4. For each article, attempt full content extraction via HTTP request + BeautifulSoup parsing.
5. Filter articles using positive/negative keyword matching against title + content.
6. Deduplicate against the SQLite content database.
7. Track and log problematic/failing feeds.

**Retry Mechanism:**
- 5 retry attempts per feed.
- Exponential backoff between retries.
- 30-second timeout per HTTP request.
- Falls back to Selenium browser automation for JavaScript-heavy sites.

**Browser Automation (Selenium):**
- Headless Chrome via `webdriver-manager`.
- Resolution: 1920x1080.
- Images disabled for performance.
- Automation flags hidden.
- Language: en-US.

**Rate Limiting:** 10 requests per 60 seconds.

**Content Size Limit:** 5 MB max for full content extraction.

**Circuit Breaker:** Feeds that fail repeatedly are marked as problematic and skipped in subsequent requests within the same run. Failures are logged to `rss_analysis_details.log`.

**Output Article Fields:**
- `id` (MD5 hash of title + URL), `title`, `url`, `snippet`, `full_text`, `source_info` (feed title, domain, type), `date`, `keywords_found`, `image` (primary image URL), `images` (all image URLs), `source_type` = "rss"

---

### 3.3 Podcast Processor (`podcast_processor.py`)

**Purpose:** Search Spotify for ESG-related podcast episodes.

**Entry Point:** `process_podcasts() -> (list[dict], dict[str, int])`

**Behavior:**
1. Authenticate with Spotify API via OAuth2 Client Credentials flow.
2. Cache the access token to `cache/spotify_token.json`.
3. For each keyword, search the Spotify API for podcast episodes.
4. Filter by language (English, German, Spanish, French).
5. Filter by publication date (last 24 hours).
6. Match episodes against ESG keywords.

**Rate Limiting:** 5 API calls per second.

**Concurrency:** Uses `ThreadPoolExecutor` for parallel keyword searches.

**Token Caching:** Spotify OAuth token is cached to disk and reused until expiry.

**Output Article Fields:**
- `id`, `title`, `url`, `snippet` (episode description), `source_type` = "podcast", `podcast_duration`, `date`, `keywords_found`, `source_info`

---

### 3.4 YouTube Processor (`youtube_processor.py`)

**Purpose:** Search YouTube Data API v3 for ESG-related videos.

**Entry Point:** `process_videos() -> (list[dict], dict[str, int])`

**Behavior:**
1. Check remaining daily API quota.
2. Search for up to 30 keywords (quota-limited).
3. For each keyword, call `GET https://www.googleapis.com/youtube/v3/search` with `type=video`, `publishedAfter` = 24 hours ago.
4. Fetch video details (duration, statistics) via `GET https://www.googleapis.com/youtube/v3/videos`.
5. Filter using YouTube-specific positive/negative keywords.

**Quota Management:**
- Daily quota: 10,000 units.
- Search cost: 100 units per search.
- Video details cost: 1 unit per video.
- Maximum keywords per day: 30 (to stay within quota).
- Falls back to fewer keywords if quota is low.

**Logging:** Three separate log files via `youtube_logs.py`:
- `logs/youtube_api.log` - API request/response logs.
- `logs/youtube_errors.log` - Error-specific logs.
- `logs/youtube_debug.log` - Debug-level detail.

**Uses YouTube-specific keywords** (separate from general ESG keywords) defined in `keywords_config.py` as `youtube_keywords_positive` and `youtube_keywords_negative`.

**Output Article Fields:**
- `id`, `title`, `url`, `snippet` (video description), `source_type` = "youtube", `video_duration`, `date`, `keywords_found`, `source_info`

---

### 3.5 Email Processor (`email_processor.py`)

**Purpose:** Fetch and filter email newsletters from an IMAP mailbox.

**Entry Point:** `process_email_newsletters(cleanup_emails=True) -> (list[dict], dict[str, int], list[str])`

**Behavior:**
1. Connect to the IMAP server via `IMAP4_SSL`.
2. Search for emails received within the last 24 hours.
3. Filter emails against the trusted sender whitelist (150+ addresses in `config.py`).
4. Extract text content from both HTML and plain text parts.
5. Extract and save attachments (`.eml` files) to `ATTACHMENTS_DIR`.
6. Extract inline images.
7. Deduplicate against `cache/email_history.json`.
8. Optionally clean up emails older than `CLEANUP_THRESHOLD` (2 days).

**Third return value:** `attachments` - list of file paths to saved `.eml` attachment files.

**Output Article Fields:**
- `id` (hash of sender + subject + date), `title` (email subject), `url` (extracted from email body if available), `snippet`, `full_text`, `html_content`, `source_type` = "email", `date`, `keywords_found`, `images`, `source_info`

---

### 3.6 HTML Generator (`html_generator.py`)

**Purpose:** Generate a professional HTML email report from aggregated articles.

**Entry Point:** `generate_html(articles: list[dict], keyword_counts: dict[str, int]) -> str`

Returns the file path to the generated HTML file.

**Report Structure:**
1. **Header** - "Latest ESG Newsletter" title, timestamp, article count.
2. **Executive Summary** - AI-generated 3-bullet-point summary via Mistral API, or a statistics-based fallback.
3. **Keyword Bubbles** - Visual circular badges showing keyword names and their frequency counts.
4. **Article Cards** - Grouped by source type, each card displays:
   - Title (hyperlinked to source)
   - Source domain badge
   - Publication date
   - Snippet (truncated to 300 characters)
   - Source type indicator (RSS, Email, Academic, Podcast, YouTube)
   - Thumbnail image (when available)
5. **Footer** - Generation timestamp, system attribution, total article count.

**Styling:**
- Responsive design with 767px mobile breakpoint.
- Dark mode support via `@media (prefers-color-scheme: dark)`.
- Collapsible sections with JavaScript toggle.
- Color scheme driven by `config.COLORS`.

**File Output:** `latest_articles/latest_articles_YYYY-MM-DD_HH-MM-SS.html`

**Companion Files Generated:**
- `css/newsletter_styles.css` (via `utils.create_css_file()`)
- `css/newsletter_scripts.js` (via `utils.create_js_file()`)

---

### 3.7 Mistral AI Integration (`mistral.py`)

**Purpose:** Generate AI-powered executive summaries for the newsletter.

**Class:** `MistralAPI`

**Configuration:**
- Model: `mistral-small-latest`
- Max tokens: 300
- Temperature: 0.2
- Top-p: 0.9
- API endpoint: `https://api.mistral.ai/v1/chat/completions`
- Timeout: 60 seconds

**System Prompt:** Instructs the model to produce a 3-bullet-point summary of no more than 100 words total, formatted as HTML (`<ul>`/`<li>` tags) with linked citations.

**Fallback:** If the API call fails or returns empty, the system falls back to a statistics-based summary (article counts per source type).

**Attribution:** Appends "Summary generated by Mistral AI" in italicized small text below the summary.

---

### 3.8 Email Sender (`email_sender.py`)

**Purpose:** Deliver the generated HTML report via SMTP.

**Entry Point:** `send_email_with_attachments(html_file_path, recipients, attachments) -> bool`

**Behavior:**
1. Read the generated HTML file.
2. Connect to the SMTP server via `SMTP_SSL` on port 465.
3. Authenticate with `EMAIL_USER` / `EMAIL_PASSWORD`.
4. For each recipient, construct a MIME multipart message:
   - Subject: `"Latest Articles Update - YYYY-MM-DD"`
   - HTML body from the generated report.
   - Attached files (newsletter `.eml` files, CSS, JS).
5. Send individually to each recipient.
6. Return `True` only if all recipients received the email successfully.

**Convenience Function:** `send_latest_report()` - finds the most recent HTML file in `OUTPUT_DIR`, collects attachments from `ATTACHMENTS_DIR`, and sends.

---

## 4. Data Models

### 4.1 Article Object

Every processor produces articles conforming to this schema:

```
{
    "id": string,              // Unique identifier (MD5 hash of title + URL, or source-specific hash)
    "source_type": string,     // "rss" | "email" | "academic" | "podcast" | "youtube"
    "title": string,           // Article/episode/paper title
    "snippet": string,         // Short excerpt or abstract
    "full_text": string,       // Complete text content (when available)
    "url": string,             // Direct link to the source
    "date": datetime,          // Publication date
    "source_info": {
        "title": string,       // Feed name / publication name
        "domain": string,      // Source domain
        "type": string         // Feed type classification
    },
    "keywords_found": [string],// List of matched positive keywords
    "html_content": string,    // Raw HTML (email sources only)
    "images": [string],        // All image URLs found
    "image": string,           // Primary/thumbnail image URL
    "abstract": string,        // Academic paper abstract
    "abstract_source": string, // "api" | "fallback" | "pdf" (academic only)
    "authors": string,         // Author names (academic only)
    "venue": string,           // Publication venue (academic only)
    "citation_count": int,     // Citations (academic only)
    "podcast_duration": string,// Episode length (podcast only)
    "video_duration": string,  // Video length (YouTube only)
    "metadata": {}             // Additional source-specific metadata
}
```

### 4.2 SQLite Schema (Content Storage)

```sql
CREATE TABLE content (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_published TIMESTAMP,
    source_info TEXT,          -- JSON-encoded
    keywords TEXT,             -- JSON-encoded array
    metadata TEXT,             -- JSON-encoded
    status TEXT DEFAULT 'active'
);

CREATE INDEX idx_content_source_type ON content(source_type);
CREATE INDEX idx_content_date_published ON content(date_published);
```

**Database Location:** `cache/content_database.db`

### 4.3 Email Deduplication Tracking

```json
{
    "email_ids": ["hash1", "hash2", "..."],
    "last_updated": "2025-02-10T17:30:00"
}
```

**File Location:** `cache/email_history.json`

### 4.4 Spotify Token Cache

```json
{
    "access_token": "...",
    "token_type": "Bearer",
    "expires_at": 1234567890
}
```

**File Location:** `cache/spotify_token.json`

---

## 5. External API Integrations

### 5.1 Semantic Scholar API

| Property | Value |
|---|---|
| Base URL | `https://api.semanticscholar.org/graph/v1` |
| Authentication | None required (public API) |
| Endpoints used | `GET /paper/search`, `GET /paper/{paperId}` |
| Rate limit enforcement | 5-second minimum interval between calls |
| Max execution time | 2.5 hours |
| Papers per keyword | Up to 200 searched, 10 returned |

### 5.2 Perplexity AI API

| Property | Value |
|---|---|
| Authentication | API key via `PERPLEXITY_API_KEY` env var |
| Purpose | Generating fallback abstracts for academic papers |
| Rate limit enforcement | 2.0-second minimum interval between calls |
| Client library | `perplexity-python` |

### 5.3 Mistral AI API

| Property | Value |
|---|---|
| Base URL | `https://api.mistral.ai/v1` |
| Authentication | Bearer token via `MISTRAL_API_KEY` env var |
| Endpoint | `POST /chat/completions` |
| Model | `mistral-small-latest` |
| Temperature | 0.2 |
| Top-p | 0.9 |
| Max tokens | 300 |
| Timeout | 60 seconds |
| Purpose | Executive summary generation |

### 5.4 Spotify Web API

| Property | Value |
|---|---|
| Auth URL | `https://accounts.spotify.com/api/token` |
| Authentication | OAuth2 Client Credentials flow |
| Credentials | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` env vars |
| Token caching | Cached to `cache/spotify_token.json` |
| Rate limit | 5 calls/second |
| Concurrency | ThreadPoolExecutor |
| Languages | English, German, Spanish, French |

### 5.5 YouTube Data API v3

| Property | Value |
|---|---|
| Base URL | `https://www.googleapis.com/youtube/v3` |
| Authentication | API key via `YOUTUBE_API_KEY` env var |
| Endpoints | `GET /search`, `GET /videos` |
| Daily quota | 10,000 units |
| Search cost | 100 units/search |
| Video detail cost | 1 unit/video |
| Max keywords/day | 30 |

### 5.6 IMAP (Email Retrieval)

| Property | Value |
|---|---|
| Protocol | IMAP4_SSL |
| Credentials | `EMAIL_HOST`, `EMAIL_USER`, `EMAIL_PASSWORD` env vars |
| Time window | Last 24 hours |
| Filter | Trusted sender whitelist (150+ addresses) |

### 5.7 SMTP (Email Sending)

| Property | Value |
|---|---|
| Protocol | SMTP_SSL |
| Port | 465 |
| Credentials | `EMAIL_HOST`, `EMAIL_USER`, `EMAIL_PASSWORD` env vars |
| Recipients | `EMAIL_RECIPIENTS` env var (comma-separated) |

---

## 6. Keyword Configuration

### 6.1 Architecture

Keywords are defined in `keywords_config.py` and loaded at startup via `get_keywords()` which returns four sets:

1. **`keywords`** - General positive keywords (40+ terms)
2. **`negative_keywords`** - General exclusion keywords (20+ terms)
3. **`youtube_keywords_positive`** - YouTube-specific positive keywords (27 terms)
4. **`youtube_keywords_negative`** - YouTube-specific exclusion keywords (15 terms)

### 6.2 Matching Rules

- Keywords with leading/trailing spaces (e.g., `" ESG "`) use **exact word boundary matching**.
- Keywords without surrounding spaces match as **substrings** within text.
- Matching is **case-insensitive**.
- Negative keywords override positive matches (an article matching both is excluded).

### 6.3 General Positive Keywords (Complete List)

**EU Regulations:** EU Taxonomy, EU-Taxonomy, EU-Taxonomie, CSRD, SFRD, NFRD, Omnibus, CSDDD, Corporate Sustainability Due Diligence Directive, CSR Directive Implementation Act, CSR-RUG

**ESG Standards & Frameworks:** DNSH, Do No Significant Harm, Principal Adverse Impact, PAIs, GAR, Green Asset Ratio, ESRS, European Sustainability Reporting Standards, Sustainable Finance Disclosure, Deutscher Nachhaltigkeitskodex, DNK, PCAF, Partnership for Carbon Accounting Financials, SDGs, TNFD, NGFS, VSME, ISSB

**Climate & Environment:** Climate Risk, CBAM, EU Carbon Border Adjustment Mechanism, EU ETS, European Union Emissions Trading System, GHG Protocol, Treibhausgas, Green House Gase, EU Green Bonds Standard, EU GBS, planetary boundaries, EU Climate Transition Benchmark, EU CTB, Paris-Aligned, EU PAB, net zero, net-zero, decarbonize, decarbonise, carbon credit, biodiversity, renaturation, rewilding, Nature based, Nature-based, Nature Risk, Biodiversity Risk, NbS, Hydrogen, Wasserstoff, Decarbonising, Decarbonizing, climate scenario, climate policy, stranded asset, transition risk, physical risk, transition path, Carbon Removal, Carbon Farming, CRCF, CDR

**Finance & Governance:** ESG, Sustainable Finance, Sustainable Investment, Basel IV, Basel III, Basel regulation, MaRisk, Stress Test, ESG-Score, ESG-Rating, ESG Rating, ESG-Szenarioanalyse, Implied Temperature Rise, ITR-Score, ITR-Rating, Natural Capital, Grüner Pfandbrief, B Corp, Social Business, Social Enterprise

**Research & Reporting:** IPCC, COP 30, EOIPA, Attribution Science, Attributionsforschung, Klimafolgenforschung, LkSG, Lieferkettensorgfaltspflichtengesetz, Supply Chain Sourcing Obligations Act, EU Regulation on Deforestation-free Products, Swiss Climate Law, CO2 Act, CO2-Act, HR DD, HR Due Diligence, European Green Deal, Paris Agreement

**Other:** Join Impact Management, Environmentally Extended Input-Output, Sovereign Emissions Intensity, follow the money method

### 6.4 General Negative Keywords (Complete List)

BaFin warnt vor, Application deadline, gene, hydrogen bomb, hyrodgen bomb, Marisken, trabalho, Sustentabilidade, Mariskal, Conspiracy, Paluten, CRAFT ATTACK, Sustainy, TTPP, blyaaaaaaaaaaaaaaaaat, detox, Basti GHG, Detox, Blondie, MM36

### 6.5 YouTube-Specific Positive Keywords

ESG investing, sustainable finance, climate risk, EU taxonomy, CSRD, climate scenario, green bonds, climate scenario analysis, climate change finance, sustainable investing, ESG analysis, climate transition, decarboniz, sustainable banking, green finance, climate policy, ESG reporting, ESG strategy, sustainable economy, Omnibus package, CSDDD, climate finance, ESG metrics, climate stress test, climate transition plan, ESG disclosure, climate adaptation, ESG integration

### 6.6 YouTube-Specific Negative Keywords

conspiracy, fake news, climate hoax, ESG scam, sustainable scam, climate denial, ESG fraud, sustainable fraud, climate conspiracy, ESG conspiracy, sustainable conspiracy, climate scam, ESG hoax, AI-Driven, sustainable hoax, climate fraud, ESG denial, sustainable denial, fun fact

---

## 7. HTML Report Generation

### 7.1 Report File Naming

`latest_articles/latest_articles_YYYY-MM-DD_HH-MM-SS.html`

### 7.2 Report Sections (in order)

1. **Header**
   - Title: "Latest ESG Newsletter"
   - Generation timestamp
   - Total article count across all sources

2. **Executive Summary**
   - Primary: AI-generated via Mistral API (3 bullet points, max 100 words, HTML formatted with linked citations)
   - Fallback: Statistics-based summary showing article counts per source type
   - Attribution line: "Summary generated by Mistral AI"

3. **Keyword Frequency Bubbles**
   - Circular visual badges for each keyword that appeared in the results
   - Each bubble shows keyword name and occurrence count
   - Centered layout

4. **Article Cards** (grouped by source type)
   - **Title** as clickable hyperlink to source URL
   - **Source domain** badge
   - **Publication date**
   - **Snippet** (300 character max)
   - **Source type** indicator badge (RSS / Email / Academic / Podcast / YouTube)
   - **Thumbnail image** when available
   - **Collapsible sections** per source type grouping

5. **Footer**
   - Generation timestamp
   - System attribution
   - Total article count

### 7.3 Styling Specification

**Color Palette (Light Mode):**
| Token | Value | Usage |
|---|---|---|
| `primary` | `#00827C` | Headers, links, primary actions |
| `primary_dark` | `#00635F` | Hover states |
| `primary_light` | `#BDD7D6` | Badges, highlights |
| `secondary` | `#3B8589` | Secondary elements |
| `background` | `#e3f1ee` | Page background |
| `background_light` | `#F8F8FF` | Card backgrounds |
| `background_alt` | `#FFFFFF` | Alternate backgrounds |
| `text_dark` | `#333333` | Primary text |
| `text_medium` | `#444444` | Secondary text |
| `text_light` | `#666666` | Muted text |
| `accent` | `#5E9E9A` | Accent elements |
| `youtube_red` | `#FF0000` | YouTube source badge |
| `youtube_light` | `#FFE4E4` | YouTube badge background |

**Dark Mode Overrides** (activated via `@media (prefers-color-scheme: dark)`):
| Token | Value |
|---|---|
| `background` | `#1a1a1a` |
| `background_alt` | `#2a2a2a` |
| `text_dark` | `#f0f0f0` |
| `text_medium` | `#e0e0e0` |
| `text_light` | `#b0b0b0` |
| `primary` | `#00a39e` |
| `primary_light` | `#004d4a` |
| `accent` | `#4a8a86` |
| `border` | `#404040` |
| `card_background` | `#333333` |
| `link` | `#66b3b0` |
| `link_hover` | `#99c9c7` |

**Responsive Breakpoint:** 767px (mobile layout)

**JavaScript Features:**
- Collapsible section toggle (click to expand/collapse article groups)
- Dark mode manual toggle with `localStorage` persistence

---

## 8. Email Distribution

### 8.1 Email Format

| Property | Value |
|---|---|
| Subject | `"Latest Articles Update - YYYY-MM-DD"` |
| MIME type | `multipart/mixed` containing `multipart/alternative` (HTML body) |
| Body | Full HTML report |
| Attachments | Newsletter `.eml` files, `newsletter_styles.css`, `newsletter_scripts.js` |

### 8.2 Delivery Behavior

- Each recipient receives an individually addressed email (separate `To:` header).
- Attachments are validated for existence before attaching.
- Returns `True` only if **all** recipients received the email.
- Failed sends per recipient are logged individually.

---

## 9. Data Persistence & Deduplication

### 9.1 Content Database

- **Engine:** SQLite via SQLAlchemy ORM
- **Location:** `cache/content_database.db`
- **Purpose:** Store article metadata for deduplication and search
- **Operations:**
  - `store_content()` - Insert or update an article
  - `get_content_by_id()` - Retrieve by unique ID
  - `get_content_by_source()` - Filter by source type
  - `search_content()` - Full-text search across title and content
  - `update_content_status()` - Change article status
  - `cleanup_old_content()` - Archive articles older than threshold
  - `get_content_stats()` - Return aggregate statistics

### 9.2 Deduplication Configuration

| Setting | Value | Description |
|---|---|---|
| `DEDUPLICATION_ENABLED` | `True` | Master on/off switch |
| `DEDUPLICATION_WINDOW_DAYS` | `30` | How far back to check for duplicates |
| `DEDUPLICATION_METHOD` | `"strict"` | `"strict"` = exact ID match; `"fuzzy"` = similar content matching |

### 9.3 Article ID Generation

- **RSS:** `MD5(title + URL)`
- **Email:** `MD5(sender + subject + date)`
- **Academic:** Paper ID from Semantic Scholar API
- **Podcast/YouTube:** Platform-specific content ID

### 9.4 Email Deduplication

Separate from the content database. Maintains a JSON file at `cache/email_history.json` tracking seen email IDs.

---

## 10. File Management & Cleanup

### 10.1 Automatic Cleanup Rules

| File Type | Location | Max Age | Additional Rules |
|---|---|---|---|
| Log files (`.log`) | `latest_articles/` | 2 days | Rotate when > 1 MB |
| HTML reports (`.html`) | `latest_articles/` | 7 days | Always keep 3 newest |
| Attachments | `latest_articles/newsletter_attachments/` | 7 days | -- |
| Empty directories | All output directories | Immediate | Removed on each cleanup |

### 10.2 Log Rotation

When a log file exceeds 1 MB, it is renamed with a timestamp suffix (`newsletter_system_YYYY-MM-DD_HH-MM-SS.log`) and a fresh log file is created.

### 10.3 Cleanup Execution

`cleanup_old_files()` runs at the beginning of every `process_all()` invocation. Returns a statistics dict:
```python
{
    "logs_deleted": int,
    "html_deleted": int,
    "attachments_deleted": int
}
```

---

## 11. Configuration & Environment

### 11.1 Required Environment Variables

| Variable | Description |
|---|---|
| `EMAIL_HOST` | SMTP/IMAP server hostname |
| `EMAIL_USER` | Email account username (must be valid email format) |
| `EMAIL_PASSWORD` | Email account password |
| `EMAIL_RECIPIENTS` | Comma-separated list of recipient email addresses |
| `PERPLEXITY_API_KEY` | Perplexity AI API key |

### 11.2 Optional Environment Variables

| Variable | Description |
|---|---|
| `MISTRAL_API_KEY` | Mistral AI API key (for executive summaries; system falls back to statistics if absent) |
| `SPOTIFY_CLIENT_ID` | Spotify app client ID (podcast processing skipped if absent) |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key (video processing skipped if absent) |
| `ESG_BASE_DIR` | Override base directory (defaults to script location) |

### 11.3 Environment File

Environment variables are loaded from a `.env` file in the project root directory. The file is parsed manually (not via `python-dotenv` at runtime, though it is listed in dependencies). Format:

```
KEY=value
KEY="quoted value"
# Comments are supported
```

### 11.4 Time Thresholds

| Constant | Value | Purpose |
|---|---|---|
| `TIME_THRESHOLD` | `86400` (24 hours in seconds) | Maximum age for content to be included |
| `CLEANUP_THRESHOLD` | `2` (days) | Age after which emails are cleaned from mailbox |

---

## 12. Error Handling & Resilience

### 12.1 Global Error Handling

The `process_all()` function wraps the entire pipeline in a try/except block. Any unhandled exception is logged with full traceback and the function returns `False`.

### 12.2 Per-Processor Resilience

Each processor is independently fault-tolerant. If one processor fails entirely, the pipeline continues with the remaining processors. An empty article list is used for the failed processor.

### 12.3 Feed-Level Resilience (RSS)

| Mechanism | Behavior |
|---|---|
| Retry | 5 attempts with exponential backoff |
| Timeout | 30 seconds per request |
| Circuit breaker | Failing feeds are marked and skipped within the same run |
| Browser fallback | Selenium used for JavaScript-heavy sites that fail standard HTTP |

### 12.4 API Resilience

| API | Failure Behavior |
|---|---|
| Semantic Scholar | Logs error, skips paper, continues to next |
| Perplexity AI | Logs warning, skips abstract generation |
| Mistral AI | Falls back to statistics-based summary |
| Spotify | Logs error, returns empty podcast list |
| YouTube | Logs error, returns empty video list; quota checks prevent overuse |
| IMAP | Logs error, returns empty email list |
| SMTP | Logs error per failed recipient, returns partial success |

---

## 13. Logging & Observability

### 13.1 Main System Log

- **File:** `latest_articles/newsletter_system.log`
- **Level:** DEBUG
- **Format:** `%(asctime)s - %(levelname)s - %(message)s`
- **Rotation:** Automatic at 1 MB, renamed with timestamp

### 13.2 RSS Analysis Log

- **File:** `rss_analysis_details.log` (project root)
- **Content:** Detailed per-feed fetch results, keyword matches, failures

### 13.3 YouTube Logs

- **Directory:** `logs/`
- **Files:**
  - `youtube_api.log` - API request and response logging
  - `youtube_errors.log` - Error-specific logging
  - `youtube_debug.log` - Debug-level detail

### 13.4 Console Output

All major operations print progress to stdout in addition to file logging. This allows monitoring when run interactively.

---

## 14. Dependencies

### 14.1 Python Version

Python 3.7 or higher.

### 14.2 Package Dependencies

**Core:**
| Package | Min Version | Purpose |
|---|---|---|
| `requests` | 2.31.0 | HTTP client for API calls and feed fetching |
| `python-dotenv` | 1.0.0 | Environment variable loading |
| `beautifulsoup4` | 4.12.0 | HTML/XML parsing |
| `lxml` | 4.9.0 | XML parser backend |
| `feedparser` | 6.0.0 | RSS/Atom feed parsing |
| `nltk` | 3.8.0 | Natural language processing utilities |
| `pandas` | 2.0.0 | Data processing |
| `numpy` | 1.24.0 | Numerical operations |
| `PyPDF2` | 3.0.0 | PDF text extraction |

**API Clients:**
| Package | Min Version | Purpose |
|---|---|---|
| `openai` | 1.0.0 | OpenAI client (installed, not actively used) |
| `perplexity-python` | 0.1.0 | Perplexity AI for fallback abstracts |

**Email:**
| Package | Min Version | Purpose |
|---|---|---|
| `aiosmtplib` | 2.0.0 | Async SMTP support |
| `email-validator` | 2.0.0 | Email address validation |

**Database:**
| Package | Min Version | Purpose |
|---|---|---|
| `sqlalchemy` | 2.0.0 | ORM for SQLite content storage |
| `psycopg2-binary` | 2.9.0 | PostgreSQL adapter (available for future migration) |

**Browser Automation:**
| Package | Min Version | Purpose |
|---|---|---|
| `selenium` | (latest) | Headless Chrome for JavaScript-heavy feeds |
| `webdriver-manager` | (latest) | Automatic ChromeDriver management |

**Development & Testing:**
| Package | Min Version | Purpose |
|---|---|---|
| `pytest` | 7.0.0 | Test framework |
| `pytest-cov` | 4.0.0 | Coverage reporting |
| `pytest-asyncio` | 0.21.0 | Async test support |
| `black` | 23.0.0 | Code formatting |
| `flake8` | 6.0.0 | Linting |
| `mypy` | 1.0.0 | Static type checking |

### 14.3 System Dependencies

- **Google Chrome** (or Chromium) - Required for Selenium browser automation
- **ChromeDriver** - Managed automatically by `webdriver-manager`

---

## 15. Deployment

### 15.1 Execution Model

Single-host batch job. Not a web server or long-running daemon.

### 15.2 Recommended Scheduling

```bash
# Run daily at 8:00 AM
0 8 * * * cd /path/to/ESG_Newsletter_v02 && python main.py >> daily_run.log 2>&1
```

### 15.3 System Requirements

| Requirement | Minimum |
|---|---|
| Python | 3.7+ |
| OS | Linux, macOS, or Windows |
| RAM | 512 MB+ |
| Disk | 1 GB+ (for logs, attachments, database) |
| Network | Outbound HTTPS to all API endpoints and RSS feed URLs |
| Chrome | Required for browser automation fallback |

### 15.4 Installation Steps

1. Clone the repository.
2. Install Python dependencies: `pip install -r requirements.txt`
3. Install Google Chrome (for Selenium fallback).
4. Create `.env` file with required environment variables (see Section 11.1).
5. Run: `python main.py`

### 15.5 Runtime Directories (auto-created)

| Directory | Purpose |
|---|---|
| `latest_articles/` | HTML reports and main system log |
| `latest_articles/newsletter_attachments/` | Saved email attachments |
| `css/` | Generated CSS and JavaScript files |
| `cache/` | SQLite database, email history, token cache |
| `logs/` | YouTube processor logs |

---

## 16. Security Considerations

### 16.1 Credential Management

- All credentials stored in `.env` file, excluded from version control via `.gitignore`.
- API keys loaded via environment variables, never hardcoded.
- Email passwords transmitted only over SSL/TLS encrypted connections.

### 16.2 Network Security

- IMAP uses `IMAP4_SSL` (encrypted connection).
- SMTP uses `SMTP_SSL` on port 465 (encrypted connection).
- All API calls use HTTPS.

### 16.3 Input Validation

- Email addresses validated against regex pattern before use.
- RSS feed content parsed through BeautifulSoup (HTML sanitization).
- Script tags stripped from extracted content.

### 16.4 Access Control

- Email newsletters filtered through a whitelist of 150+ trusted senders.
- No inbound network services exposed (batch job only).

### 16.5 Data Handling

- Article content stored temporarily in SQLite for deduplication purposes.
- Logs may contain URLs and partial content (review retention policies).
- No user tracking, analytics, or PII collection.

---

## 17. Directory Structure

```
ESG_Newsletter_v02/
├── main.py                          # Entry point / orchestrator
├── config.py                        # Central configuration (env vars, feeds, colors, settings)
├── keywords_config.py               # Keyword definitions (positive, negative, YouTube-specific)
├── rss_processor.py                 # RSS feed aggregation module
├── email_processor.py               # IMAP email newsletter processing module
├── academic_processor.py            # Semantic Scholar API integration module
├── podcast_processor.py             # Spotify API podcast processing module
├── youtube_processor.py             # YouTube Data API v3 integration module
├── html_generator.py                # HTML report generation module
├── email_sender.py                  # SMTP email delivery module
├── mistral.py                       # Mistral AI executive summary module
├── utils.py                         # Shared utilities (text normalization, CSS/JS generation, etc.)
├── content_storage.py               # SQLite database persistence module
├── email_deduplication.py           # Email duplicate tracking module
├── cleanup_files.py                 # Log/file cleanup module
├── browser_setup.py                 # Selenium Chrome WebDriver configuration
├── youtube_logs.py                  # YouTube processor logging utilities
├── system_tester.py                 # Dependency and compatibility testing
├── requirements.txt                 # Python package dependencies
├── .env                             # Environment variables (not in version control)
├── .gitignore                       # Git ignore rules
│
├── latest_articles/                 # [auto-created] Output directory
│   ├── *.html                       # Generated HTML newsletter reports
│   ├── newsletter_system.log        # Main system log
│   └── newsletter_attachments/      # [auto-created] Saved email attachments
│       └── *.eml
│
├── css/                             # [auto-created] Generated stylesheets
│   ├── newsletter_styles.css
│   └── newsletter_scripts.js
│
├── cache/                           # [auto-created] Persistent data
│   ├── content_database.db          # SQLite deduplication database
│   ├── email_history.json           # Email deduplication tracking
│   └── spotify_token.json           # Cached Spotify OAuth token
│
└── logs/                            # [auto-created] YouTube processor logs
    ├── youtube_api.log
    ├── youtube_errors.log
    └── youtube_debug.log
```

---

## Appendix A: RSS Feed Source Categories

The system monitors 700+ RSS feeds spanning these categories:

| Category | Example Sources |
|---|---|
| **Academic & Research** | Nature, Science, MIT Press, Oxford University Press, IOP Science, Copernicus Publications |
| **Central Banks & Regulators** | ECB, Federal Reserve, BaFin, BIS, ESRB, DNB, Central Bank of Ireland, Bank of Greece |
| **EU Institutions** | European Parliament, EBA, EIOPA |
| **Financial Institutions** | JP Morgan, Morgan Stanley, UBS, Deutsche Bank Research, KfW, BBVA, ING |
| **News & Media (English)** | The Guardian, Reuters, Bloomberg, Financial Times, Live Science |
| **News & Media (German)** | Tagesschau, FAZ, Sueddeutsche Zeitung, Spiegel, Presseportal |
| **Climate & Environment** | NASA Climate, UNDRR, Greenpeace, Resilience.org, NOAA |
| **Think Tanks & NGOs** | HEC, UNU, SOAS, Strathclyde University |
| **International Organizations** | UN News, UNEP |
| **Substacks & Blogs** | Various ESG-focused newsletters (Carbon Risk, French Dispatch, etc.) |
| **Podcasts (RSS)** | Various finance and ESG podcast feeds |
| **Social Media (Bluesky)** | Select Bluesky RSS feeds for ESG thought leaders |

---

## Appendix B: Trusted Email Sender Categories

The email processor filters incoming emails against a whitelist of 150+ trusted senders from:

| Category | Examples |
|---|---|
| **Financial Institutions** | JP Morgan, Goldman Sachs, Deutsche Bank, UBS |
| **Central Banks** | ECB, Bundesbank, Federal Reserve |
| **Academic Institutions** | Harvard, Oxford, LSE, Cambridge |
| **Think Tanks** | Bruegel, CEPS, Chatham House |
| **Regulatory Bodies** | BaFin, EBA, ESMA |
| **NGOs & Nonprofits** | WWF, Greenpeace, Climate Policy Initiative |
| **News Organizations** | Reuters, Bloomberg, Financial Times |
| **Industry Groups** | GFANZ, NGFS, TCFD |

---

*End of PRD*

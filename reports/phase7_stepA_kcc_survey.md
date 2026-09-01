# Phase 7 Step A — KCC acquisition survey

Verifier (Phase 6) is complete: 740 label_db rows, 616 gradeable trainable.
This phase pairs real farmer queries (KCC) with label_db answers for SFT.
This step surveys whether KCC data is actually gettable before any download
code is written. **No data was downloaded.** All findings below are from
web search and direct HTTP probes on 2026-09-01; nothing here has been
verified against the actual dataset contents.

## 1. What exists on data.gov.in

Two resources, both under the "Kisan Call Centre" dataset group:

- **[Kisan Call Centre (KCC) - Transcripts of farmers queries answers](https://www.data.gov.in/resource/kisan-call-centre-kcc-transcripts-farmers-queries-answers)**
  — the transcript-level resource (query text + answer text), described as
  "district wise - month wise details of queries asked by farmers and
  answers given by Farm Tele Advisors (FTAs)."
- **[District wise and month wise queries of farmers in KCC](https://www.data.gov.in/catalog/district-wise-and-month-wise-queries-farmers-kisan-call-centre-kcc)**
  — likely an aggregated count table, not transcript-level. Returned an
  Akamai edge error (HTTP 504) when probed; not confirmed.

**Both pages are React/Angular single-page apps.** A plain HTTP GET (curl,
WebFetch) returns an empty shell — no dataset content, no field list, no
resource ID — because the page hydrates via client-side JS calling internal
APIs after load. This means the content **cannot be scraped with a simple
fetch**; either a JS-rendering client or the actual OGD API is required.

**Fields** (assembled from the KisanQRS paper's dataset description, since
the portal itself wouldn't render): season, crop category, query type, crop,
question text, answer text, state name, district name, block name, date/time
of query. This matches what we need — crop, query, answer, state, date all
present.

**Access**: data.gov.in exposes a real REST API at `api.data.gov.in/resource/
{resource_id}`, gated by a free API key (self-service registration on the
portal, no approval wait reported anywhere). **The resource_id for the KCC
transcript resource was not found** during this survey — the portal's own
search API isn't public (confirmed by the `datagovindia` package's README,
which says it has to scrape+cache metadata locally because "the OGD
platform's lack of a search API for resources"). Getting the resource_id
requires either the `datagovindia` package's `sync_metadata()` step, or
manually opening the resource page in a real browser and reading the "API"
tab.

**Granularity**: records are logged "for each district per month," so a
single 4-year, 5-state pull is not one API call — it's paginated across many
district-months. No rate limit was documented anywhere; data.gov.in API keys
are commonly reported (outside this survey, from general knowledge of the
platform) to cap at ~10k records per single call and require offset paging on
top of that.

## 2. AIKosh (aikosh.indiaai.gov.in)

Two listings exist in AIKosh's own site index:
- `kisan_call_center_query_dataset.html`
- `kisan_call_centre_kcc_transcripts_of_farmers_queries_and_answers.html`

**Both returned "Oops... The requested resource is unavailable"** when
fetched directly (confirmed twice, distinct URLs). AIKosh is also a SPA, so
this could mean either (a) the listing is genuinely broken/delisted, or (b)
the page requires client-side routing that a direct URL fetch doesn't
trigger correctly. Not resolved — **needs a manual browser check**, this
survey could not distinguish the two causes.

## 3. Preprocessed / mirrored versions found

| Source | Rows | Columns | Fits our filter? |
|---|---|---|---|
| [Kaggle: daskoushik/farmers-call-query-data-qa](https://www.kaggle.com/datasets/daskoushik/farmers-call-query-data-qa) | unknown — page wouldn't render for this tool | unknown | Unverified, described as "QA dataset generated from data.gov.in" |
| [HuggingFace: hisham1404/kcc_call_center_query_embedded](https://huggingface.co/datasets/hisham1404/kcc_call_center_query_embedded) | 139,542 | **only `questions` + `answers`** (no state/crop/date columns) | **No** — no join key for state or crop filtering. Only usable as a generic style/answer reference, not for our Maharashtra+8-crop cut. |
| [GitHub: batul02/KCC_Data_Analysis](https://github.com/batul02/KCC_Data_Analysis) | unstated | unstated | Points to `kcc-chakshu.icar.gov.in/insights.html` as source, mentions a 6.7GB CSV — this is the ICAR portal, see §5 below |
| [GitHub: digitalagadvisory/india_kisan_call_center](https://github.com/digitalagadvisory/india_kisan_call_center) | "30M+" | unstated | Points to `dackkms.gov.in` (the actual backend system KCC data is drawn from) as source; 2004-2022, 32 states, 670 districts, 6,300 blocks; reports Agriculture 75% / Horticulture 22% / Livestock 1% / Fisheries <1% sector split. No download URL or resource ID given in the README. |

**None of the preprocessed mirrors are directly usable as-is.** The
HuggingFace one is the only one confirmed to have real content, and it
stripped exactly the columns (state, crop, date) we need for filtering.

## 4. GODL-India attribution requirements

Confirmed from the Wikipedia GODL-India template documentation (data.gov.in's
own GODL page is also an unrenderable SPA):

- Must **explicitly publish an "Attribution Statement"** naming the data
  provider (the Ministry/Department that owns the dataset — here, presumably
  the Department of Agriculture & Farmers Welfare), the source, and the
  license, **plus the dataset's DOI, URL, or URI**.
- If multiple data sources are combined and per-source attribution isn't
  practical, a single linked page listing all attribution statements is
  permitted — relevant to us since KCC will sit alongside CIB&RC-sourced
  label_db.
- License explicitly **excludes**: personal information, non-shareable/
  sensitive data, official symbols/logos/crests, patented/trademarked
  material, and anything excluded under India's RTI Act.

**Flag, not just for licensing**: KCC records are FTA-transcribed phone
calls. The "excludes personal information" clause plus basic data hygiene
means **any farmer name or phone number that leaked into a query/answer
transcript must be scrubbed before this goes into a training set** — this
needs to be checked once real rows are in hand, it's not something the
license text alone resolves.

## 5. Row-count estimate for MH + 4 neighbours, 4yr, 8 crops, plant protection

Anchor numbers found (nationwide, all states, all categories):
- Full KCC history: **~30-34 million** records, 2004/2006–present (two
  independent sources: KisanQRS paper, digitalagadvisory README).
- 2015–2020 subset: **10,981,793** queries, 31 states, 553 districts (~2.2M/yr
  nationwide, all categories).
- Single-state annual volumes reported in academic studies: Rajasthan ~4M
  over 2009–2023 (~285k/yr), Uttar Pradesh 3.6M over 2017–2021 (~900k/yr).
  Both are large agricultural states, roughly comparable in scale to
  Maharashtra/MP/Gujarat.
- Category share: a Gujarat-focused study reports **weather is the #1 query
  category and plant protection is #2** — but exact percentages weren't
  found, and it's unclear whether "weather" queries are FTA-answered
  transcripts (in scope for us) or automated push alerts (would inflate the
  denominator without being relevant).

Rough chain: 5 states × 4 years × ~300-600k/yr/state (all categories) ≈
6–12M rows in scope of geography+time → apply plant-protection category
share (unconfirmed, guessing 10–20% based on the "#2 category" signal) →
**~600k–2.4M** → apply the 8-crop filter (cotton/soybean/tur/gram common
across all 5 states; onion mostly MH+Karnataka; grape/pomegranate are
Maharashtra-concentrated with little presence in the other 4 — call it
15–25% of plant-protection rows) → **raw row estimate: ~100,000–400,000.**

That is **well above** the 20-60k figure in the original roadmap.

But raw row count is not the number that matters. KCC is known (from every
analysis project surfaced in this survey) to be noisy: heavy duplication of
canned FTA answers, one-line non-answers ("contact your nearest KVK"),
transcription garble, and answers that don't carry a specific chemical name
+ dose the way label_db does. Historically-reported quality-filter survival
rates in similar public-sector call-center corpora are commonly in the
5–20% range. Applying that to the 100k–400k raw estimate lands back around
**~15,000–60,000 usable rows** — which is, reassuringly, close to the
original roadmap number. **The original estimate was likely reasoning about
the wrong stage** (usable rows, arrived at intuitively) rather than being
wrong about raw availability. This needs an actual pull to confirm either
number; treat both as unverified until real rows are in hand.

## 6. Alternatives, if KCC turns out inaccessible or the plant-protection
   slice is too thin after real filtering

- **dackkms.gov.in** — the backend system KCC data is actually drawn from
  (per digitalagadvisory's README). Might expose more granular or more
  current data than the data.gov.in mirror, but public bulk-access is
  unconfirmed — worth a manual check before assuming it's usable.
- **KCC-CHAKSHU 2.0** (`kcc-chakshu.icar-web.com`) — ICAR's own analytics
  portal built specifically on this data, covering January 2006–present,
  with state/crop/date filtering and a "download selective datasets"
  feature per its own description. **This session could not connect to it**
  — both curl and WebFetch failed at the TLS handshake stage (schannel
  `SEC_E_INTERNAL_ERROR`, then `TLSV1_ALERT_INTERNAL_ERROR` on retry). This
  looks like it could be a transient local/network issue rather than the
  site being down, since two different HTTP clients failed at different TLS
  stages — **needs a manual browser check**, not ruled out.
- **"What a million Indian farmers say"** (arXiv 2108.03374) — a
  crowdsourcing-based pest-surveillance paper built on KCC data; may have
  released a cleaner structured subset. Not checked in depth this pass.
- **mKisan SMS logs** — these are advisory pushes *to* farmers, not queries
  *from* them; wrong direction for our purpose (we need the farmer's natural
  question, not the department's broadcast). Deprioritize.
- **State agriculture department / KVK helpline archives** — plausible in
  principle, no evidence found of any being publicly downloadable in bulk
  the way KCC is. Would need direct outreach, not a data portal.

## 7. Proposed acquisition plan (not yet executed)

1. Register a free API key on data.gov.in.
2. Install `datagovindia` (PyPI), run `sync_metadata()`, then
   `search("kisan call centre")` to recover the actual `resource_id`(s) for
   both KCC resources — confirm which one is transcript-level vs. aggregated
   counts before writing any pull logic.
3. In parallel, manually open `kcc-chakshu.icar-web.com` in a real browser
   (this session's HTTP clients couldn't reach it) and check whether its
   "download selective datasets" feature can produce a pre-filtered
   state+crop+date extract directly — if so, this may be a cleaner path than
   paginating the raw API.
4. Manually re-check both AIKosh listing URLs in a browser to confirm
   whether they're genuinely dead or just failed this tool's fetch.
5. Pull a **small sanity sample first** (e.g. one state, one recent month)
   via the API before committing to a full 5-state/4-year pull — confirms
   field names, confirms whether "plant protection" is a literal Category
   value we can filter on server-side, and gives a real per-district-month
   row count to extrapolate from instead of the guesswork in §5.
6. Once the real category taxonomy is known, filter: state ∈ {Maharashtra,
   Karnataka, Telangana, Gujarat, Madhya Pradesh}, date ≥ (today − 4y),
   category = plant protection (exact label TBD), crop ∈ the 8 slugs from
   `src/scope.py`.
7. Dedup near-identical FTA boilerplate answers before counting anything as
   "usable" — raw row count from step 6 is not the number to report back.
8. Scrub any leaked PII (farmer name/phone) from surviving rows.
9. Write the GODL-India attribution block (provider, source, dataset URL,
   license reference per §4) into `SOURCES.md` alongside the existing
   CIB&RC entries, before any KCC-derived row ships anywhere.

Stopping here per instructions — nothing downloaded, no acquisition code
written. Waiting on review before proceeding to Phase 7 Step B.

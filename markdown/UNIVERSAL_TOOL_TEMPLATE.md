# Toolpika — Universal Tool Template (canonical spec)

> **Status:** reconstructed from the platform brief. This file is the single
> source of truth for every generated tool page. `backend/app/templates/tool_template.py`
> parses it; `backend/app/qa/validator.py` enforces it. If you have the original
> template, replace this file — the field names and rules below are the contract.

---

## 1. Identity fields

| Field | Rule |
| :--- | :--- |
| `slug` | lowercase kebab-case, unique |
| `category` | one of `text, image, file, code, converter, calculator, security` |
| `tier` | `1` (full SEO content) or `2` (lite) |
| `indexable` | boolean |
| `name` | full tool name |
| `shortName` | ≤ 18 characters |
| `componentId` | React component id used by the frontend registry |

## 2. Search / SEO fields

| Field | Rule |
| :--- | :--- |
| `primaryKeyword` | one phrase |
| `secondaryKeywords` | 2–5 phrases |
| `searchIntent` | short description of intent |
| `peopleAlsoAsk` | 3–6 real questions |
| `seo.title` | **50–60 characters** |
| `seo.description` | **120–155 characters** |

## 3. Visible content fields

| Field | Rule |
| :--- | :--- |
| `h1` | **max 6 words**, contains `primaryKeyword` |
| `directAnswer` | **exactly 40–43 words** |
| `howToUse` | 3–6 steps, each a plain sentence |
| `example` | 1–3 objects with `input` and `output`, must be real and correct |
| `features` | 3–7 short feature strings |
| `about.whatIs` | Tier 1: **≥ 200 words** |
| `about.useCases` | Tier 1: **≥ 3** entries |
| `about.commonMistakes` | Tier 1: **≥ 2** entries |
| `about.limits` | honest limitations, ≥ 1 entry |
| `faqs` | 4–8 items; **≥ 75% of questions unique** across all tools; at most one generic privacy FAQ |
| `relatedTools` | 3–6 slugs that exist in the registry |
| `trust.author` | author name |
| `trust.lastUpdated` | ISO date |

## 4. Schema toggles

`schema.softwareApplication`, `schema.faqPage`, `schema.howTo`, `schema.breadcrumb` — booleans.

## 5. Translation rules

- Translate every visible string and SEO field; never translate code, inline
  `` `code` ``, URLs, slugs, component ids or terms in the KEEP glossary.
- Keep SEO title ≤ 60 chars and description ≤ 155 chars **after** translation.
- Output valid JSON with the same keys as the source chunk.

---

## 6. Banned strings (hard errors, case-insensitive)

- `converters tool`
- `converters fix`
- `converters job`
- `converters action`
- `converters utility`
- `a free {category} tool that`
- `get out of the way`
- any unfilled placeholder: `{`, `}`, `undefined`, `null`, `[object Object]`

## 7. Category-name leak (hard error)

The category label (e.g. "Text", "Converter") must **not** appear inside prose
bodies: `directAnswer`, `about.*`, `faqs[*].answer`. Titles and metadata may use
it where natural.

## 8. Warnings (log, do not block)

- Reading level too complex
- `primaryKeyword` missing from H1 / SEO title / directAnswer
- More than 3 FAQs start with the same two words
- No internal link to a blog post

## 9. Pipeline contract

1. Research → 3 ranked candidates (Tavily).
2. Generate ToolSpec (Nemotron), strict JSON only.
3. Validate; on failure send errors back for fix, **max 3 attempts**.
4. Publish `status: published`, `source_hash: sha256(json)` (idempotent by slug).
5. Schedule chunked translation at T+5 minutes.
6. Translation chunks: `seo`, `core`, `deep`, `faqs`; per-locale, per-chunk rows in
   `content_translations` keyed by `(locale, slug, chunk)`.

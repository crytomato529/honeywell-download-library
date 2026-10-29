# Honeywell Download Library

[简体中文](README.md) | **English**

Public industrial-manual collection tools and a portable AI skill for Honeywell. Works with Codex, Claude Code, other Python-capable agents, or directly from a terminal. No simulated browser clicks.

## Improvements

Examples separate classic Safety Manager from Safety Manager SC and cover hardware references, safety manuals, installation, technical specifications and change notices. Validation extracted 28 public links across both product pages; these include marketing/training material, not 28 manuals. The SC page explicitly offers more documents after sign-in.

- Combine product aliases, manual categories, exact document numbers and public pages; PDF citations produce follow-up search plans.
- Maintain accumulated JSON/CSV catalogs, resume pending downloads and preserve historical records.
- Compare identity-confirmed document revisions across URLs; distinguish pending newer editions from applicability review.
- Validate file signatures and SHA-256; atomically save state and reject empty files, login pages and fake PDFs.
- Export traceable local RAG indexes with a separate version-review set.

**This is not exhaustive enumeration of all manufacturer documents or the entire web.** Search engines are bounded; gated documents, unavailable links and access denials stay visible and are not bypassed.

## Quick Start

Python 3.10+. Collection/downloads use the standard library. Optional PDF inspection dependency:

```bash
python -m pip install -r requirements-inspection.txt
```

Give the complete repository folder to a skill-capable agent to read `SKILL.md`, or run the commands below. Keep output outside the skill installation. Copy and adapt the example config for your products, retaining stable product IDs and output roots.

```bash
python scripts/manual_watch.py plan --config references/honeywell.example.json --out web-query-plan.json
python scripts/manual_watch.py run --config references/honeywell.example.json --root honeywell-manuals --web-results web-results.json
python scripts/manual_watch.py resume --config references/honeywell.example.json --root honeywell-manuals
python scripts/manual_watch.py audit --config references/honeywell.example.json --root honeywell-manuals
```

The example plan currently contains 19 queries. Execute them with any search tool, then export `web-results.json` using the [import schema](references/manual-watch.md) and actual search timestamps. Do not relabel old results as fresh. A normal first run omits `--limit` and downloads all accessible candidates in the selected scope. Use `--limit 2` only for testing.

For standalone search, set `TAVILY_API_KEY` in the process environment and replace `--web-results web-results.json` with `--web-provider tavily`. This provider may charge per query; preview the plan first. Never put keys in files or the repository. Without fresh searches, only public-page or saved-catalog coverage can be claimed.

Later `run` operations refresh discovery and download missing files. `resume` uses saved catalogs without searching; `audit` rebuilds comparisons entirely offline. Add `--revalidate` to detect silent replacements at the same URL. Resume is file-level: an interrupted file restarts, without byte-range continuation.

## Outputs And Versions

Naming: `Document type - Document number - Document title - Version.pdf`. Missing fields are omitted; multi-file records and name collisions get suffixes. Unknown metadata is never invented.

| File | Purpose |
| --- | --- |
| `catalog.json / catalog.csv` | Accumulated items, including undownloaded/non-manual records |
| `download-manifest.json` | Candidates filtered by format and document class |
| `version-report.json` | Cross-URL families, pending revisions, unidentified records |
| `followup-plan.json` | PDF-derived document queries and official links; review relevance first |
| `pdf-evidence.json` | Front matter, physical page numbers, references and extraction errors |
| `rag-index.jsonl` | Valid local files and preserved history |
| `rag-current.jsonl / rag-review.jsonl` | Known-conflict-filtered corpus / revision-review records |

Recognized marketing/training material stays catalogued but is excluded from the examples' download scope. Unclassified PDFs remain candidates to reduce omissions. Inspection defaults to 40 pages and caches by hash. Image-only PDFs may need separate OCR. See [version-aware collection](references/version-aware-collection.md).

A higher revision does not establish applicability. Future RAG-assisted design reviews must consider actual hardware, firmware, software releases and certification requirements with an engineer. This tool does not approve revisions, deploy a vector database or replace engineering review.

## Validation And Limits

On 2026-10-30 (China time), the shared engine passed **68 offline regression tests**, including both brands' 2+2 resume, cross-URL revisions, language isolation, bad-file rejection and history preservation.

A live SC Direct Landing Adapter FC-TUDL01 technical document, version 1.0, downloaded successfully (294,817 bytes). Immediate resume downloaded zero and skipped one. No independent document number was printed on the cover, so naming omits it rather than substituting the product model.

Live acceptance used bounded downloads and imported primary-source evidence. It did not bulk-download all documents, execute every planned query, or test the standalone Tavily HTTP backend. Exit codes: `0` operation succeeded, `2` partial coverage/sources/inspection, `1` configuration/runtime error. Inspect reports; a nonzero status is not proof of no documents.

```bash
python -B -m unittest discover -s scripts -p "test_*.py"
```

Any scheduler may periodically run the same config/root. Installing the skill does not create a schedule. A root lock prevents overlapping jobs; inspect the recorded process before handling a stale lock.

## Document Rights

Not affiliated with Honeywell. Manufacturer documents remain copyrighted by their owners; comply with access terms and internal-use rules. The public repository contains code and documentation, not downloaded manuals, user state, private data or credentials.

---
name: honeywell-download-library
description: Collect public Honeywell product manuals with official-page and web-search discovery, document-number gap searches, cross-URL version comparisons and resumable downloads. Use for periodic manual updates and traceable local RAG preparation, not exhaustive enumeration of gated manufacturer libraries.
---

# Honeywell Download Library

Portable Python 3.10+ scripts for AI agents (including Codex and Claude Code) or standalone use. No browser clicks required. Keep one stable output root per brand outside the skill folder.

Read [the workflow and import schema](references/manual-watch.md) for search/export commands and [version-aware collection](references/version-aware-collection.md) for PDF evidence, version families and review boundaries.

## Workflow

1. Start from [the product config](references/honeywell.example.json). Preview `plan`; the example generates 19 queries. Adapt product aliases, manual topics, document numbers and language scope to the user.
2. Run planned queries with an available search tool and export actual query timestamps/results. Or use the optional Tavily backend with a process-environment API key. Never fabricate execution records.
3. Run collection with fresh exported results. Normal first collection has no download limit; `--limit` is for testing only.
4. After interruption, use `resume` with the same root/config. It only uses the saved catalog and never searches. For new documents use `run`; add `--revalidate` to detect silent same-URL replacements.
5. Review `followup-plan.json` for referenced document numbers and official links. Execute only relevant leads and import their results; do not recursively crawl everything.

```bash
python scripts/manual_watch.py plan --config references/honeywell.example.json --out web-query-plan.json
python scripts/manual_watch.py run --config references/honeywell.example.json --root honeywell-manuals --web-results web-results.json
python scripts/manual_watch.py resume --config references/honeywell.example.json --root honeywell-manuals
python scripts/manual_watch.py audit --config references/honeywell.example.json --root honeywell-manuals
```

## Invariants

- This brand uses public searches and bounded public pages, not a complete official-library API. Query completion is not entire-web completeness.
- The examples retain marketing/training entries in the catalog but exclude recognized ones from download. Classification is heuristic; unclassified PDFs remain eligible.
- PDF inspection uses optional `pypdf` or PyMuPDF, is cached by file hash and inspects the first 40 pages by default. Scanned PDFs may need separate OCR.
- `version-report.json` compares identity-confirmed document families across URLs and languages separately. A higher observed revision is not proof of newest applicability.
- `rag-current.jsonl` excludes pending catalog revisions and version families needing review; `rag-review.jsonl` retains conflicts. All original files remain preserved. Engineer-reviewed hardware/software applicability is required before design review with RAG.
- Unknown document number/version stays blank. Never turn a model number into a document number or a search snippet into verified metadata.
- Report missing/denied/authenticated sources honestly. Never bypass login, agreements or access challenges. Empty responses, HTML and invalid file signatures cannot complete.
- No schedule or publication is created unless the user requests it. Do not publish downloaded manuals, private state, credentials or local evidence.

Run `python -B -m unittest discover -s scripts -p "test_*.py"` after changes.

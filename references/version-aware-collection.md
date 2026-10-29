# Version-Aware Collection / 版本与查缺

## Coverage Strategy

Use product aliases, manual categories, official/global PDF searches, exact document numbers, and PDF document-guide references together. No single search engine or public product page proves completeness. `manual_topics` generates exact-topic official searches for each keyword. Preview the query plan before using a metered search service: the current Honeywell example generates 19 queries and the Siemens example 24.

Honeywell examples keep Safety Manager and Safety Manager SC in separate products. Classic Safety Manager excludes explicit SC titles/URLs. Official product-page documents are deduplicated; a sign-in notice is reported even when public PDFs are accessible. 28 public links across the two example pages were observed in the 2026-10-30 China-time validation, but these include brochures, product notes and training material, not 28 manuals. This count is a snapshot, not a promise.

Siemens searches cover system/equipment/function/programming manuals, safety and Product Information. Product Information may amend a base manual; do not discard it just because it is short. The S7-1500 documentation guides cite manual-collection and function-manual support pages. These pages may require JavaScript or reject requests; they remain leads, not automatically successful enumerations. Use only observed URLs, never guessed attachment IDs.

## Config Fields

- `manual_topics`: additional exact-topic queries per keyword.
- `document_numbers`: exact document-number queries. For Siemens use the A5E base number to discover changed revision suffixes.
- `exclude_keywords`: explicit out-of-scope phrases in title/URL. Use carefully; exclusions can hide relevant results.
- `download_classes`: any of `technical`, `marketing`, `training`, `unclassified`. Default without this field includes all four. Classification is a title/URL heuristic, not PDF content verification. Excluded classes remain in the catalog.
- Imported metadata may include `document_language` and `product_release`. Set `verified: true` only after inspecting the PDF or authoritative document details, not an ordinary search snippet.

When reusing an old combined Safety Manager output, its accumulated records remain preserved. New `exclude_keywords` does not delete old entries. Use a new product ID/root for a clean classic/SC split or review the existing catalog explicitly. `resume` uses the saved scope; use `run` to apply config updates.

## Offline Audit

Install optional inspection support with `python -m pip install pypdf`. PyMuPDF is also supported. Collection/downloads otherwise use the standard library. `run` and `resume` automatically audit Honeywell/Siemens local files; an optional-parser failure appears in the audit summary and does not mark a valid download failed. Run `audit` to retry inspection after installing the parser:

```bash
python scripts/manual_watch.py audit --brand siemens --config references/siemens.example.json --root siemens-manuals
```

An audit does not call search engines or download URLs. It checks local hashes, inspects up to the first 40 pages, and caches successful PDF extraction by hash/brand/page budget. `pdf-evidence.json` retains front-matter text, physical page numbers, references, annotation links and errors. Scanned/image-only documents require separate OCR; no OCR is silently assumed. To inspect all pages of an individual manual:

```bash
python scripts/manual_references.py --brand siemens --pdf path/to/manual.pdf --max-pages 0 --out references.json
```

`followup-plan.json` contains exact-number queries and official PDF/support-page links with source-page evidence. Review relevance, then execute selected queries with your search tool and import the results through `--web-results`. Add durable gaps to `document_numbers`/`extra_queries` in the config for future runs. The plan is not an auto-crawl queue; it never triggers recursive or paid requests by itself. References can cite other products or the same document.

## Cross-URL Comparison

`version-report.json` groups identity-confirmed records by document number and language, regardless of URL. For Siemens, `A5E50811213-AC` and `A5E50811213-AF` share base `A5E50811213`; revision letters remain separate. Honeywell EP-SM/EP-SC document numbers retain the series and numeric issue. Unknown or ambiguous identity goes to `unidentified`, not a guessed family. Unknown languages are flagged and not merged with known languages. Identical version labels with conflicting PDF metadata also require review.

The report includes `highest_observed_revision`, `newer_candidate_pending`, release contexts and download status. Numeric issues compare numerically, not lexically. Unknown version schemes are not ordered. Revision ordering does not establish project applicability, newest global edition, certification status or manufacturer support. Different product/software releases require an engineer to decide applicability.

All downloaded versions remain preserved. `rag-index.jsonl` includes current local files and history. `rag-current.jsonl` excludes catalog revisions not yet downloaded, historical/hash-duplicate rows, and version families requiring review. `rag-review.jsonl` holds those version conflicts for deliberate selection in the consuming knowledge base. There is no automatic approval command and no claim that the filtered set is the latest applicable corpus. Never use an AI/RAG result as the sole safety-system design approval.

## Acceptance Evidence

On 2026-10-30 China time, the shared engine passed 68 offline regression tests. Live bounded tests downloaded one Honeywell SC Technical Information PDF (version 1.0, 294,817 bytes) and two Siemens manuals (A5E50811213-AC and A5E03484625-AK). Immediate resume downloaded zero files and skipped 1/2 respectively. The two Siemens PDFs produced 36 unique official reference links from their first 40 pages.

A newer A5E50811213-AF was confirmed in the official search-indexed PDF front matter. Its known cache URL returned 404 through the research fetcher and the support attachment returned HTTP 403 from the downloader. The newer candidate is therefore pending, not downloaded. The AC family is excluded from automatic current RAG ingestion once that pending revision is catalogued. No login, WAF, or agreement was bypassed.

These live tests used imported primary-source results, not the standalone Tavily HTTP backend. They did not execute every generated query or bulk-download the entire catalog. Raw manuals, local state, private data and API keys are excluded from public packages.

## 中文摘要

先把产品别名、手册类别、官网入口和文档号组合起来检索，再从已下载 PDF 的文档指南反查引用。霍尼韦尔经典 Safety Manager 与 SC 分开，宣传册和培训资料单独分类；西门子用 A5E 基础文档号串联换过网址的各个修订版。首次不设限量，后续 `run` 更新清单并下载缺项；中断后用 `resume`，不会重搜。单个中断文件会重新下载，不是字节级 Range 续传。

版本不同、软件发行版不同、元数据矛盾时，系统只标记待审核，不擅自宣布新版可替代旧版。AI 知识库应根据实际硬件、固件、工程版本及安全认证要求选择资料，并保留原始来源、物理页码和文件哈希供方案审核溯源。公开搜索覆盖、登录受限、404/403 和缺少 OCR 都应如实记录。

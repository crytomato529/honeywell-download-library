"""Offline, hash-cached PDF evidence and conservative cross-URL version comparisons."""

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, unquote

from library_common import atomic_json, allowed_url, valid_record
from manual_references import inspect_pdf
from source_discovery import pdf_link, detail_link


def classify(title):
    value = str(title).casefold().replace("_", " ")
    for label, pattern in (
        ("training", r"\b(course|training|curriculum)\b"),
        ("marketing", r"\b(brochure|case study|success story|product information note|pin)\b"),
        ("technical", r"\b(manual|guide|reference|specification|instructions|datasheet|data sheet|system hints|change notice|release note)\b|手册|指南|规格|说明书"),
    ):
        if re.search(pattern, value):
            return label
    return "unclassified"


def identity(number, version, brand):
    number = re.sub(r"\s+", "", str(number or "")).upper()
    version = str(version or "").strip()
    if brand == "siemens":
        match = re.fullmatch(r"(A5E\d{8})-([A-Z]{2})", number)
        if match:
            number, revision = match.groups()
            version = version or revision
    return number, version


def language(value, url=""):
    if value:
        return str(value).strip().lower().replace("_", "-")
    match = re.search(r"(?:_|-)(en-us|en-gb|zh-cn|zh-tw|de-de|fr-fr)(?:_|-|\.)", unquote(urlsplit(url).path), re.I)
    return match[1].lower() if match else "unknown"


def revision_order(value, brand):
    value = str(value).strip()
    if brand == "siemens" and re.fullmatch(r"[A-Z]{2}", value):
        return tuple(ord(char) - 65 for char in value)
    match = re.fullmatch(r"(?:Issue\s*|v)?(\d+(?:\.\d+)*)", value, re.I)
    return tuple(int(part) for part in match[1].split(".")) if match else None


def compare_versions(entries, brand):
    groups, unidentified = {}, []
    for row in entries:
        number, version = identity(row.get("document_number"), row.get("version"), brand)
        if not number or not row.get("identity_verified"):
            unidentified.append(row)
            continue
        lang = language(row.get("language"), row.get("url", ""))
        key = number + "|" + lang
        groups.setdefault(key, {"family": key, "document_number": number, "language": lang, "entries": []})["entries"].append({**row, "version": version})
    for group in groups.values():
        rows = group["entries"]
        versions = sorted({row["version"] for row in rows if row["version"]})
        releases = sorted({release for row in rows for release in row.get("product_releases", [])})
        ordered = {version: revision_order(version, brand) for version in versions}
        comparable = bool(versions) and all(value is not None for value in ordered.values())
        highest = max(versions, key=ordered.get) if comparable else None
        known = [row for row in rows if row.get("downloaded") and row.get("local_status") != "historical"]
        local_versions = {row["version"] for row in known}
        newer = bool(highest and highest not in local_versions and local_versions and
                     all(revision_order(v, brand) is not None and revision_order(v, brand) < ordered[highest] for v in local_versions))
        mixed_unknown = bool(versions) and any(not row["version"] for row in rows)
        review = len(versions) > 1 or len(releases) > 1 or mixed_unknown or any(row.get("metadata_conflict") for row in rows)
        group.update(versions=versions, product_releases=releases, highest_observed_revision=highest,
                     newer_candidate_pending=newer, review_required=review,
                     status="review_required" if review else "single_observed_revision",
                     incomplete_revision_metadata=mixed_unknown,
                     applicability="not_established", unknown_language=group["language"] == "unknown")
    return {"families": list(groups.values()), "unidentified": unidentified,
            "note": "Highest observed revision is not proof of latest/applicable edition. Languages stay separate; multiple product releases require review. No files are deleted or superseded automatically."}


def audit(directory, catalog, brand, domains, max_pages=40):
    directory = Path(directory)
    state_path = directory / "downloads" / f".{brand}_download_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    cache_path = directory / "pdf-audit-cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    entries, inspected, errors, followups, link_leads = [], [], [], {}, {}
    local_urls = set()
    for record, status in [(row, "current") for row in state.get("files", {}).values()] + [(row, "historical") for row in state.get("history", [])]:
        if not valid_record(record, record.get("url", "")):
            continue
        local_urls.add(record["url"])
        path = Path(record["path"])
        cache_key = f"v1:{brand}:{max_pages}:{record.get('sha256', '')}"
        result = cache.get(cache_key)
        if result is None:
            try:
                result = inspect_pdf(path, brand, max_pages=max_pages)
                # Errors can be retried after installing a parser or correcting a file.
                if not result["errors"] and result["text_pages"]:
                    cache[cache_key] = result
            except Exception as exc:
                result = {"metadata": {}, "references": [], "links": [], "errors": [{"error": str(exc)}]}
        inspected.append({**result, "path": str(path), "source_pdf": str(path), "sha256": record.get("sha256")})
        errors.extend({"path": str(path), **error} for error in result["errors"])
        metadata = result["metadata"]
        actual = metadata.get("status") == "extracted"
        declared_number, declared_version = identity(record.get("reference"), record.get("version"), brand)
        number = metadata.get("document_number") or declared_number
        version = metadata.get("version") or declared_version
        conflict = actual and bool((declared_number and declared_number != number) or
                                   (declared_version and metadata.get("version") and declared_version != version))
        entries.append({"url": record["url"], "path": str(path), "sha256": record.get("sha256"),
                        "document_number": number, "version": version,
                        "language": language(record.get("language"), record["url"]),
                        "product_releases": metadata.get("product_releases", []) or ([record["product_release"]] if record.get("product_release") else []),
                        "identity_verified": actual or bool(record.get("metadata_verified")),
                        "identity_source": "pdf_front_matter" if actual else "imported_metadata",
                        "metadata_conflict": conflict, "downloaded": True, "local_status": status})
        for ref in result["references"]:
            base, _ = identity(ref["document_number"], "", brand)
            query = '"' + base + '" (' + " OR ".join("site:" + domain for domain in domains) + ")"
            lead = followups.setdefault(query, {"product": directory.name, "query": query, "document_number": base, "evidence": []})
            lead["evidence"].append({"source_pdf": str(path), "pages": ref["pages"]})
        for link in result.get("links", []):
            url = link["url"]
            if allowed_url(url, domains) and (pdf_link(url) or detail_link(url)):
                lead = link_leads.setdefault(url, {"url": url, "evidence": [], "status": "unverified_reference_link"})
                lead["evidence"].append({"source_pdf": str(path), "pages": link["pages"]})
    for item in catalog.get("items", []):
        for file in item.get("files", []):
            url = file["download_url"]
            # A newer catalog revision at the same URL remains a separate candidate.
            number, version = identity(item.get("reference"), item.get("version"), brand)
            same = any(row["url"] == url and row["document_number"] == number and row["version"] == version for row in entries)
            if same:
                continue
            entries.append({"url": url, "document_number": number, "version": version,
                "language": language(item.get("document_language"), url),
                "product_releases": [item["product_release"]] if item.get("product_release") else [],
                "identity_verified": bool(item.get("metadata_verified")), "downloaded": False,
                "catalog_key": item["key"], "url_has_local_copy": url in local_urls})
    report = compare_versions(entries, brand)
    report.update(pdf_count=len(inspected), errors=errors,
                  document_classes=dict(Counter(item.get("document_class", "unclassified") for item in catalog.get("items", []))))
    atomic_json(cache_path, cache)
    atomic_json(directory / "version-report.json", report)
    atomic_json(directory / "pdf-evidence.json", {"files": inspected})
    known = {identity(item.get("reference"), "", brand)[0] for item in catalog.get("items", []) if item.get("metadata_verified")}
    atomic_json(directory / "followup-plan.json", {"queries": [{**row, "catalog_status": "catalogued" if row["document_number"] in known else "not_in_catalog"} for row in followups.values()],
                "links": list(link_leads.values()), "automatic_requests": 0,
                "note": "Review relevance before searching/following. References can include unrelated products; page limits and search engine limits still apply."})
    rag_path = directory / "rag-index.jsonl"
    if rag_path.exists():
        rows = [json.loads(line) for line in rag_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        review_paths = {entry.get("path") for group in report["families"] if group["review_required"] for entry in group["entries"]}
        review = [dict(row, review_reason="cross_url_version_or_metadata_conflict") for row in rows if row["path"] in review_paths]
        eligible = [row for row in rows if row["local_status"] == "current" and not row.get("duplicate_of") and row["path"] not in review_paths]
        for name, values in (("rag-current.jsonl", eligible), ("rag-review.jsonl", review)):
            temporary = directory / (name + ".tmp")
            temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in values), encoding="utf-8")
            temporary.replace(directory / name)
    return {"families": len(report["families"]), "review_required": sum(group["review_required"] for group in report["families"]),
            "newer_candidate_pending": sum(group["newer_candidate_pending"] for group in report["families"]),
            "inspected_pdfs": len(inspected), "errors": len(errors), "followup_queries": len(followups), "followup_links": len(link_leads)}

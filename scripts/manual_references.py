"""Extract document-number leads from a local PDF with page evidence; never guess versions."""

import argparse
import hashlib
import json
import re
import urllib.parse
from pathlib import Path

from library_common import atomic_json, configure_console


PATTERNS = {
    "yokogawa": r"\b(?:IM|GS|TI)\s*\d{2}[A-Z]\d{2}[A-Z]\d{2}-\d{2}[A-Z][A-Z0-9]*\b",
    "schneider": r"\b(?:EIO\d{10}|(?:QGH|NHA|HRB|S1A|S1B|NVE|NNZ)\d{5})\b",
    "honeywell": r"\bEP[-\s]?(?:SM|SC)\s*[.\-]\s*(?:MAN|DOC|SPEC)\s*[.\-]\s*\d{4,6}\b",
    "siemens": r"\bA5E\d{8}(?:-[A-Z]{2})?\b",
}


def cover_metadata(pages, brand):
    """Read identity from the cover/front matter only, never from arbitrary citations."""
    evidence = [{"page": index + 1, "text": " ".join(text.split())}
                for index, text in enumerate(pages[:3])]
    numbers = {number for page in evidence for number, _ in extract(page["text"], brand)}
    result = {"evidence": evidence, "status": "ambiguous" if len(numbers) > 1 else "not_found"}
    text = " ".join(page["text"] for page in evidence)
    if brand == "honeywell":
        issue = re.search(r"\b(?:Issue|Version)\s*:?\s*(\d+(?:\.\d+)*)\b", text, re.I)
        if issue:
            result["version"] = issue[1]
    if len(numbers) != 1:
        return result
    number = next(iter(numbers))
    version = ""
    if brand == "siemens":
        match = re.fullmatch(r"(A5E\d{8})-([A-Z]{2})", number)
        if match:
            number, version = match.groups()
    elif brand == "honeywell":
        match = re.search(r"\b(?:Issue|Version)\s*:?\s*(\d+(?:\.\d+)*)\b", text, re.I)
        if match:
            version = match[1]
    release_pattern = r"\bRelease\s+\d+(?:\.\d+)*\b" if brand == "honeywell" else r"\b(?:Version\s+\d+(?:\.\d+)+|V\d+(?:\.\d+)+)\b"
    releases = sorted(set(re.findall(release_pattern, text, re.I)))
    return {**result, "status": "extracted", "document_number": number, "version": version,
            "product_releases": releases, "method": "pdf_front_matter"}


def pdf_annotation_links(page):
    if not hasattr(page, "get"):
        return []
    links = []
    for annotation in page.get("/Annots", []):
        obj = annotation.get_object()
        action = obj.get("/A")
        if action:
            action = action.get_object() if hasattr(action, "get_object") else action
            if action.get("/URI"):
                links.append(str(action["/URI"]))
    return links


def extract(text, brand):
    normalized = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u00ad", "")
    matches = []
    for found in re.finditer(PATTERNS[brand], normalized, re.I):
        value = re.sub(r"\s+", "", found.group()).upper()
        if brand == "yokogawa":
            value = value[:2] + " " + value[2:]
        elif brand == "honeywell":
            value = re.sub(r"^EP-?", "EP-", value)
            value = re.sub(r"(SM|SC)[.-](MAN|DOC|SPEC)[.-]", r"\1.\2.", value)
        excerpt = " ".join(normalized[max(0, found.start() - 55):found.end() + 100].split())
        matches.append((value, excerpt))
    return matches


def inspect_pdf(path, brand, max_pages=40, max_references=100):
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF inspection needs optional pypdf or PyMuPDF; normal collection needs neither") from exc
        document = fitz.open(path)
        if document.needs_pass:
            document.close()
            raise ValueError("Password-protected PDF requires review")
        total = len(document)
        get_text = lambda index: document[index].get_text()
        get_links = lambda index: [link["uri"] for link in document[index].get_links() if link.get("uri")]
        close = document.close
    else:
        document = PdfReader(str(path))
        if document.is_encrypted and not document.decrypt(""):
            raise ValueError("Password-protected PDF requires review")
        total = len(document.pages)
        get_text = lambda index: document.pages[index].extract_text() or ""
        get_links = lambda index: pdf_annotation_links(document.pages[index])
        close = lambda: None
    references, errors, links, front = {}, [], {}, []
    examined = min(total, max_pages) if max_pages else total
    text_pages, overflow = 0, False
    try:
        for index in range(examined):
            try:
                text = get_text(index)
            except Exception as exc:
                errors.append({"page": index + 1, "error": str(exc)})
                continue
            text_pages += bool(text.strip())
            if index < 3:
                # Retain physical page positions even if another page failed extraction.
                while len(front) < index:
                    front.append("")
                front.append(text)
            try:
                urls = get_links(index)
            except Exception as exc:
                errors.append({"page": index + 1, "error": "Link extraction: " + str(exc)})
                urls = []
            urls += re.findall(r"https?://[^\s<>\"\)]+", text)
            for url in urls:
                url = url.rstrip(".,;")
                parts = urllib.parse.urlsplit(url)
                if parts.scheme not in ("http", "https") or not parts.hostname or parts.username:
                    continue
                if url not in links and len(links) >= 200:
                    continue
                link = links.setdefault(url, {"url": url, "pages": []})
                if index + 1 not in link["pages"]:
                    link["pages"].append(index + 1)
            for number, excerpt in extract(text, brand):
                if number not in references and len(references) >= max_references:
                    overflow = True
                    continue
                record = references.setdefault(number, {"document_number": number, "pages": [], "excerpt": excerpt,
                    "query": '"' + number + '"', "status": "unverified_search_lead"})
                if index + 1 not in record["pages"]:
                    record["pages"].append(index + 1)
    finally:
        close()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"source_pdf": str(path.resolve()), "sha256": digest.hexdigest(), "brand": brand,
            "total_pages": total, "examined_pages": examined, "text_pages": text_pages,
            "page_limit_reached": examined < total, "reference_limit_reached": overflow,
            "errors": errors, "references": list(references.values()),
            "links": list(links.values()), "metadata": cover_metadata(front, brand),
            "note": "Leads may include this document itself and unrelated references. Review before adding document_numbers; no edition or applicability inferred."}


def compare_catalog(result, catalog):
    normalize = lambda value: re.sub(r"[^A-Z0-9]", "", str(value).upper())
    known = {}
    for item in catalog.get("items", []):
        number = normalize(item.get("code") or item.get("reference") or "")
        if number:
            known.setdefault(number, []).append(item.get("key") or item.get("id"))
    for record in result["references"]:
        matches = known.get(normalize(record["document_number"]), [])
        record["catalog_keys"] = matches
        record["catalog_status"] = "catalogued" if matches else "not_in_catalog"
    result["catalog_comparison"] = {"catalog_generated_at": catalog.get("generated_at"),
        "catalogued": sum(bool(row["catalog_keys"]) for row in result["references"]),
        "not_in_catalog": sum(not row["catalog_keys"] for row in result["references"]),
        "note": "Exact document-number comparison only; language codes stay separate. Not in this catalog does not mean unavailable, missing from all libraries, or required by your project."}


def main(argv=None):
    configure_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--brand", required=True, choices=PATTERNS)
    parser.add_argument("--out", required=True)
    parser.add_argument("--catalog", help="Optional accumulated catalog or native manifest for exact-number gap comparison")
    parser.add_argument("--max-pages", type=int, default=40, help="0 scans all pages")
    parser.add_argument("--max-references", type=int, default=100)
    args = parser.parse_args(argv)
    if args.max_pages < 0 or args.max_references < 1:
        parser.error("max-pages must be nonnegative and max-references positive")
    result = inspect_pdf(Path(args.pdf), args.brand, args.max_pages, args.max_references)
    if args.catalog:
        compare_catalog(result, json.loads(Path(args.catalog).read_text(encoding="utf-8-sig")))
    atomic_json(Path(args.out), result)
    print(f"{len(result['references'])} document-number leads from {result['examined_pages']}/{result['total_pages']} pages")
    return 2 if result["errors"] or not result["text_pages"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

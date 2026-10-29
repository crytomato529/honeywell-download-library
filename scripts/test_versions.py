"""Cross-URL lineage, PDF leads, classification and both brands' resume regressions."""

import argparse
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import document_audit as audit
import manual_references as refs
import manual_watch as watch
import source_discovery as discovery
from library_common import atomic_json
import test_library as fixtures


class VersionTests(unittest.TestCase):
    def entry(self, version, url, downloaded=True, lang="en-us", release=""):
        return {"document_number": "A5E50811213-" + version, "version": "", "url": url,
                "language": lang, "downloaded": downloaded, "identity_verified": True,
                "product_releases": [release] if release else []}

    def test_changed_url_newer_pending(self):
        result = audit.compare_versions([self.entry("AC", "https://siemens.com/old.pdf"),
                                         self.entry("AF", "https://siemens.com/new.pdf", False)], "siemens")
        group = result["families"][0]
        self.assertEqual(group["versions"], ["AC", "AF"])
        self.assertEqual(group["highest_observed_revision"], "AF")
        self.assertTrue(group["newer_candidate_pending"])
        self.assertTrue(group["review_required"])
        self.assertEqual(group["applicability"], "not_established")

    def test_languages_and_document_numbers_stay_separate(self):
        other = self.entry("AF", "other.pdf")
        other["document_number"] = "A5E32565315-AS"
        result = audit.compare_versions([self.entry("AC", "en.pdf"), self.entry("AF", "de.pdf", lang="de-de"), other], "siemens")
        self.assertEqual(len(result["families"]), 3)
        self.assertFalse(any(group["review_required"] for group in result["families"]))

    def test_unverified_snippet_cannot_supersede_verified_pdf(self):
        unverified = self.entry("ZZ", "new.pdf", False)
        unverified["identity_verified"] = False
        result = audit.compare_versions([self.entry("AC", "old.pdf"), unverified], "siemens")
        self.assertEqual(len(result["unidentified"]), 1)
        self.assertEqual(result["families"][0]["highest_observed_revision"], "AC")

    def test_known_and_unknown_revisions_require_review(self):
        unknown = self.entry("AC", "unknown.pdf")
        unknown["document_number"] = "A5E50811213"
        result = audit.compare_versions([self.entry("AF", "new.pdf"), unknown], "siemens")
        self.assertTrue(result["families"][0]["incomplete_revision_metadata"])
        self.assertTrue(result["families"][0]["review_required"])

    def test_scalar_keyword_cannot_expand_into_character_queries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            atomic_json(path, {"products": [{"id": "p", "keywords": "S7-1500"}]})
            with self.assertRaisesRegex(ValueError, "keyword"):
                watch.load_config(path)

    def test_numeric_versions_not_lexical(self):
        rows = [{"document_number": "EP-SM.MAN.6284", "version": version, "identity_verified": True,
                 "downloaded": version == "2.9", "url": version} for version in ("2.9", "2.10")]
        group = audit.compare_versions(rows, "honeywell")["families"][0]
        self.assertEqual(group["highest_observed_revision"], "2.10")
        self.assertTrue(group["newer_candidate_pending"])

    def test_same_revision_different_release_requires_review(self):
        result = audit.compare_versions([self.entry("AC", "a.pdf", release="Version 30.0"),
                                         self.entry("AC", "b.pdf", release="Version 31.1")], "siemens")
        self.assertTrue(result["families"][0]["review_required"])

    def test_front_matter_extracts_revision_and_release(self):
        result = refs.cover_metadata(["Operating Instructions A5E50811213-AF SIMATIC Industrial OS Version 31.1"], "siemens")
        self.assertEqual(result["document_number"], "A5E50811213")
        self.assertEqual(result["version"], "AF")
        self.assertEqual(result["product_releases"], ["Version 31.1"])
        honeywell = refs.cover_metadata(["EP-SM.MAN.6284 Issue 2.1 Release 162"], "honeywell")
        self.assertEqual(honeywell["version"], "2.1")

    def test_ambiguous_cover_cannot_assign_identity(self):
        result = refs.cover_metadata(["See A5E50811213-AC and A5E32565315-AS"], "siemens")
        self.assertEqual(result["status"], "ambiguous")
        self.assertNotIn("document_number", result)

    def test_annotations_and_classification(self):
        class Annotation:
            def get_object(self): return {"/A": {"/URI": "https://siemens.com/manual.pdf"}}
        self.assertEqual(refs.pdf_annotation_links({"/Annots": [Annotation()]}), ["https://siemens.com/manual.pdf"])
        for value, expected in (("Safety Manager SC Brochure", "marketing"), ("Safety Manager PIN", "marketing"),
                                ("Safety Training", "training"), ("FC-TUDL01 Technical Specification", "technical")):
            self.assertEqual(audit.classify(value), expected)

    def test_deduped_seed_counts_and_login_notice(self):
        parser = discovery.Links()
        parser.feed('<h1>Safety Manager</h1><p>Sign in to access more documents</p><a href="a.pdf">a</a><a href="a.pdf">a</a>')
        with patch.object(discovery, "fetch_links", return_value=("https://honeywell.com/p", parser)):
            result = discovery.discover({"id": "p", "seed_pages": ["https://honeywell.com/p"]}, ["honeywell.com"])
        self.assertEqual(result["pages"][0]["discovered_files"], 1)
        self.assertTrue(result["restricted_listing_notice"])

    def test_product_scope_excludes_sc_from_classic(self):
        original = watch.VENDOR
        try:
            watch.configure_brand("honeywell")
            item, evidence = watch.native_web_item({"url": "https://honeywell.com/safety-manager-sc/a.pdf", "title": "Safety Manager SC Manual"},
                                                   {"id": "classic", "keywords": ["Safety Manager"], "exclude_keywords": ["Safety Manager SC"]})
            self.assertIsNone(item)
            self.assertEqual(evidence["status"], "excluded_product_scope")
            queries = watch.query_plan({"products": [{"id": "p", "keywords": ["Safety Manager"], "manual_topics": ["Hardware Reference"]}]})
            self.assertEqual(len(queries), 4)
            self.assertIn('"Hardware Reference"', queries[-1]["query"])
        finally:
            watch.configure_brand(original)

    def test_cached_audit_quarantines_cross_url_versions_and_exports_leads(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = {"files": {}}
            items = []
            for revision in ("AC", "AF"):
                path = root / (revision + ".pdf")
                data = ("%PDF-1.7\n" + revision).encode()
                path.write_bytes(data)
                url = "https://cache.industry.siemens.com/" + revision + "_en-US.pdf"
                state["files"][revision] = {"url": url, "path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                    "reference": "A5E50811213-" + revision, "version": revision, "metadata_verified": True, "key": revision, "language": "en-us"}
                items.append({"key": revision, "reference": "A5E50811213-" + revision, "version": revision, "files": [{"download_url": url}]})
            atomic_json(root / "downloads" / ".siemens_download_state.json", state)
            rows = [{"path": record["path"], "local_status": "current"} for record in state["files"].values()]
            (root / "rag-index.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            def inspect(path, brand, max_pages):
                return {"metadata": {"status": "extracted", "document_number": "A5E50811213", "version": path.stem},
                    "errors": [], "text_pages": 1, "references": [{"document_number": "A5E03484625-AK", "pages": [7]}],
                    "links": [{"url": "https://support.industry.siemens.com/cs/ww/en/view/109742705", "pages": [8]}]}
            with patch.object(audit, "inspect_pdf", side_effect=inspect) as parse:
                summary = audit.audit(root, {"items": items}, "siemens", ["siemens.com"])
                audit.audit(root, {"items": items}, "siemens", ["siemens.com"])
            self.assertEqual(parse.call_count, 2)
            self.assertEqual(summary["review_required"], 1)
            self.assertEqual((root / "rag-current.jsonl").read_text(), "")
            self.assertEqual(len((root / "rag-review.jsonl").read_text().splitlines()), 2)
            plan = json.loads((root / "followup-plan.json").read_text())
            self.assertEqual(plan["queries"][0]["document_number"], "A5E03484625")
            self.assertEqual(len(plan["links"]), 1)


class IncrementalBrandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RegressionTests.setUpClass()
        cls.base = fixtures.RegressionTests.base

    @classmethod
    def tearDownClass(cls):
        fixtures.RegressionTests.tearDownClass()

    def test_both_brands_two_then_two_no_search_and_no_marketing(self):
        original = watch.VENDOR
        try:
            for brand in ("honeywell", "siemens"):
                with self.subTest(brand=brand), tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    watch.configure_brand(brand)
                    product = {"id": "p", "keywords": ["Test product"], "download_classes": ["technical"]}
                    results = [{"product": "p", "url": self.base + f"/{i}.pdf", "title": "Test product " + ("Manual" if i < 4 else "Brochure"),
                                "document_number": str(i), "verified": True} for i in range(5)]
                    args = argparse.Namespace(command="run", limit=2, max_results=0, search_only=False, revalidate=False)
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        first = watch.run_product(product, root, {"results": results}, args)
                        args.command = "resume"
                        with patch.object(watch, "discover", side_effect=AssertionError("Resume searched")):
                            second = watch.run_product(product, root, {}, args)
                            third = watch.run_product(product, root, {}, args)
                    self.assertEqual(first["catalog_count"], 5)
                    self.assertEqual(first["download_candidate_items"], 4)
                    self.assertEqual(first["download_summary"]["downloaded"], 2)
                    self.assertEqual(second["download_summary"]["downloaded"], 2)
                    self.assertEqual(second["download_summary"]["skipped"], 2)
                    self.assertEqual(third["download_summary"]["skipped"], 4)
                    self.assertEqual(third["download_summary"]["downloaded"], 0)
        finally:
            watch.configure_brand(original)


if __name__ == "__main__":
    unittest.main(verbosity=2)

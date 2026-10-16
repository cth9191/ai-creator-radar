import unittest

import fetch

SAMPLE = """# Changelog

## 2.1.301

- Added the `%` motion to vim mode
- [VSCode] Windows: Fixed a crash on start
- Improved artifact updates: Claude now republishes in one call
  and keeps the link
- Updated `/cost` figures

## 2.1.300

- Fixed something
"""


class ParseTest(unittest.TestCase):
    def test_versions_and_items(self):
        rels = fetch.parse_changelog(SAMPLE)
        self.assertEqual([r["version"] for r in rels], ["2.1.301", "2.1.300"])
        items = rels[0]["items"]
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0]["kind"], "added")
        self.assertEqual(items[1], {"kind": "fixed", "area": "VSCode / Windows", "text": "Fixed a crash on start"})
        self.assertEqual(items[2]["kind"], "improved")
        self.assertIsNone(items[2]["area"])
        self.assertTrue(items[2]["text"].endswith("and keeps the link"))
        self.assertEqual(items[3]["kind"], "changed")

    def test_highlights_prefer_new_features(self):
        items = fetch.parse_changelog(SAMPLE)[0]["items"]
        kinds = [h["kind"] for h in fetch.pick_highlights(items, n=2)]
        self.assertEqual(kinds, ["added", "improved"])

    def test_title(self):
        counts, summary = fetch.summarize(fetch.parse_changelog(SAMPLE)[0])
        self.assertEqual(fetch.title(counts, summary), "1 new feature, 1 improvement, 1 change, 1 fix")


if __name__ == "__main__":
    unittest.main()

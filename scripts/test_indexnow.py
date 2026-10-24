"""IndexNow helper checks. Run: python3 scripts/test_indexnow.py"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import indexnow_ping as ip


class IndexNow(unittest.TestCase):
    def test_key_file_at_root(self):
        key = ip.find_key()
        self.assertRegex(key or "", r"^[0-9a-f]{32}$")
        with open(os.path.join(ip.ROOT, key + ".txt"), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), key)

    def test_pages_served_without_jekyll(self):
        self.assertTrue(os.path.exists(os.path.join(ip.ROOT, ".nojekyll")))

    def test_bing_site_auth(self):
        with open(os.path.join(ip.ROOT, "BingSiteAuth.xml"), encoding="utf-8") as f:
            self.assertIn("<user>", f.read())

    def test_path_to_url(self):
        self.assertEqual(ip.path_to_url("index.html"), "https://lumitrades.io/")
        self.assertEqual(ip.path_to_url("es/agents/index.html"), "https://lumitrades.io/es/agents/")
        self.assertEqual(ip.path_to_url("feed.xml"), "https://lumitrades.io/feed.xml")

    def test_sitemap_urls(self):
        urls = ip.sitemap_urls(os.path.join(ip.ROOT, "sitemap.xml"))
        self.assertIn("https://lumitrades.io/", urls)
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all(u.startswith("https://lumitrades.io/") for u in urls))


if __name__ == "__main__":
    unittest.main()

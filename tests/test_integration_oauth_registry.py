import unittest

import integration_oauth
from integration_oauth_registry import OAUTH_PROVIDERS
from integrations_catalog import INTEGRATION_CATEGORIES, enrich_integration


class IntegrationOAuthRegistryTests(unittest.TestCase):
    def test_registry_has_all_109(self) -> None:
        self.assertEqual(len(OAUTH_PROVIDERS), 109)

    def test_registry_slugs_exist_in_catalog(self) -> None:
        catalog_slugs = {
            item["slug"]
            for category in INTEGRATION_CATEGORIES
            for item in category["integrations"]
        }
        for slug in OAUTH_PROVIDERS:
            self.assertIn(slug, catalog_slugs, f"OAuth slug missing from catalog: {slug}")

    def test_enrich_marks_oauth_providers(self) -> None:
        item = enrich_integration({"slug": "github", "name": "GitHub"})
        self.assertIn("oauth", item["auth_methods"])
        self.assertTrue(item["oauth_available"])

    def test_catalog_slug_has_oauth_slot(self) -> None:
        item = enrich_integration({"slug": "wordpress", "name": "WordPress"})
        self.assertIn("oauth", item["auth_methods"])
        self.assertTrue(item["oauth_available"])
        self.assertFalse(item["oauth_configured"])

    def test_is_oauth_provider(self) -> None:
        self.assertTrue(integration_oauth.is_oauth_provider("github"))
        self.assertTrue(integration_oauth.is_oauth_provider("wordpress"))
        self.assertFalse(integration_oauth.is_oauth_provider("not-in-catalog"))


if __name__ == "__main__":
    unittest.main()

"""Public SEO files (robots.txt, sitemap.xml)."""

from __future__ import annotations

from xml.sax.saxutils import escape

from app_urls import public_app_base_url

_SITEMAP_PATHS: tuple[tuple[str, str, str], ...] = (
    ("", "daily", "1.0"),
    ("/login", "monthly", "0.6"),
    ("/signup", "monthly", "0.7"),
    ("/privacy-policy", "monthly", "0.4"),
    ("/terms-and-conditions", "monthly", "0.4"),
    ("/licence-agreement", "monthly", "0.4"),
    ("/agent-notes", "monthly", "0.5"),
)


def robots_txt() -> str:
    base = public_app_base_url().rstrip("/")
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        "Disallow: /webhooks/\n"
        "Disallow: /agent\n"
        "Disallow: /businesses\n"
        "Disallow: /data\n"
        "Disallow: /billing\n"
        "Disallow: /settings\n"
        f"\nSitemap: {base}/sitemap.xml\n"
    )


def sitemap_xml() -> str:
    base = public_app_base_url().rstrip("/")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, changefreq, priority in _SITEMAP_PATHS:
        loc = f"{base}{path}" if path else base
        lines.extend(
            (
                "  <url>",
                f"    <loc>{escape(loc)}</loc>",
                f"    <changefreq>{changefreq}</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            )
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"

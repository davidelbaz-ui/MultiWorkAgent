"""Print commented OAuth env block for .env.example (all 109 integrations)."""

from integration_oauth_registry import list_env_keys_table

lines = [
    "# Integration OAuth (platform apps). Callback: {APP_BASE_URL}/integrations/oauth/callback",
    "# All 109 catalog integrations — uncomment and fill as you register each OAuth app.",
    "# Regenerate: PYTHONPATH=. python scripts/gen_env_oauth_example.py",
]
for row in list_env_keys_table():
    wired = "wired" if row["urls_configured"] == "yes" else "urls TBD in integration_oauth_registry.py"
    lines.append(f"# {row['slug']} ({row['name']}) [{wired}]")
    lines.append(f"# {row['client_id_env']}=")
    lines.append(f"# {row['client_secret_env']}=")
    lines.append("")
print("\n".join(lines))

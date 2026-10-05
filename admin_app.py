"""Optional: run the main app on port 8000 — operator UI is at /admin (same as Vercel)."""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass

from app import APP_CONFIG, app

if __name__ == "__main__":
    host = os.environ.get("ADMIN_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.environ.get("ADMIN_PORT", "8000"))
    print(f"Open http://{host}:{port}/admin")
    app.run(host=host, port=port, debug=APP_CONFIG.debug)

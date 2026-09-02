"""
Inject the data cube (outputs/dashboard_data.json) into the dashboard page
template (outputs/dashboard_template.html), producing two publishable files:

  outputs/dashboard.html — fragment (no <html>/<head>/<body>) for Claude
    Artifact publishing, which wraps the page itself.
  docs/index.html — a complete, standalone HTML document (explicit
    <!DOCTYPE>, <html>, <head> with a charset, <body>) for GitHub Pages or
    any other static host, which does no such wrapping on its own. Without
    an explicit charset a browser can mis-guess the encoding and mangle
    non-ASCII characters (em dashes, arrows) in the page copy.

Edit outputs/dashboard_template.html for markup/style/logic changes, then
re-run this (after re-running build_dashboard_data.py if the underlying
data changed) rather than editing either output directly.

Run: python src/build_dashboard_data.py && python src/build_dashboard_html.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT / "outputs"
DOCS_DIR = ROOT / "docs"
TEMPLATE_PATH = OUTPUTS_DIR / "dashboard_template.html"
DATA_PATH = OUTPUTS_DIR / "dashboard_data.json"
FRAGMENT_OUTPUT_PATH = OUTPUTS_DIR / "dashboard.html"
STANDALONE_OUTPUT_PATH = DOCS_DIR / "index.html"
PLACEHOLDER = "/*__DASHBOARD_DATA__*/"


def main():
    template = TEMPLATE_PATH.read_text()
    data_json = DATA_PATH.read_text()
    if PLACEHOLDER not in template:
        raise ValueError(f"Placeholder {PLACEHOLDER!r} not found in {TEMPLATE_PATH}")
    fragment = template.replace(PLACEHOLDER, data_json)

    FRAGMENT_OUTPUT_PATH.write_text(fragment)
    print(f"Wrote {FRAGMENT_OUTPUT_PATH} ({FRAGMENT_OUTPUT_PATH.stat().st_size / 1e6:.2f} MB)")

    body_marker = '<div class="app">'
    split_at = fragment.index(body_marker)
    head_part, body_part = fragment[:split_at], fragment[split_at:]
    standalone = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"{head_part}"
        "\n</head>\n<body>\n"
        f"{body_part}"
        "\n</body>\n</html>\n"
    )
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    STANDALONE_OUTPUT_PATH.write_text(standalone)
    print(f"Wrote {STANDALONE_OUTPUT_PATH} ({STANDALONE_OUTPUT_PATH.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()

"""
Inject the data cube (outputs/dashboard_data.json) into the dashboard page
template (outputs/dashboard_template.html), producing the publishable
outputs/dashboard.html.

Edit outputs/dashboard_template.html for markup/style/logic changes, then
re-run this (after re-running build_dashboard_data.py if the underlying
data changed) rather than editing dashboard.html directly.

Run: python src/build_dashboard_data.py && python src/build_dashboard_html.py
"""

from pathlib import Path

OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"
TEMPLATE_PATH = OUTPUTS_DIR / "dashboard_template.html"
DATA_PATH = OUTPUTS_DIR / "dashboard_data.json"
OUTPUT_PATH = OUTPUTS_DIR / "dashboard.html"
PLACEHOLDER = "/*__DASHBOARD_DATA__*/"


def main():
    template = TEMPLATE_PATH.read_text()
    data_json = DATA_PATH.read_text()
    if PLACEHOLDER not in template:
        raise ValueError(f"Placeholder {PLACEHOLDER!r} not found in {TEMPLATE_PATH}")
    final = template.replace(PLACEHOLDER, data_json)
    OUTPUT_PATH.write_text(final)
    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()

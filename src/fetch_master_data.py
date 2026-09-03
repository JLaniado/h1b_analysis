"""
Download the consolidated master data files on demand.

`data/interim/{lca,perm}_master.csv.gz` are built by `consolidate_raw.py`
from the raw DOL exports, but at ~216MB / ~55MB (gzip-compressed) they're
too big to commit to git normally. They're published instead as assets on
a GitHub Release of this repo — this module fetches them into place the
first time anything tries to load data and they're not already there
(a fresh `git clone`, a cloud deploy, a classmate's laptop), so nobody has
to run the raw-data pipeline themselves just to use the app.

If you regenerate the master files (new raw data dropped in data/raw/,
`python src/consolidate_raw.py` re-run), re-upload them to the release so
everyone else's next auto-download picks up the update:
  gh release upload data-v1 data/interim/lca_master.csv.gz data/interim/perm_master.csv.gz --clobber
"""

import urllib.request
from pathlib import Path

INTERIM_DIR = Path(__file__).resolve().parent.parent / "data" / "interim"
RELEASE_BASE_URL = "https://github.com/JLaniado/h1b_analysis/releases/download/data-v1"

FILES = ["lca_master.csv.gz", "perm_master.csv.gz"]


def ensure_master_data(progress_callback=None) -> None:
    """Download any missing master data file into data/interim/.

    progress_callback(filename, downloaded_bytes, total_bytes), if given, is
    called periodically during each download — e.g. to drive a Streamlit
    progress bar. Does nothing for files that already exist locally.
    """
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        dest = INTERIM_DIR / filename
        if dest.exists():
            continue
        url = f"{RELEASE_BASE_URL}/{filename}"
        tmp_dest = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(url) as response, open(tmp_dest, "wb") as out_f:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            while chunk := response.read(1024 * 1024):
                out_f.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(filename, downloaded, total)
        tmp_dest.rename(dest)


if __name__ == "__main__":
    def _print_progress(filename, downloaded, total):
        pct = downloaded / total * 100 if total else 0
        print(f"\r{filename}: {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({pct:.0f}%)", end="")

    ensure_master_data(progress_callback=_print_progress)
    print("\nDone.")

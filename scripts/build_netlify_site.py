"""Builds the standalone Netlify deployment site in dist_netlify/."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist_netlify"
DIST.mkdir(parents=True, exist_ok=True)
DIST_REPORTS = DIST / "reports"
DIST_REPORTS.mkdir(parents=True, exist_ok=True)
DIST_SCREENSHOTS = DIST / "reports" / "screenshots"
DIST_SCREENSHOTS.mkdir(parents=True, exist_ok=True)

# Copy reports and screenshots
src_reports = ROOT / "reports"
if src_reports.exists():
    for f in src_reports.glob("report_*.html"):
        shutil.copy2(f, DIST_REPORTS / f.name)
    for f in src_reports.glob("report_*.json"):
        shutil.copy2(f, DIST_REPORTS / f.name)
    
src_screenshots = ROOT / "reports" / "screenshots"
if src_screenshots.exists():
    for f in src_screenshots.glob("*.png"):
        shutil.copy2(f, DIST_SCREENSHOTS / f.name)

# Also copy sample_page.html
sample_html = ROOT / "tests" / "sample_page.html"
if sample_html.exists():
    shutil.copy2(sample_html, DIST / "sample_page.html")

print("Copied reports and evidence to dist_netlify/")

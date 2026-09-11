"""One-off cleaner for the 4 new PDFs (alcohol, breakfast, headaches,
lung_cancer) — mirrors the same process used for the original 9 papers:
pdftotext -> strip running headers/footers/page numbers -> flatten ->
truncate to ~3000 words -> prepend a Title/Source citation header.

Usage: .venv/Scripts/python.exe scripts/clean_new_papers.py
"""
import re
import subprocess
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample_papers"
OUT_DIR = Path(__file__).parent.parent / "data" / "health_papers"

# (pdf filename, output filename, Title, Source citation line, extra noise-line patterns)
PAPERS = [
    (
        "alcohol.pdf",
        "11_alcohol_cvd.txt",
        "Alcohol use and burden for 195 countries and territories, 1990-2016: a systematic analysis for the Global Burden of Disease Study 2016.",
        "Lancet. 2018 Sep 22;392(10152):1015-1035. doi: 10.1016/S0140-6736(18)31310-2.",
        [
            r"^Articles$",
            r"^www\.thelancet\.com.*$",
            r"^See Comment.*$",
            r"^\*Collaborators listed.*$",
        ],
    ),
    (
        "breakfast.pdf",
        "12_breakfast_weight.txt",
        "Effect of breakfast on weight and energy intake: systematic review and meta-analysis of randomised controlled trials.",
        "BMJ. 2019 Jan 30;364:l42. doi: 10.1136/bmj.l42.",
        [
            r"^RESEARCH$",
            r"^BMJ: first published.*$",
            r"^thebmj\|.*$",
        ],
    ),
    (
        "headaches.pdf",
        "13_msg_headache.txt",
        "Does monosodium glutamate really cause headache?: a systematic review of human studies.",
        "J Headache Pain. 2016;17:54. doi: 10.1186/s10194-016-0639-4.",
        [
            r"^Obayashi and Nagamura The Journal of Headache and Pain.*$",
            r"^REVIEW ARTICLE$",
            r"^Open Access$",
            r"^Page \d+ of \d+$",
        ],
    ),
    (
        "lung_cancer.pdf",
        "14_betacarotene_lung_cancer.txt",
        "Effects of a Combination of Beta Carotene and Vitamin A on Lung Cancer and Cardiovascular Disease.",
        "N Engl J Med. 1996 May 2;334(18):1150-5.",
        [
            r"^THE NEW ENGLAND JOURNAL OF MEDICINE$",
            r"^Vol\. \d+ No\. \d+.*$",
            r"^The New England Journal of Medicine is produced by.*$",
        ],
    ),
]

COMMON_NOISE = [
    r"^\d{1,4}$",  # bare page numbers
    r"^Downloaded from .*$",
    r"^Copyright.*$",
]


def clean(pdf_path: Path, extra_patterns: list[str]) -> str:
    raw = subprocess.run(
        ["pdftotext", str(pdf_path), "-"], capture_output=True, text=True, check=True
    ).stdout
    patterns = [re.compile(p) for p in (COMMON_NOISE + extra_patterns)]
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(p.match(stripped) for p in patterns):
            continue
        lines.append(stripped)
    flat = " ".join(lines)
    flat = re.sub(r"\s+", " ", flat).strip()
    words = flat.split(" ")
    return " ".join(words[:3000])


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for pdf_name, out_name, title, source, extra_patterns in PAPERS:
        pdf_path = SAMPLE_DIR / pdf_name
        if not pdf_path.exists():
            print(f"  [skip] {pdf_name} not found")
            continue
        body = clean(pdf_path, extra_patterns)
        header = f"Title: {title}\n\nSource: {source}\n\n"
        out_path = OUT_DIR / out_name
        out_path.write_text(header + body, encoding="utf-8")
        print(f"  [ok] {pdf_name} -> {out_name} ({len(body.split())} words)")


if __name__ == "__main__":
    main()

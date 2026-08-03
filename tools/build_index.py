#!/usr/bin/env python3
"""Generate INDEX.md from the wigs in the repo.

A git repository offers no download counts and no view counts, and stars
are repo-wide. Fitting count is the only honest popularity signal
available here, and it happens to be the right one: a wig with five
independent fittings is simultaneously the most used and the most
proven. So that is the column the table sorts on.

Usage:

    build_index.py --hair-src PATH [--root .] [--check]

``--check`` writes nothing and exits 1 if INDEX.md is out of date, which
is how CI keeps the committed file honest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_wigs import WIG_SUFFIX, WIGS_DIR, discover, load_hair  # noqa: E402

HEADER = """# Index

Every wig in the shop. Generated from the files by
[`tools/build_index.py`](tools/build_index.py) and rewritten on merge,
so edits here are overwritten. Change a wig, not this page.

**Fittings** is how many people proved every row of this wig on their
own hardware. It is the closest thing to a rating this repo has, and
unlike a star it costs somebody real time at real hardware. Three
fittings from three different people makes a wig eligible for
[WigFactory](https://github.com/DAB-LABS/WigFactory).

**Covered** is how many rows anybody has proven, pooled across
everyone. It can reach the full count while Fittings is still zero:
three people who each proved a different third have not, between them,
produced anybody who can say the whole wig works. Both numbers are
true, and they answer different questions.

Use your browser's find to search this page by brand, kind, model or
product identifier.
"""

EMPTY = """
## No wigs yet

The shop is open and nothing has landed in it.

If you have a remote working in HAIR, you are most of the way there.
Fit it, download it, and open a pull request:
[CONTRIBUTING.md](CONTRIBUTING.md). The first entry is the one everyone
else copies.
"""

FOOTER = """
---

**Kind** says what the device is, and it is what most people search by.
**Identifiers** are FCC IDs, UPCs and ASINs, which are how hardware with
no meaningful brand stays findable.

Nothing here was accepted on somebody's word. Every row was proven on
real hardware by the people named in its fittings.
"""


def escape(value: str) -> str:
    """Keep a stray pipe in a model number from breaking the table."""
    return value.replace("|", "\\|")


def wig_row(rel_path: str, wig, mods) -> tuple[str, int, str]:
    """One table row, plus the sort keys behind it.

    Fittings counts PERFECT fits, using HAIR's ``bundle_is_complete``,
    so the number means exactly what a green check means in the Closet.
    Covered is the union across everybody, which HAIR hands to the shop
    as judgement rather than a check. Keeping them in separate columns
    is deliberate: coverage must never be able to read as proof.
    """
    wf = mods["wig_format"]
    wfit = mods["wig_fitting"]

    bundles = wf.claims_of(wig)
    digests = wf.wig_row_digests(wig)
    perfect = [b for b in bundles if wfit.bundle_is_complete(b, wig, digests)]
    handles = sorted({b.handle for b in perfect if b.handle})

    if wig.climate is not None:
        # A matrix wig's claims bind the lattice as a set, so there is no
        # per-row union to report. Saying "0/0" would read as nothing
        # proven, which is the opposite of the truth for a signed
        # checklist.
        covered = "matrix"
    else:
        covered = f"{len(wf.coverage(bundles, digests))}/{len(digests)}"

    ids = []
    for key in sorted(wig.identifiers or {}):
        for value in wf.identifier_values(wig.identifiers, key):
            ids.append(f"{key}: {value}")

    brand = wig.brand or Path(rel_path).parent.name
    name = escape(wig.name)
    link = f"[{name}]({rel_path})"

    row = (
        "| {brand} | {kind} | {model} | {link} | {count} | {covered} "
        "| {who} | {ids} |"
    ).format(
        brand=escape(brand),
        kind=escape(wig.kind or ""),
        model=escape(wig.model or ""),
        link=link,
        count=len(perfect),
        covered=covered,
        who=escape(", ".join(handles)),
        ids=escape("; ".join(ids)),
    )
    return row, len(perfect), brand.lower()


def unreadable_section(unreadable: list[str]) -> str:
    """The files that did not parse, named rather than silently dropped."""
    if not unreadable:
        return ""
    listed = "\n".join(f"- `{p}`" for p in unreadable)
    return (
        "\n## Not readable\n\nThese files did not parse and are left "
        "out of the table above. A wig written for a newer format major "
        "than the pinned HAIR reads this way, and so does a damaged "
        "file:\n\n" + listed + "\n"
    )


def build(root: Path, mods) -> str:
    wf = mods["wig_format"]
    rows: list[tuple[str, int, str]] = []
    unreadable: list[str] = []

    for rel_path in discover(root):
        text = (root / rel_path).read_text(encoding="utf-8")
        result = wf.parse_wig(text)
        if not result.ok or result.wig is None:
            unreadable.append(rel_path)
            continue
        rows.append(wig_row(rel_path, result.wig, mods))

    parts = [HEADER]

    if not rows:
        # Not "the shop is empty" when files exist and none of them
        # parsed. That distinction cost a front page once: one
        # unreadable wig in a corpus of one rendered the empty state,
        # so the index cheerfully announced that nothing had ever
        # landed here.
        parts.append(EMPTY if not unreadable else "\n")
        parts.append(unreadable_section(unreadable))
        return "".join(parts).rstrip() + "\n"

    # Most proven first, then alphabetical so the order is stable.
    rows.sort(key=lambda r: (-r[1], r[2], r[0]))

    parts.append(
        f"\n{len(rows)} wig(s).\n\n"
        "| Brand | Kind | Model | Wig | Fittings | Covered | Fitted by | Identifiers |\n"
        "|---|---|---|---|---:|---:|---|---|\n"
    )
    parts.append("\n".join(row for row, _, _ in rows))
    parts.append("\n")

    parts.append(unreadable_section(unreadable))

    parts.append(FOOTER)
    return "".join(parts).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate INDEX.md.")
    parser.add_argument("--hair-src", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing; exit 1 if INDEX.md is out of date",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    mods = load_hair(args.hair_src)
    content = build(root, mods)
    target = root / "INDEX.md"

    if args.check:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != content:
            print(
                "INDEX.md is out of date. Regenerate it with:\n"
                "  python3 tools/build_index.py --hair-src <hair checkout>"
            )
            return 1
        print("INDEX.md is up to date.")
        return 0

    target.write_text(content, encoding="utf-8")
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

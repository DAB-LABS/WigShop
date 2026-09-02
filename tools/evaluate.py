#!/usr/bin/env python3
"""Write the evaluation of one pull request.

The checks decide; this only reports. Nothing here judges a wig, adds a
rule, or changes a verdict: it runs exactly what CI runs, through
``validate_wigs.run_checks``, and writes down what came back.

WHY A FILE AND NOT A COMMENT. The evaluation is an artifact on the run,
never posted anywhere. What gets said to a contributor is a separate
thing built from this, so the way the shop talks to people can change
without touching what the shop records. It also means the evaluation can
be blunt: it is an inspection sheet, not a reply.

WHY ONE FILE WITH BOTH HALVES. English at the top so a person can open
it and stop reading when they have what they need, and the same findings
as data at the bottom so a reviewing agent takes facts rather than
parsing prose back out of sentences. One file, because two would drift
and somebody would eventually read the stale one.

WHAT THE ENGLISH IS NOT. It is generated, so it reads like an inspection
sheet, and it is meant to. Warmth is the barber's job further down the
pipe, and string templates pretending to be friendly would produce
exactly the tone this project is trying to avoid.

Usage:

    evaluate.py --hair-src PATH [--base-ref REF] [--pr N]
                [--previous PRIOR.md] [--out evaluation.md] FILES...

``--previous`` points at the evaluation from this pull request's last
run. When given, the new file opens with what changed, which is the
thing worth reading on a resubmission and is far better than repeating
the first evaluation at somebody who has already read it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_wigs import (
    WIG_SUFFIX,
    discover,
    load_hair,
    run_checks,
)

#: Bump when the shape of the data block changes in a way a reader
#: cannot absorb silently. The English above it is free to change.
SCHEMA = 1

FENCE = "```json"

VERDICTS = {
    "refuse": "not accepted",
    "accept-with-notes": "accepted, with things to read",
    "accept": "accepted",
}


def verdict_of(report) -> str:
    """One of three, and the middle one is not decoration.

    "Accepted with things to read" is the state a reviewing agent must
    not be able to round up to "accepted", which is why it is a value
    here rather than something derived from whether a list happens to
    be empty.
    """
    if not report.ok:
        return "refuse"
    if any(e.level == "warn" for e in report.entries):
        return "accept-with-notes"
    return "accept"


def facts(report, wigs: list[str], pr: int | None, hair_ref: str) -> dict:
    """The data block: the same findings, without the sentences around
    them."""
    by_path: dict[str, list] = defaultdict(list)
    for entry in report.entries:
        by_path[entry.path].append(entry.as_dict())

    return {
        "schema": SCHEMA,
        "pr": pr,
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hair_ref": hair_ref,
        "verdict": verdict_of(report),
        "checked": report.checked,
        "wigs": [
            {"path": path, "findings": by_path.get(path, [])}
            for path in wigs
        ],
        # Findings that belong to the pull request rather than to any
        # one file: a wig removed with no successor, two files sharing
        # an id. They have nowhere else to go and must not be dropped.
        "shelf": [
            entry.as_dict()
            for entry in report.entries
            if entry.path not in set(wigs)
        ],
    }


def read_previous(path: Path) -> dict | None:
    """The data block out of an earlier evaluation, or None."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"```json\n(.*?)\n```", text, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _shape(block: dict) -> dict[str, tuple[set[str], int]]:
    """Per path: the coded findings, and how many uncoded ones there are.

    Only codes are named in a delta. An uncoded finding has nothing
    short to call it, and splicing its whole sentence into a
    comma-joined list produces a paragraph nobody can read -- which is
    what the first version of this did.
    """
    out: dict[str, tuple[set[str], int]] = {}
    for wig in block.get("wigs") or []:
        codes: set[str] = set()
        uncoded = 0
        for finding in wig.get("findings") or []:
            code = finding.get("code")
            if code:
                codes.add(code)
            else:
                uncoded += 1
        out[wig["path"]] = (codes, uncoded)
    return out


def since_last_time(previous: dict, current: dict) -> list[str]:
    """What changed between two evaluations of the same pull request.

    On a resubmission this is the only part worth reading. Repeating an
    evaluation somebody has already read teaches them to skip it, and
    the whole reason to keep the artifacts is so the second answer can
    be about the delta.
    """
    lines: list[str] = []

    was, now = previous.get("verdict"), current.get("verdict")
    if was != now:
        lines.append(
            f"The verdict moved from **{VERDICTS.get(was, was)}** to "
            f"**{VERDICTS.get(now, now)}**."
        )
    else:
        lines.append(f"Still **{VERDICTS.get(now, now)}**.")
    lines.append("")

    before, after = _shape(previous), _shape(current)
    moved = False
    for path in sorted(set(before) | set(after)):
        was_codes, was_uncoded = before.get(path, (set(), 0))
        now_codes, now_uncoded = after.get(path, (set(), 0))
        gone = sorted(was_codes - now_codes)
        fresh = sorted(now_codes - was_codes)
        if not gone and not fresh and was_uncoded == now_uncoded:
            continue
        moved = True
        lines.append(f"`{Path(path).name}`")
        if gone:
            lines.append(f"- cleared: {', '.join(gone)}")
        if fresh:
            lines.append(f"- new: {', '.join(fresh)}")
        if was_uncoded != now_uncoded:
            lines.append(
                f"- other findings: {was_uncoded} to {now_uncoded}"
            )
        lines.append("")

    if not moved:
        lines.append("No finding changed on any wig.")
        lines.append("")
    return lines


def render(block: dict, report, previous: dict | None) -> str:
    """The evaluation, English first."""
    pr = block.get("pr")
    title = f"Evaluation: PR #{pr}" if pr else "Evaluation"
    out = [f"# {title}", ""]
    out.append(f"**Verdict: {VERDICTS[block['verdict']]}.**")
    out.append("")

    if previous is not None:
        out.append("## Since last time")
        out.append("")
        out.extend(since_last_time(previous, block))
        out.append("")

    checked = block["checked"]
    out.append(
        f"{checked} wig(s) checked against HAIR {block['hair_ref']}."
    )
    out.append("")

    for wig in block["wigs"]:
        out.append(f"## `{wig['path']}`")
        out.append("")
        findings = wig["findings"]
        if not findings:
            out.append("Nothing to report. Every check passed clean.")
            out.append("")
            continue
        for level, heading in (
            ("fail", "Refused"),
            ("warn", "Worth reading"),
            ("note", "Recorded"),
        ):
            picked = [f for f in findings if f["level"] == level]
            if not picked:
                continue
            out.append(f"**{heading}**")
            out.append("")
            for finding in picked:
                out.append(f"- {finding['text']}")
            out.append("")

    if block["shelf"]:
        out.append("## The shelf as a whole")
        out.append("")
        for finding in block["shelf"]:
            out.append(f"- {finding['text']}")
        out.append("")

    out.append("## The facts")
    out.append("")
    out.append(
        "The same findings as data. A reviewing agent reads this rather "
        "than the prose above, so it cannot mistake a warning for a pass "
        "or invent a finding nobody made."
    )
    out.append("")
    out.append(FENCE)
    out.append(json.dumps(block, indent=1, sort_keys=False))
    out.append("```")
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the evaluation of one pull request."
    )
    parser.add_argument("files", nargs="*", help="the wigs this PR touches")
    parser.add_argument("--hair-src", required=True)
    parser.add_argument("--base-ref", default=None)
    parser.add_argument("--root", default=".")
    parser.add_argument("--pr", type=int, default=None)
    parser.add_argument(
        "--previous",
        default=None,
        help="this PR's evaluation from its last run, to diff against",
    )
    parser.add_argument("--out", default="evaluation.md")
    parser.add_argument(
        "--hair-ref",
        default="unknown",
        help="the HAIR release the checks ran against, for the record",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    mods = load_hair(args.hair_src)

    # Only the wigs this pull request touches (owner ruling 2026-09-02).
    # A shelf-wide evaluation would bury the one file somebody is
    # waiting on under everything that was already there.
    targets = [
        Path(f).as_posix()
        for f in (args.files or discover(root))
        if str(f).endswith(WIG_SUFFIX)
    ]

    report = run_checks(
        root, targets, args.base_ref, mods, submitted=bool(args.files)
    )
    present = [p for p in targets if (root / p).exists()]
    block = facts(report, present, args.pr, args.hair_ref)

    previous = read_previous(Path(args.previous)) if args.previous else None

    Path(args.out).write_text(
        render(block, report, previous), encoding="utf-8"
    )
    print(f"Wrote {args.out}: {VERDICTS[block['verdict']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

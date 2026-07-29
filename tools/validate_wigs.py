#!/usr/bin/env python3
"""Validate wigs in the shop against HAIR's own format rules.

Every check here wraps something HAIR already owns. The shop does not
carry a second implementation of the wig format: it imports
``custom_components.hair.wig_format`` and friends from a pinned HAIR
checkout, so a wig that passes here parses on a real install and a wig
that fails here would have failed there too.

Usage:

    validate_wigs.py --hair-src PATH [--base-ref REF] [FILE ...]

With FILE arguments it validates exactly those wigs, and, when
``--base-ref`` names a git ref where a file already exists, also checks
the two rules that only mean anything against a previous version:
signals may not change, and fittings may not disappear.

With no FILE arguments it validates every wig in ``wigs/``.

Exit code is 0 when nothing failed, 1 otherwise. Warnings never fail
the run; they are there for a human to glance at.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

WIG_SUFFIX = ".wig.json"
WIGS_DIR = "wigs"
UNBRANDED = "unbranded"

# Mechanical, so they are enforced. Anything needing judgement is a
# warning and stays with the human reviewer.
BRAND_FOLDER_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FILENAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass
class Report:
    """Everything one run found, grouped by the file it came from."""

    failures: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    warnings: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    checked: int = 0

    def fail(self, path: str, message: str) -> None:
        self.failures[path].append(message)

    def warn(self, path: str, message: str) -> None:
        self.warnings[path].append(message)

    @property
    def ok(self) -> bool:
        return not self.failures


def load_hair(hair_src: str):
    """Import HAIR's format modules from a checkout.

    ``hair_src`` is the root of a HAIR clone: the directory holding
    ``custom_components/``.
    """
    sys.path.insert(0, hair_src)
    pkg_init = Path(hair_src) / "custom_components" / "__init__.py"
    if not pkg_init.exists():
        pkg_init.parent.mkdir(parents=True, exist_ok=True)
        pkg_init.write_text("")
    # HAIR's own package __init__ pulls in Home Assistant, which is not
    # installed here and is not needed: the format modules are stdlib
    # only. Import the submodules directly under a stub package.
    import importlib.util
    import types

    hair_dir = Path(hair_src) / "custom_components" / "hair"
    stub = types.ModuleType("hairfmt")
    stub.__path__ = [str(hair_dir)]
    sys.modules["hairfmt"] = stub

    mods = {}
    for name in (
        "const",
        "pronto_validator",
        "wig_format",
        "wig_climate",
        "wig_fitting",
        "fitting_signing",
    ):
        spec = importlib.util.spec_from_file_location(
            f"hairfmt.{name}", hair_dir / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"hairfmt.{name}"] = module
        spec.loader.exec_module(module)
        mods[name] = module
    return mods


def git_show(ref: str, path: str) -> str | None:
    """The content of ``path`` at ``ref``, or None when it is not there."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def github_key(value: object) -> str | None:
    """The canonical form of a GitHub handle, for comparison only.

    People type this field by hand, so the same account arrives as
    ``dab``, ``@dab``, ``DAB`` and ``github.com/dab``. Left alone, one
    person on two installs reads as two distinct contributors, which is
    exactly what the factory's three-distinct-handles gate is supposed
    to prevent.

    This never rewrites a file. Fittings are signed over their own
    contents, so normalizing ``@dab`` to ``dab`` on disk would break the
    signature and violate the immutability rule at the same time. The
    canonical form exists to compare with, not to store.

    Case-folded because GitHub usernames are case-insensitive, and the
    leading ``@`` is dropped because it is not a legal username
    character, so removing it loses nothing.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    for prefix in (
        "https://github.com/",
        "http://github.com/",
        "www.github.com/",
        "github.com/",
    ):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.lstrip("@").strip()
    # A pasted URL often carries more than the account: a repo path
    # (github.com/name/repo) or a query (github.com/name?tab=stars).
    # Keep the first segment only. Without this the key comes back as
    # "name/repo", which is not merely useless, it is wrong: it makes
    # one account look like a different contributor from the same
    # account typed plainly, which is the exact failure this function
    # exists to prevent.
    for sep in ("/", "?", "#"):
        text = text.split(sep, 1)[0]
    return text.strip().casefold() or None


def fitting_identity(raw: dict) -> tuple[str, str]:
    """What makes two fitting entries 'the same fitting'.

    Handle plus content hash. A person refitting the same codes replaces
    their own entry rather than stacking a second one, and that is the
    only case where a fitting legitimately changes.

    The handle is compared case-insensitively so that somebody who
    refits as ``david`` having first fitted as ``David`` does not read
    as having deleted their own earlier fitting.
    """
    return (
        str(raw.get("handle", "")).strip().casefold(),
        str(raw.get("content_hash", "")),
    )


def check_path_shape(rel_path: str, report: Report) -> str | None:
    """Folder and filename rules. Returns the brand folder, or None."""
    parts = Path(rel_path).parts
    if len(parts) != 3 or parts[0] != WIGS_DIR:
        report.fail(
            rel_path,
            f"wigs live at {WIGS_DIR}/<brand>/<file>{WIG_SUFFIX}; "
            f"this path has {len(parts)} segments",
        )
        return None

    _, brand_folder, filename = parts

    if not BRAND_FOLDER_RE.match(brand_folder):
        report.fail(
            rel_path,
            f"brand folder {brand_folder!r} must be lowercase ascii "
            "letters, digits and single hyphens",
        )

    if not filename.endswith(WIG_SUFFIX):
        report.fail(rel_path, f"filename must end in {WIG_SUFFIX}")
        return brand_folder

    stem = filename[: -len(WIG_SUFFIX)]
    if not FILENAME_RE.match(stem):
        report.fail(
            rel_path,
            f"filename stem {stem!r} must be lowercase ascii letters, "
            "digits and single hyphens",
        )
    elif not stem.startswith(f"{brand_folder}-") and stem != brand_folder:
        report.fail(
            rel_path,
            f"filename must start with the brand folder: expected "
            f"{brand_folder}-<kind>-<model>{WIG_SUFFIX}, got {filename}",
        )

    return brand_folder


def check_wig(
    rel_path: str,
    text: str,
    brand_folder: str | None,
    mods,
    report: Report,
) -> tuple[object, str] | None:
    """Parse and check one wig. Returns (wig, content_hash) when usable."""
    wf = mods["wig_format"]
    wfit = mods["wig_fitting"]
    fsign = mods["fitting_signing"]

    raw_bytes = len(text.encode("utf-8"))
    if raw_bytes > wf.MAX_WIG_BYTES:
        report.fail(
            rel_path,
            f"file is {raw_bytes} bytes, over the "
            f"{wf.MAX_WIG_BYTES} byte cap",
        )
        return None

    result = wf.parse_wig(text)
    if not result.ok or result.wig is None:
        for err in result.errors:
            report.fail(rel_path, err)
        return None

    wig = result.wig
    content_hash = wf.wig_content_hash(wig)

    view = wfit.parse_fittings(wig)
    for warning in view.warnings:
        report.warn(rel_path, warning)

    if not view.fittings:
        report.fail(
            rel_path,
            "no fitting. Every wig in the shop was proven on real "
            "hardware first; see CONTRIBUTING.md",
        )

    seen_handles: dict[str, list[str]] = defaultdict(list)
    seen_accounts: dict[str, list[str]] = defaultdict(list)
    fingerprints: dict[str, set[str]] = defaultdict(set)

    for fitting in view.fittings:
        who = fitting.handle
        seen_handles[who.strip().casefold()].append(who)

        account = github_key(fitting.raw.get("github"))
        if account:
            seen_accounts[account].append(who)

        if fitting.draft:
            report.fail(
                rel_path,
                f"fitting {who!r} is a draft. HAIR strips drafts on "
                "download, so this file was hand-edited",
            )
            continue

        if not wfit.fitting_is_valid(fitting, wig):
            report.fail(
                rel_path,
                f"fitting {who!r} has content_hash "
                f"{fitting.content_hash}, but this wig hashes to "
                f"{content_hash}. The codes changed after it was "
                "fitted",
            )

        if not wfit.fitting_is_complete(fitting, wig):
            rows = {key for key, _, _ in wfit.fitting_rows(wig)}
            missing = sorted(rows - set(fitting.confirmed))
            detail = f"failed: {sorted(fitting.failed)}" if fitting.failed else ""
            if missing:
                shown = ", ".join(missing[:5])
                if len(missing) > 5:
                    shown += f" and {len(missing) - 5} more"
                detail = f"{detail + '; ' if detail else ''}unconfirmed: {shown}"
            report.fail(
                rel_path,
                f"fitting {who!r} is incomplete ({detail})",
            )

        verdict = fsign.verify_fitting(fitting.raw)
        if verdict == fsign.SIGNED_INVALID:
            report.fail(
                rel_path,
                f"fitting {who!r} carries a signature that does not "
                "verify. The record was altered after it was recorded",
            )
        elif verdict is None:
            report.warn(
                rel_path,
                f"fitting {who!r} is unsigned. Valid, just "
                "self-reported",
            )

        key = fitting.raw.get("key")
        if isinstance(key, str) and key:
            fp = fsign.key_fingerprint(key)
            if fp:
                fingerprints[fp].add(github_key(fitting.raw.get("github")) or who)

    # Same-person detection warns, it never fails the run.
    #
    # A wig arriving in a pull request must contain every fitting the
    # repo's copy already has, or the superset check refuses it. So if
    # a duplicate is already sitting in a merged wig, a contributor can
    # neither keep it (this check would fail them) nor remove it (the
    # superset check would fail them, and tell them they fitted a stale
    # copy, which is not what happened). That is a rejection nobody can
    # act on, and HAIR gives a fitter no way to delete a fitting anyway.
    #
    # The rule this follows: only fail a pull request for something the
    # person opening it can actually change. Losing a fitting is
    # actionable, so it fails. Somebody else's duplicate is not, so it
    # is surfaced for the maintainer instead. The strict version of this
    # belongs at factory promotion, which is the gate that matters and
    # which counts handles itself.
    for names in seen_handles.values():
        if len(names) > 1:
            report.warn(
                rel_path,
                f"handle {names[0]!r} appears on {len(names)} fittings. "
                "A person refitting should replace their own entry "
                "rather than add a second one, so this is worth a look",
            )

    for account, names in seen_accounts.items():
        if len(names) > 1:
            shown = ", ".join(repr(n) for n in sorted(set(names)))
            report.warn(
                rel_path,
                f"fittings {shown} all give the GitHub handle "
                f"{account!r}, so they look like one person under "
                "different names. Not a failure, but they should not "
                "count as independent proof at promotion",
            )

    for fp, accounts in fingerprints.items():
        if len(accounts) > 1:
            report.warn(
                rel_path,
                f"fittings by {sorted(accounts)} share signing key "
                f"{fp}, so they came from one install. Not a failure, "
                "worth a look before this counts as independent proof",
            )

    if brand_folder == UNBRANDED:
        values = []
        for key in (wig.identifiers or {}):
            values.extend(wf.identifier_values(wig.identifiers, key))
        if not values:
            report.fail(
                rel_path,
                "wigs in unbranded/ must carry at least one entry in "
                "identifiers (fcc_id, upc or asin) so the hardware "
                "stays findable",
            )

    if wig.brand and brand_folder and brand_folder != UNBRANDED:
        squashed = re.sub(r"[^a-z0-9]+", "", wig.brand.lower())
        folder_squashed = brand_folder.replace("-", "")
        if squashed != folder_squashed:
            report.warn(
                rel_path,
                f'brand field is "{wig.brand}" but the folder is '
                f"{brand_folder}/. Worth confirming that is deliberate",
            )

    if not wig.kind:
        report.warn(
            rel_path,
            "no kind set. Kind is what people search for when wigs are "
            "shared, and the factory uses it for the wrapper platform",
        )

    return wig, content_hash


def check_against_base(
    rel_path: str, text: str, base_ref: str, mods, report: Report
) -> None:
    """The two rules that only exist relative to what is already merged.

    Signals are immutable once merged, because every fitting is bound to
    a hash of exactly those signals. And an incoming file must carry
    every fitting the repo's copy already has: a contributor who fitted
    a stale download produces a clean diff that silently deletes
    somebody else's work, and git will not warn about it.
    """
    wf = mods["wig_format"]
    wfit = mods["wig_fitting"]

    previous = git_show(base_ref, rel_path)
    if previous is None:
        return

    old = wf.parse_wig(previous)
    if not old.ok or old.wig is None:
        report.warn(
            rel_path,
            f"the copy at {base_ref} does not parse, so the "
            "signals-unchanged and fittings-superset checks were "
            "skipped",
        )
        return

    new = wf.parse_wig(text)
    if not new.ok or new.wig is None:
        return

    old_hash = wf.wig_content_hash(old.wig)
    new_hash = wf.wig_content_hash(new.wig)
    if old_hash != new_hash:
        report.fail(
            rel_path,
            "the codes in this wig changed. Once a wig is merged its "
            "signals are fixed, because every existing fitting is "
            "bound to a hash of exactly those signals. Corrections "
            "arrive as a new file with a note about what changed "
            f"(was {old_hash}, now {new_hash})",
        )

    old_ids = {
        fitting_identity(f.raw) for f in wfit.parse_fittings(old.wig).fittings
    }
    new_ids = {
        fitting_identity(f.raw) for f in wfit.parse_fittings(new.wig).fittings
    }
    lost = old_ids - new_ids
    if lost:
        who = ", ".join(sorted(handle for handle, _ in lost))
        report.fail(
            rel_path,
            f"this file is missing fittings that are already here "
            f"({who}). You fitted an older copy of the wig. Download "
            "the current file from this repo, drop it on the Closet, "
            "fit that, and open the PR from it. Nothing is wrong with "
            "your fitting; it just needs to ride alongside the others "
            "instead of replacing them",
        )


def discover(root: Path) -> list[str]:
    """Every wig in the repo, as repo-relative posix paths."""
    wigs_root = root / WIGS_DIR
    if not wigs_root.is_dir():
        return []
    return sorted(
        str(p.relative_to(root).as_posix())
        for p in wigs_root.rglob(f"*{WIG_SUFFIX}")
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate wigs against HAIR's format rules."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="wig files to check; default is every wig in wigs/",
    )
    parser.add_argument(
        "--hair-src",
        required=True,
        help="root of a HAIR checkout (the directory holding "
        "custom_components/)",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="git ref to compare against for the signals-unchanged and "
        "fittings-superset checks",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="repository root (default: current directory)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    mods = load_hair(args.hair_src)
    report = Report()

    targets = args.files or discover(root)
    if not targets:
        print("No wigs to check yet.")
        return 0

    hashes: dict[str, list[str]] = defaultdict(list)

    for rel_path in targets:
        rel_path = Path(rel_path).as_posix()
        full = root / rel_path
        if not full.exists():
            # A deletion in the diff. Nothing to validate.
            continue
        if not rel_path.endswith(WIG_SUFFIX):
            continue

        report.checked += 1
        text = full.read_text(encoding="utf-8")

        brand_folder = check_path_shape(rel_path, report)
        checked = check_wig(rel_path, text, brand_folder, mods, report)
        if checked is not None:
            _, content_hash = checked
            hashes[content_hash].append(rel_path)

        if args.base_ref:
            check_against_base(rel_path, text, args.base_ref, mods, report)

    # A duplicate is only ever the incoming file's problem. On a diff
    # run the failure is reported against the wig being added, never
    # against the one already merged, so a contributor is not shown an
    # error on a file they did not touch.
    submitted = {Path(f).as_posix() for f in args.files} if args.files else None

    if submitted is not None:
        for rel_path in discover(root):
            if rel_path in submitted:
                continue
            full = root / rel_path
            if not full.exists():
                continue
            result = mods["wig_format"].parse_wig(
                full.read_text(encoding="utf-8")
            )
            if result.ok and result.wig is not None:
                digest = mods["wig_format"].wig_content_hash(result.wig)
                if digest in hashes:
                    hashes[digest].append(rel_path)

    for digest, paths in hashes.items():
        if len(paths) < 2:
            continue
        # Whom to blame: the submitted files on a diff run, everyone
        # otherwise (a full sweep has no incoming file to single out).
        blamed = [p for p in paths if submitted is None or p in submitted]
        for path in blamed:
            others = [p for p in paths if p != path]
            report.fail(
                path,
                f"identical codes to {', '.join(others)} ({digest}). "
                "The same remote is already here. Add your fitting to "
                "that file instead of adding a second copy: download "
                "it, drop it on the Closet, fit it, and open the PR "
                "replacing that file",
            )

    return emit(report)


def emit(report: Report) -> int:
    """Print the outcome, and annotate the PR when running in Actions."""
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"

    for path in sorted(report.warnings):
        for message in report.warnings[path]:
            if in_actions:
                print(f"::warning file={path}::{message}")
            else:
                print(f"WARN  {path}: {message}")

    for path in sorted(report.failures):
        for message in report.failures[path]:
            if in_actions:
                print(f"::error file={path}::{message}")
            else:
                print(f"FAIL  {path}: {message}")

    total_failures = sum(len(v) for v in report.failures.values())
    total_warnings = sum(len(v) for v in report.warnings.values())

    print()
    if report.ok:
        print(
            f"{report.checked} wig(s) checked, all good"
            + (f", {total_warnings} warning(s)" if total_warnings else "")
        )
        return 0

    print(
        f"{report.checked} wig(s) checked, {total_failures} problem(s) "
        f"in {len(report.failures)} file(s)"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

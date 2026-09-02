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
``--base-ref`` names a git ref, also runs the checks that only mean
anything against what is already merged: what a changed row cost in
orphaned claims, that no fitting went missing, and the ancestry walk
that tells a supersession from a stale attestation.

With no FILE arguments it validates every wig in ``wigs/``.

Exit code is 0 when nothing failed, 1 otherwise. Warnings and notes
never fail the run; they are there for a human to read.

The shop's shelf holds current descriptions of devices, wholly proven.
Three things follow, and most of this file is one of them:

- **Perfect fits only.** A wig lands when at least one person has
  claimed every row of it worked on their own hardware. Wig-level, not
  bundle-level: an honest partial attestation may ride alongside, it
  just cannot open the door.
- **Identity is the signing key.** One person, one current word. A
  re-fit from the same install replaces that person's earlier bundle
  rather than stacking a duplicate, so a legitimate re-attestation PR
  shows one bundle removed and one added carrying the same key.
- **Content changes arrive as supersession.** A changed wig is a new
  wig with a new id that names its ancestor in ``supersedes``. The old
  file leaves the shelf and its ledger retires with it.
"""

from __future__ import annotations

import argparse
import hashlib
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

# HAIR composes a download name from the wig's own fields and appends
# the fitting tier, hyphenated, so the file drops into the shop with no
# rename. The suffixes are listed here ONLY so the docs and the tests
# can name them. Nothing in this file reads a tier from a filename: a
# name that could promote a file by being edited would defeat the point
# of signed per-row claims. Claims are the evidence, always.
TIER_SUFFIXES = ("-perfect-fit", "-fitted")


@dataclass
class Report:
    """Everything one run found, grouped by the file it came from.

    Three levels. Failures block. Warnings are for a human to weigh.
    Notes are the deterministic readouts a reviewing agent works from:
    what a supersession actually changed, who re-attested. They carry no
    judgement at all, which is the point -- the reviewer spends its
    judgement on whether the story fits, never on re-deriving the
    comparison.
    """

    failures: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    warnings: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    notes: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    checked: int = 0

    def fail(self, path: str, message: str) -> None:
        self.failures[path].append(message)

    def warn(self, path: str, message: str) -> None:
        self.warnings[path].append(message)

    def note(self, path: str, message: str) -> None:
        self.notes[path].append(message)

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
    # Order matters: each module is executed as it is registered, so a
    # dependency has to be in place before whatever imports it.
    # ``decoders`` is a package rather than a module, and wig_comb
    # imports from it.
    for name in (
        "const",
        "decoders",
        "pronto_validator",
        "field_readers",
        "wig_format",
        "wig_climate",
        "wig_fitting",
        "fitting_signing",
        "wig_comb",
    ):
        target = hair_dir / name
        if target.is_dir():
            package = types.ModuleType(f"hairfmt.{name}")
            package.__path__ = [str(target)]
            sys.modules[f"hairfmt.{name}"] = package
            spec = importlib.util.spec_from_file_location(
                f"hairfmt.{name}",
                target / "__init__.py",
                submodule_search_locations=[str(target)],
            )
        else:
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


def git_list_wigs(ref: str) -> list[str]:
    """Every wig on the shelf at ``ref``, as repo-relative posix paths.

    The ancestry walk needs the WHOLE shelf, not the file in front of
    it. A supersession pairs by ``wig_id`` rather than by path, so the
    successor to a wig whose kind or model changed arrives at a name
    nothing in the diff connects to its ancestor.
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", WIGS_DIR],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return sorted(
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith(WIG_SUFFIX)
    )


def github_key(value: object) -> str | None:
    """The canonical form of a GitHub handle, for comparison only.

    People type this field by hand, so the same account arrives as
    ``dab``, ``@dab``, ``DAB`` and ``github.com/dab``.

    This never rewrites a file. Bundles are signed over their own
    contents, so normalizing ``@dab`` to ``dab`` on disk would break the
    signature. The canonical form exists to compare with, not to store.

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
    # account typed plainly.
    for sep in ("/", "?", "#"):
        text = text.split(sep, 1)[0]
    return text.strip().casefold() or None


def bundle_identity(bundle) -> str:
    """Who made this bundle. ONE key, and it is the signing key.

    Ruled on HAIR's bench 2026-08-06 and shipped in 0.9.7: one person,
    one current word. A fitter re-attesting an unchanged wig from the
    same install REPLACES their earlier bundle rather than appending a
    second, and "the same install" means the same ed25519 key. The typed
    handle is display prose.

    This replaced a generous set-of-aliases match that compared by
    intersection over key, GitHub account and display name. That was
    written to protect against a false "you deleted somebody's fitting"
    accusation, and it over-corrected into a hole that the shop's own
    corpus demonstrates: the Sanmli wig carries two bundles from two
    installs that both typed ``DAB-LABS``, so deleting either one left
    the other satisfying its identity and the deletion went unreported.

    Keys close that hole without reopening the false positive, because
    the case the old code feared no longer exists. Somebody who
    reinstalls Home Assistant signs with a new key, so current HAIR
    appends their new bundle beside the old one instead of replacing it,
    and both are present in the file they upload. Nothing goes missing,
    so nothing gets accused.

    Unsigned bundles fall back to the GitHub account, then the display
    name, then a digest of the rows they claim. The last is a poor
    identity and is meant to be: an unsigned, unnamed, accountless
    bundle has told us nothing to recognise it by, and matching it on
    its own content at least makes its disappearance visible.
    """
    if bundle.key and bundle.key.strip():
        return f"key:{bundle.key.strip()}"
    account = github_key(bundle.github)
    if account:
        return f"gh:{account}"
    if bundle.handle and bundle.handle.strip():
        return f"name:{bundle.handle.strip().casefold()}"
    rows = ",".join(sorted(f"{r.digest}:{r.verdict}" for r in bundle.rows))
    return f"rows:{hashlib.sha256(rows.encode('utf-8')).hexdigest()[:16]}"


def who(bundle) -> str:
    """A bundle's name for a human, never for matching."""
    return bundle.handle or bundle.github or "(unnamed)"


def matrix_checklist_digests(wig, mods) -> set[str] | None:
    """The dimension checklist a lattice implies, as row digests.

    A matrix has thousands of cells and nobody presses thousands of
    buttons, so a checklist SAMPLES it: every mode, every fan speed,
    every swing, the ends of the temperature range, the power codes.
    HAIR derives that sample deterministically from the lattice, and
    this imports the same function rather than guessing at the shape.

    The shop has to derive it because ``bundle_is_complete`` cannot.
    As shipped in 0.9.7 it asks only "non-empty, and every row worked",
    which never re-derives what the lattice implies -- so a bundle that
    simply omits a dimension row reads complete, and a ONE-ROW bundle
    over a sixteen-cell lattice reads complete. Silence is not a claim.
    Verified against the shipped code on 2026-08-08; HAIR's own fix
    lands in the perfect-or-nothing round, but files minted by 0.9.7
    installs are already in the wild, so the shop applies the check
    itself rather than trusting the answer it is given.

    Returns None when the checklist cannot be derived, which is a
    different thing from an empty one and is never treated as passing.
    """
    if wig.climate is None:
        return None
    wf = mods["wig_format"]
    wc = mods["wig_climate"]
    try:
        items = wc.dimension_checklist(wig.climate)
    except Exception:  # a lattice shape HAIR's derivation cannot walk
        return None
    return {wf.row_digest(item.pronto, 0, False) for item in items}


def bundle_is_perfect(
    bundle, wig, mods, digests=None, expected=None
) -> bool:
    """Did this one bundle prove the whole wig? THE gate, in one place.

    Flat wigs delegate to HAIR's ``bundle_is_complete``, so the shop and
    the Closet cannot disagree. Matrix wigs add two conditions HAIR does
    not check: the bundle must pin the lattice this file carries, and
    its worked claims must cover the checklist that lattice implies.

    One function because two callers used to answer this separately and
    the index quietly disagreed with the validator about matrix wigs.
    """
    wf = mods["wig_format"]
    wfit = mods["wig_fitting"]

    if wig.climate is None:
        return wfit.bundle_is_complete(bundle, wig, digests)

    if not bundle.cells_hash:
        return False
    if bundle.cells_hash != wf.cells_content_hash(wig.climate):
        return False
    if expected is None:
        expected = matrix_checklist_digests(wig, mods)
    if not expected:
        return False
    worked = {
        row.digest for row in bundle.rows if row.verdict == wf.VERDICT_WORKED
    }
    return expected <= worked


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
    elif brand_folder == UNBRANDED:
        # The brand prefix exists so a file sitting in somebody's
        # Downloads carries its brand. A wig with no brand has none to
        # carry, and HAIR names its download from the wig's own fields:
        # with no brand it falls back to the slug of the wig's name, so
        # demanding an "unbranded-" prefix would send the first
        # unbranded contributor off to rename a file for no reason.
        pass
    elif not stem.startswith(f"{brand_folder}-") and stem != brand_folder:
        report.fail(
            rel_path,
            f"filename must start with the brand folder: expected "
            f"{brand_folder}-<kind>-<model>{WIG_SUFFIX}, got {filename}",
        )

    return brand_folder


def check_claims(rel_path: str, wig, mods, report: Report) -> None:
    """Everything the shop asks of a wig's attestations.

    Under hair-wig/3 a fitting is a signed bundle of per-row claims,
    each binding one row's transmit recipe by digest. Every judgment
    here is HAIR's: ``claims_of``, ``wig_row_digests``,
    ``bundle_is_complete``, ``coverage`` and ``verify_fitting`` are all
    imported, so a wig that reads perfect here reads perfect in the
    Closet.

    **The gate is perfect fits only** (owner ruling 2026-08-04), and it
    is HAIR's word used HAIR's way: ``bundle_is_complete`` is true when
    one bundle claims every current row worked. Wig-level, not
    bundle-level -- the wig must be perfect, individual bundles need
    not be, so an honest scoped attestation can ride alongside a whole
    proof without either one lying about the other.

    The shop deliberately keeps no vocabulary of its own here. An
    earlier gate admitted a wig when every row carried SOME claim and
    called that "admitted", which needed three words for three states.
    One gate needs one word, and it is already taken.
    """
    wf = mods["wig_format"]
    wfit = mods["wig_fitting"]
    fsign = mods["fitting_signing"]

    raw_entries = wig.extra.get("fittings")
    raw_entries = raw_entries if isinstance(raw_entries, list) else []

    # Legacy fittings are refused, not converted (owner ruling
    # 2026-08-03). A whole-file hash says "these bytes, all of them" and
    # carries nothing about which rows anybody proved, so minting claims
    # from one would manufacture evidence nobody gave.
    #
    # The test is the SHAPE, never the format stamp. Files exist that
    # stamp hair-wig/3 and carry old-shape fittings, so trusting the
    # major would admit exactly what this refuses.
    legacy = [e for e in raw_entries if wf.is_legacy_fitting(e)]
    if legacy:
        named = ", ".join(
            sorted(
                repr(str(e.get("handle", "?")))
                for e in legacy
                if isinstance(e, dict)
            )
        )
        report.fail(
            rel_path,
            f"{len(legacy)} fitting(s) ({named}) use the pre-claims "
            "format. They cannot be converted, because a whole-file hash "
            "does not record which rows anybody proved. Import this wig "
            "into HAIR 0.9.5 or newer, live with the device, and save it "
            "to the closet again to attest it under the claims model",
        )

    # Pair each bundle with the raw entry it came from: verify_fitting
    # checks a signature over the raw JSON, not over the parsed object.
    pairs = []
    for entry in raw_entries:
        if not wf.is_claims_bundle(entry):
            continue
        bundle = wf.parse_claims_bundle(entry)
        if bundle is not None:
            pairs.append((entry, bundle))

    if not pairs:
        # Only when there is nothing at all. A wig carrying legacy
        # entries has already been told exactly what is wrong with it,
        # and "no fitting" on a file that visibly contains one reads as
        # the tool being confused rather than the wig being wrong.
        if not legacy:
            report.fail(
                rel_path,
                "no fitting. Every wig in the shop was proven on real "
                "hardware first; see CONTRIBUTING.md",
            )
        return

    matrix = wig.climate is not None
    digests = wf.wig_row_digests(wig)
    live = set(digests)
    lattice = wf.cells_content_hash(wig.climate) if matrix else None
    expected = matrix_checklist_digests(wig, mods) if matrix else None
    best_covered = 0

    by_identity: dict[str, list[str]] = defaultdict(list)
    seen_accounts: dict[str, set[str]] = defaultdict(set)
    wont_work: dict[str, set[str]] = defaultdict(set)
    not_on_device: dict[str, set[tuple[str, str]]] = defaultdict(set)
    perfect: list[object] = []

    for entry, bundle in pairs:
        name = who(bundle)
        identity = bundle_identity(bundle)
        by_identity[identity].append(name)
        account = github_key(bundle.github)
        if account:
            seen_accounts[account].add(identity)

        # A bundle carries its own wig id inside the signed bytes, while
        # the file's is outside every digest and therefore unsigned. If
        # the two disagree, this bundle was written about a different
        # wig: the signature still verifies, because it covers the
        # bundle rather than the file it is sitting in, so nothing else
        # here would catch it. Two files sharing a code set (rebadged
        # hardware, a fork, a converted SmartIR entry) would otherwise
        # let a bundle be copied across and read as proof.
        if (bundle.wig_id or "").strip() != (wig.wig_id or "").strip():
            report.fail(
                rel_path,
                f"fitting {name!r} claims wig_id {bundle.wig_id!r}, but "
                f"this file is {wig.wig_id!r}. A bundle is signed over "
                "itself, not over the file it rides in, so a bundle "
                "moved between wigs still verifies. This one is "
                "attesting something else",
            )

        verdict = fsign.verify_fitting(entry)
        if verdict == fsign.SIGNED_INVALID:
            report.fail(
                rel_path,
                f"fitting {name!r} carries a signature that does not "
                "verify. The record was altered after it was recorded",
            )
        elif verdict is None:
            report.warn(
                rel_path,
                f"fitting {name!r} is unsigned. Valid, just self-reported",
            )

        for row in bundle.rows:
            if row.verdict == wf.VERDICT_WONT_WORK:
                wont_work[row.digest].add(identity)
            elif row.verdict == wf.VERDICT_NOT_ON_DEVICE:
                not_on_device[row.digest].add((identity, row.alias_at_claim))

        if matrix:
            # A checklist samples a lattice rather than walking it, so
            # the bundle pins the lattice it sampled AND has to cover the
            # sample. Per-row presence is not a question that can be
            # asked here: a matrix wig has no flat row digests by design.
            complete = False
            if not bundle.cells_hash:
                report.warn(
                    rel_path,
                    f"fitting {name!r} carries no cells_hash, so there is "
                    "no way to tell which lattice its checklist vouched "
                    "for",
                )
            elif bundle.cells_hash != lattice:
                # The matrix equivalent of an orphaned flat claim, and
                # treated the same way: kept, reported, never counted.
                # It cannot be a refusal, because a lattice repairs IN
                # PLACE (owner ruling 2026-08-08) and HAIR's own update
                # keeps the existing fittings when it writes the new
                # one -- so failing here would reject the repair path
                # for carrying exactly what HAIR put in the file.
                report.warn(
                    rel_path,
                    f"fitting {name!r} vouched for a different lattice "
                    f"(cells_hash {bundle.cells_hash}). The matrix has "
                    "changed since it was attested, so this checklist is "
                    "orphaned: it stays as somebody's signed statement "
                    "about a lattice this file no longer carries, and it "
                    "counts toward nothing",
                )
            elif not expected:
                report.warn(
                    rel_path,
                    f"the dimension checklist for this lattice could not "
                    f"be derived, so fitting {name!r} cannot be checked "
                    "for completeness and does not count toward the gate",
                )
            else:
                worked = {
                    row.digest
                    for row in bundle.rows
                    if row.verdict == wf.VERDICT_WORKED
                }
                covered = len(expected & worked)
                best_covered = max(best_covered, covered)
                complete = expected <= worked
        else:
            complete = wfit.bundle_is_complete(bundle, wig, digests)
            orphans = [r for r in bundle.rows if r.digest not in live]
            if orphans:
                shown = ", ".join(repr(r.alias_at_claim) for r in orphans[:5])
                more = (
                    f" and {len(orphans) - 5} more" if len(orphans) > 5 else ""
                )
                report.warn(
                    rel_path,
                    f"fitting {name!r} has {len(orphans)} orphaned "
                    f"claim(s) ({shown}{more}): rows it proved that the "
                    "wig no longer carries. Kept deliberately, since they "
                    "are somebody's signed statement about bytes that "
                    "were once here, but worth reading before merging",
                )

        if complete:
            perfect.append(bundle)

    # One bundle per key per wig, an invariant since HAIR 0.9.7. Two
    # bundles sharing a key means the submitter's HAIR predates the
    # replace rule, or the file was hand-edited. Either way the fix is
    # upstream of this repo.
    for identity, names in by_identity.items():
        if len(names) > 1 and identity.startswith("key:"):
            report.fail(
                rel_path,
                f"{len(names)} fittings ({', '.join(sorted(set(names)))}) "
                f"share one signing key. Since HAIR 0.9.7 a person "
                "re-fitting a wig replaces their own earlier bundle "
                "rather than adding a second, so one install can only "
                "have one current word on one wig. Import this file into "
                "current HAIR and save it to the closet again to collapse "
                "them, rather than editing the file by hand",
            )
        elif len(names) > 1:
            report.warn(
                rel_path,
                f"{len(names)} unsigned fittings "
                f"({', '.join(sorted(set(names)))}) "
                "cannot be told apart, because an unsigned bundle has no "
                "key to identify it by. Worth confirming they are "
                "different people",
            )

    # THE GATE. Perfect fits only: at least one person must have claimed
    # every row of this wig worked on their own hardware.
    if not perfect:
        if matrix:
            shortfall = (
                f" The dimension checklist this lattice implies has "
                f"{len(expected)} rows; the best bundle here vouched for "
                f"{best_covered}."
                if expected
                else ""
            )
            report.fail(
                rel_path,
                "no perfect fit. The shop takes a wig when one person has "
                "vouched for its whole checklist against the lattice this "
                f"file carries.{shortfall} A bundle that simply omits a "
                "checklist row reads complete to HAIR 0.9.7, so the shop "
                "re-derives the checklist from the lattice itself: "
                "silence is not a claim. Import it into HAIR, live with "
                "the device, and save it with every checklist row marked",
            )
        else:
            proven = wf.coverage(
                [b for _, b in pairs], digests
            )
            missing = [d for d in digests if d not in proven]
            aliases = [
                s.alias
                for s in wig.signals
                if wf.signal_row_digest(s) in set(missing)
            ]
            shown = ", ".join(repr(a) for a in aliases[:6])
            more = (
                f" and {len(missing) - 6} more" if len(missing) > 6 else ""
            )
            if missing:
                detail = (
                    f"{len(missing)} of {len(digests)} row(s) have nobody "
                    f"saying they worked: {shown}{more}"
                )
            else:
                # Every row is proven, but by different people. Coverage
                # is real and worth knowing; it is not a whole witness.
                detail = (
                    f"all {len(digests)} rows are proven between "
                    f"{len(pairs)} fitters, but no single one of them "
                    "covers the whole wig"
                )
            report.fail(
                rel_path,
                f"no perfect fit: {detail}. The shop takes a wig when ONE "
                "person has proven every row on their own hardware -- a "
                "file where three people each proved a third is a file "
                "nobody has watched work. Fit the remaining rows and save "
                "to the closet again. If your hardware revision does not "
                "have these buttons, do not trim them out of a shared "
                "wig: save your revision as its own wig, named for what "
                "it is",
            )

    # A second GitHub account on a different key is two people or one
    # person on two installs, and the shop cannot tell which. Not a
    # failure; it matters only where independence is being counted.
    for account, identities in seen_accounts.items():
        if len(identities) > 1:
            report.warn(
                rel_path,
                f"{len(identities)} fittings give the GitHub handle "
                f"{account!r} from different installs. Not a failure, but "
                "they should not count as independent proof at promotion",
            )

    # The reason the exclusion reasons are an enum rather than free
    # text: several people reporting wont_work on the SAME recipe is a
    # mechanical signal that the code is wrong for a hardware revision,
    # which no amount of reading prose would surface reliably. Counted
    # by key, never by handle -- two "David"s are two people when their
    # keys differ, and one person is never two.
    for digest, identities in wont_work.items():
        if len(identities) > 1:
            alias = next(
                (
                    s.alias
                    for s in wig.signals
                    if wf.signal_row_digest(s) == digest
                ),
                digest,
            )
            report.warn(
                rel_path,
                f"{len(identities)} fitters report {alias!r} does not "
                "work on their hardware. One person is a hardware "
                "revision; several is a sign the code itself is wrong",
            )

    # The other half of the diagnostic feed, and it argues the opposite
    # way. Several fitters saying a row is NOT ON their device is not a
    # bad code -- it is a fingerprint of a hardware revision that lacks
    # that button, and the answer is a revision-variant wig rather than
    # a repair. Only matrix wigs can still produce these from current
    # HAIR, whose flat checklists went green-only, but flat files minted
    # by 0.9.5 and 0.9.6 carry them and stay valid.
    for digest, seen in not_on_device.items():
        identities = {identity for identity, _ in seen}
        if len(identities) > 1:
            label = next(
                (alias for _, alias in seen if alias),
                digest,
            )
            report.warn(
                rel_path,
                f"{len(identities)} fitters say {label!r} is not on their "
                "device at all. That is the fingerprint of a hardware "
                "revision rather than a bad code, so the answer is a "
                "revision wig of its own, not a repair to this one",
            )

    # An attestation does not launder an anomalous code. A green,
    # complete bundle over a code that does not resemble the file's
    # other rows is possible and sometimes honest -- a fitter who tests
    # a comb-flagged code and finds it working signs for it, and the
    # signature is the better evidence. But claims are the EVIDENCE and
    # the comb is the reviewer's INSTRUMENT, and "it looked attested" is
    # not a reason to skip looking at the bytes.
    comb = wig.extra.get("comb")
    suspects = comb.get("suspects") if isinstance(comb, dict) else None
    if perfect and isinstance(suspects, int) and suspects > 0:
        report.warn(
            rel_path,
            f"this wig is perfectly fitted AND its comb receipt lists "
            f"{suspects} suspect(s). Both can be true: somebody may have "
            "tested a flagged code and found it working. Read the receipt "
            "before merging anyway -- an attestation does not launder a "
            "code that does not resemble its neighbours",
        )


#: The receipt version the pinned HAIR writes. A receipt older than
#: this cannot be expected to know about checks that shipped after it,
#: so a disagreement with one is housekeeping rather than a discrepancy.
RECEIPT_VERSION = 2


def _today() -> str:
    """The date a freshly derived receipt is stamped with."""
    from datetime import date

    return date.today().isoformat()


def stored_receipt(wig) -> dict | None:
    """The comb receipt the FILE claims, if it carries a readable one."""
    comb = wig.extra.get("comb")
    return comb if isinstance(comb, dict) else None


def live_comb(wig, mods):
    """Comb this wig here, now, with the pinned HAIR.

    The shop used to read ``comb.suspects`` out of the file and believe
    it. But a receipt is written by whoever combed, and the file is text
    a contributor can edit, so a wig can arrive carrying a clean bill
    nobody ever gave it. The first matrix the shop received stated zero
    suspects and combs to fifty-two.

    So the stored receipt is a HINT about what the fitter saw, and this
    is the evidence. Returns ``None`` only if the pinned HAIR has no
    comb at all, which cannot happen at the current pin and is handled
    so that a rollback degrades instead of crashing.
    """
    wcomb = mods.get("wig_comb")
    if wcomb is None:
        return None
    return wcomb.comb_wig(wig)


def check_comb(rel_path: str, wig, mods, report: Report):
    """Comb the wig and say what came out.

    A fitting attests the dimension checklist, which on a matrix wig is
    fourteen or so rows out of a lattice of hundreds. Codes outside the
    checklist can be wrong and no fitting will ever say so: the shop's
    first matrix carried fifty-two cells sending their neighbour's
    temperature, none of them in its checklist, under a complete signed
    fitting that was honestly earned. Combing is the only instrument
    that can see them.

    Warnings, never failures. Combing reports and never changes a code,
    a suspect is a finding a human should look at, and a wig with three
    bad cells out of a hundred and eighty is still worth having. This
    puts it in front of the maintainer and stops there.
    """
    findings = live_comb(wig, mods)
    stored = stored_receipt(wig)

    if findings is None:
        # The pinned HAIR predates combing. Fall back to the receipt,
        # which is all the shop had before the 0.14.0 pin.
        if stored is None:
            report.warn(
                rel_path,
                "no comb receipt, and the pinned HAIR cannot comb. "
                "Nothing has checked this wig's codes against each other",
            )
        return None

    receipt = findings.to_receipt(_today())
    suspects = receipt.get("suspects") or 0
    counts = receipt.get("counts") or {}

    _report_receipt_drift(rel_path, stored, suspects, report)
    _report_coverage(rel_path, wig, receipt, report)

    if suspects == 0:
        return findings

    detail = "; ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    report.warn(
        rel_path,
        f"combing found {suspects} suspect(s)"
        + (f" ({detail})" if detail else "")
        + ". Worth reading before merging",
    )
    _report_findings(rel_path, findings, report)
    return findings


def _report_receipt_drift(
    rel_path: str, stored: dict | None, suspects: int, report: Report
) -> None:
    """What the file SAID, against what combing it says now.

    A disagreement is its own finding. It means the receipt travelled
    without the codes it describes, or somebody edited one of the two.
    Either way the receipt is not evidence about this file.
    """
    if stored is None:
        report.warn(
            rel_path,
            "no comb receipt in this file. The shop combed it here "
            "instead, so the findings above stand, but nothing travels "
            "with the file: import it into HAIR and share it again and "
            "the receipt rides along for everyone downstream",
        )
        return

    claimed = stored.get("suspects")
    if not isinstance(claimed, int) or claimed == suspects:
        return

    # A receipt written by an older comb is not a lie, it is an older
    # opinion: the checks that found these had not been written when it
    # was stamped. Telling the two apart matters, because one is
    # housekeeping and the other is a file whose paperwork does not
    # describe its own codes.
    version = stored.get("version")
    if isinstance(version, int) and version < RECEIPT_VERSION:
        report.note(
            rel_path,
            f"the receipt in this file is version {version} and claims "
            f"{claimed} suspect(s); combing it with the pinned HAIR "
            f"finds {suspects}. The receipt is not wrong, it is older "
            "than the checks that caught these. Re-comb in HAIR and the "
            "file will carry the newer answer",
        )
        return

    report.warn(
        rel_path,
        f"the comb receipt in this file claims {claimed} suspect(s); "
        f"combing it here finds {suspects}, and the receipt is current "
        "enough to have known. It describes a version of these codes "
        "that is not the version in this file, so it is being ignored "
        "and the findings below were derived fresh",
    )


def _report_coverage(
    rel_path: str, wig, receipt: dict, report: Report
) -> None:
    """Say what was NOT checked, where that silence is load-bearing.

    Only on a matrix. On a flat remote the check that matters is frame
    self-consistency, and that runs on anything without needing a map,
    so a missing field map costs a flat wig nothing worth a line.

    On a lattice it costs everything. A dimension checklist samples
    fourteen cells out of hundreds, and where no map covers the protocol
    the field check cannot run either, which leaves the rest of the
    lattice attested by nobody and examined by nothing. That is exactly
    what fifty-two bad cells looked like before the pin, so an unchecked
    lattice must not read like a clean one.
    """
    if wig.climate is None:
        return

    coverage = receipt.get("coverage")
    if not isinstance(coverage, dict):
        return

    protocol = coverage.get("protocol")
    if isinstance(protocol, dict):
        codes = protocol.get("codes") or 0
        if protocol.get("id") is None:
            report.warn(
                rel_path,
                f"no field map covers this lattice's protocol, so none "
                f"of its {codes} cell(s) were read against their labels. "
                "The fitting attests fourteen or so of them and nothing "
                "has looked at the rest. Unchecked is not the same as "
                "clean",
            )
        else:
            readable = protocol.get("readable") or 0
            report.note(
                rel_path,
                f"protocol read as {protocol['id']}: {readable} of "
                f"{codes} cell(s) decoded",
            )

    fields = coverage.get("fields")
    if isinstance(fields, dict):
        unchecked = sorted(
            name
            for name, block in fields.items()
            if isinstance(block, dict) and not block.get("checked")
        )
        if unchecked:
            report.note(
                rel_path,
                "field(s) this lattice was not judged on: "
                + ", ".join(unchecked)
                + ". A field the map does not yet ratify is left alone "
                "rather than guessed at",
            )


def _report_findings(rel_path: str, findings, report: Report) -> None:
    """The findings themselves, grouped so a lattice does not flood."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for finding in findings.findings:
        for key in finding.keys:
            grouped[finding.check].append(key)

    for check, keys in sorted(grouped.items()):
        shown = ", ".join(sorted(keys)[:8])
        if len(keys) > 8:
            shown += f"; and {len(keys) - 8} more"
        report.note(rel_path, f"{check}: {shown}")

    # The one class worth naming on its own. A malformed frame is
    # ignored by the device, which is annoying but obvious. A code that
    # says something other than its label makes the device answer and
    # look like it worked while landing on the wrong state, so nobody
    # notices until they wonder why the room is a degree off.
    dangerous = [
        f
        for f in findings.findings
        if f.check in ("duplicated-neighbour", "field-mismatch")
    ]
    if dangerous:
        report.warn(
            rel_path,
            f"{len(dangerous)} code(s) answer the device and land on the "
            "wrong state. A dimension checklist does not sample these, "
            "so no fitting could have caught them and the fitter is not "
            "at fault. HAIR 0.14.0 can repair them on the device",
        )


#: Where HAIR writes a repair record, inside the cell's or signal's own
#: unknown-keys bag so it rides the file with no format change.
REPAIR_KEY = "hair_repair"

#: How honest a repaired code is about the room it was proved in.
#: ``air-tested`` means somebody fired this code at the device.
#: ``rule-derived`` means it was written under a ratified field rule
#: whose sample WAS fired, and the record names the cells that were.
#: ``accepted`` means a person said yes to the bytes and nothing was
#: transmitted at all.
TIER_AIR_TESTED = "air-tested"
TIER_RULE_DERIVED = "rule-derived"
TIER_ACCEPTED = "accepted"


def repair_records(wig, mods) -> list[tuple[str, dict]]:
    """Every repair record in this wig, paired with what it repaired.

    A repaired wig is a file HAIR mints beside the original once
    somebody works the Needs attention list, and it is a shape the shop
    had never seen before 0.14.0. The records ride in cell and signal
    extras by the unknown-keys contract, so an older shop reads straight
    past them, which is exactly why they have to be read here on purpose.
    """
    found: list[tuple[str, dict]] = []

    for signal in wig.signals or []:
        record = (signal.extra or {}).get(REPAIR_KEY)
        if isinstance(record, dict):
            found.append((signal.alias, record))

    if wig.climate is not None:
        # HAIR's own key function, not a reimplementation of it. A cell
        # coordinate built here would read "cool/auto/16.0" against the
        # comb's "cool/auto/16", because temp is a float, and the
        # cross-check below would silently match nothing forever.
        cell_key = mods["wig_format"].cell_key
        for cell in wig.climate.cells:
            record = (cell.extra or {}).get(REPAIR_KEY)
            if isinstance(record, dict):
                found.append((cell_key(cell), record))

    return found


def check_repairs(rel_path: str, wig, mods, combed, report: Report) -> None:
    """Say what this file CLAIMS was mended, and check the claim.

    Ruled by the owner 2026-09-02: **accept and report.** A repair is
    not held to a standard the shelf has never applied to anything else.
    A lattice already carries hundreds of cells nobody pressed, because
    that is what a dimension checklist is, and a repair run proves a
    sample on air and names it. Refusing the second while accepting the
    first would be inconsistent rather than careful.

    But note the word CLAIMS. ``canonical_cells_json`` builds the
    matrix hash from mode, fan, swing, temp and pronto only, so cell
    extras are outside it on purpose -- two files differing by nothing
    but annotations must hash alike or fittings would stop
    accumulating. The consequence is that **a repair record is covered
    by no signature at all.** It can be stamped onto any wig, or
    stripped off one, and every gate here still passes.

    So this reads exactly like the comb receipt does: as the file's own
    word about itself, never as evidence. What the shop CAN do is hold
    the claim against the codes, because a wig that says it mended
    fifty-two cells and still combs to fifty-two mended nothing.
    """
    records = repair_records(wig, mods)
    if not records:
        return

    tiers: dict[str, int] = defaultdict(int)
    runs: set[str] = set()
    overridden: list[str] = []
    proved_on_air: set[str] = set()
    claimed_keys: set[str] = set()

    for key, record in records:
        claimed_keys.add(key)
        tiers[str(record.get("tier") or "unstated")] += 1
        run = record.get("run")
        if isinstance(run, str):
            runs.add(run)
        if record.get("reading_disagreed"):
            overridden.append(key)
        for cell in record.get("tested_cells") or []:
            if isinstance(cell, str):
                proved_on_air.add(cell)

    spread = ", ".join(f"{n} {tier}" for tier, n in sorted(tiers.items()))
    in_runs = f" across {len(runs)} repair run(s)" if runs else ""
    report.note(
        rel_path,
        f"this file states that {len(records)} of its code(s) were "
        f"repaired in HAIR{in_runs}: {spread}. Repair records ride "
        "outside the matrix hash, so nothing signs them and they are "
        "the file's word rather than proof",
    )

    _check_repairs_took(rel_path, claimed_keys, combed, report)

    if proved_on_air:
        shown = ", ".join(sorted(proved_on_air)[:6])
        if len(proved_on_air) > 6:
            shown += f"; and {len(proved_on_air) - 6} more"
        report.note(
            rel_path,
            f"the rule-derived records name {len(proved_on_air)} cell(s) "
            f"as proved on air behind them: {shown}",
        )

    unstated = tiers.get("unstated", 0)
    if unstated:
        report.warn(
            rel_path,
            f"{unstated} repair record(s) carry no tier, so they do not "
            "even claim whether anything was transmitted. HAIR writes a "
            "tier on every repair it makes, so these came from "
            "somewhere else",
        )

    if tiers.get(TIER_ACCEPTED):
        report.note(
            rel_path,
            f"{tiers[TIER_ACCEPTED]} of these are accepted without a "
            "send: the one-at-a-time path, where a person read the "
            "bytes and said yes and nothing was fired at the device",
        )

    # A human who overrode the reading is the most interesting line in
    # the file. It is allowed on purpose -- a remote sends what its
    # display shows, so a consistent mismatch is evidence about OUR
    # field map rather than about the person pressing the button -- and
    # repeated overrides in one protocol family are how a provisional
    # field eventually gets ratified. That only works if somebody reads
    # them, so they are surfaced rather than counted.
    if overridden:
        shown = ", ".join(sorted(overridden)[:6])
        if len(overridden) > 6:
            shown += f"; and {len(overridden) - 6} more"
        report.note(
            rel_path,
            f"{len(overridden)} repair(s) were kept after HAIR read them "
            f"as something other than their label: {shown}. Worth "
            "reading: this is how a field map learns it is wrong",
        )


def _check_repairs_took(
    rel_path: str, claimed: set[str], combed, report: Report
) -> None:
    """Hold the claim against the codes.

    The one thing about a repair the shop can check without trusting
    anybody: a cell somebody says they mended should no longer be the
    cell combing complains about. Where it still is, the record is
    decoration, whether it was written in good faith or not.
    """
    if combed is None or not claimed:
        return

    still_flagged = {
        key
        for finding in combed.findings
        for key in finding.keys
        if key in claimed
    }
    if not still_flagged:
        return

    shown = ", ".join(sorted(still_flagged)[:6])
    if len(still_flagged) > 6:
        shown += f"; and {len(still_flagged) - 6} more"
    report.warn(
        rel_path,
        f"{len(still_flagged)} code(s) carry a repair record and are "
        f"still flagged by combing: {shown}. Whatever those records "
        "say was done, the codes did not change",
    )


def check_wig(
    rel_path: str,
    text: str,
    brand_folder: str | None,
    mods,
    report: Report,
) -> tuple[object, str] | None:
    """Parse and check one wig. Returns (wig, content_hash) when usable."""
    wf = mods["wig_format"]

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

    if not wig.wig_id:
        # Every wig HAIR writes has carried one since 0.9.5, and claims
        # bind to it. A file without one was hand-made or came through a
        # tool that does not mint identities, and nothing downstream --
        # the ancestry walk, the bundle cross-check -- can place it.
        report.fail(
            rel_path,
            "no wig_id. Every wig HAIR has written since 0.9.5 carries "
            "one, claims bind to it, and supersession is tracked by it. "
            "Import this file into HAIR and save it to the closet to "
            "mint one",
        )

    check_claims(rel_path, wig, mods, report)

    combed = check_comb(rel_path, wig, mods, report)

    check_repairs(rel_path, wig, mods, combed, report)

    # Orphaned claims are kept on purpose: they are somebody's signed
    # statement about bytes that were once here, and deleting them
    # destroys evidence. Nothing prunes them, though, and the format has
    # a size cap, so a wig repaired often enough across a large lattice
    # could drift toward it carrying mostly dead claims. Surfaced long
    # before it can fail.
    if raw_bytes > wf.MAX_WIG_BYTES // 2:
        report.warn(
            rel_path,
            f"file is {raw_bytes} bytes, over half the "
            f"{wf.MAX_WIG_BYTES} byte cap. Retired claims are never "
            "pruned, so a much-repaired wig grows; worth watching",
        )

    if brand_folder == UNBRANDED:
        values = []
        for key in wig.identifiers or {}:
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
            "shared, the factory uses it for the wrapper platform, and "
            "HAIR composes the download name from it",
        )

    return wig, content_hash


# ---------------------------------------------------------------------------
# What only means anything against what is already merged
# ---------------------------------------------------------------------------


def row_map(wig, wf) -> dict[str, str]:
    """Alias to row digest, in file order."""
    return {s.alias: wf.signal_row_digest(s) for s in wig.signals}


def overlap(old_wig, new_wig, wf) -> dict:
    """What changed between two versions of a wig's rows.

    Pairing is digest first, then alias, which is the rule the format
    asks for: a claim matches a row by digest alone, so a rename with an
    unchanged digest costs nothing, while duplicate-payload rows (real
    devices ship them: Power and Toggle sending the same bytes) must not
    cross-match on the digest alone when deciding what a human should
    read.
    """
    old_rows = row_map(old_wig, wf)
    new_rows = row_map(new_wig, wf)
    old_digests = set(old_rows.values())
    new_digests = set(new_rows.values())

    identical = old_digests & new_digests
    shared_alias = set(old_rows) & set(new_rows)

    changed = sorted(a for a in shared_alias if old_rows[a] != new_rows[a])
    renamed = sorted(
        a
        for a in set(new_rows) - shared_alias
        if new_rows[a] in old_digests
    )
    added = sorted(
        a
        for a in set(new_rows) - shared_alias
        if new_rows[a] not in old_digests
    )
    removed = sorted(
        a
        for a in set(old_rows) - shared_alias
        if old_rows[a] not in new_digests
    )
    return {
        "identical": len(identical),
        "total": len(new_rows),
        "was": len(old_rows),
        "changed": changed,
        "renamed": renamed,
        "added": added,
        "removed": removed,
        # Kept apart on purpose. A repaired row and a deleted row both
        # orphan whatever bound the old recipe, and they are not the
        # same act: one is the designed path back to the shelf, the
        # other is the trim-to-green move the perfect-only gate tempts.
        # Reporting them under one sentence describes somebody's repair
        # as a haircut.
        "changed_digests": {old_rows[a] for a in changed},
        "removed_digests": {old_rows[a] for a in removed},
    }


def overlap_line(ov: dict) -> str:
    """The deterministic readout a reviewing agent works from."""

    def listed(key: str) -> str:
        values = ov[key]
        return ", ".join(repr(v) for v in values) if values else "none"

    return (
        f"{ov['identical']} of {ov['total']} rows byte-identical "
        f"(was {ov['was']}); added: {listed('added')}; "
        f"changed: {listed('changed')}; removed: {listed('removed')}; "
        f"renamed: {listed('renamed')}"
    )


def claims_cost(old_wig, gone: set[str], wf) -> dict[str, dict[str, str]]:
    """Whose proof each departing digest carries away.

    Keyed by identity rather than by display name, because the trim rule
    turns on WHOSE proof is being discarded: your own earlier word is
    yours to withdraw, somebody else's is not.
    """
    cost: dict[str, dict[str, str]] = defaultdict(dict)
    for bundle in wf.claims_of(old_wig):
        for row in bundle.rows:
            if row.verdict == wf.VERDICT_WORKED and row.digest in gone:
                cost[row.digest][bundle_identity(bundle)] = who(bundle)
    return cost


def named(cost: dict[str, dict[str, str]]) -> str:
    """The people behind a claims_cost map, for a message."""
    return ", ".join(
        sorted({n for group in cost.values() for n in group.values()})
    )


def lattice_line(old_matrix, new_matrix, mods) -> str:
    """Which cells moved, by coordinate. The readout for a matrix repair."""
    wf = mods["wig_format"]

    def cells(matrix) -> dict[str, str]:
        if matrix is None:
            return {}
        return {
            wf.cell_key(c): wf.row_digest(c.pronto, 0, False)
            for c in matrix.cells
        }

    was, now = cells(old_matrix), cells(new_matrix)
    changed = sorted(k for k in set(was) & set(now) if was[k] != now[k])
    added = sorted(set(now) - set(was))
    removed = sorted(set(was) - set(now))

    def listed(values: list[str]) -> str:
        if not values:
            return "none"
        shown = ", ".join(values[:8])
        more = f"; and {len(values) - 8} more" if len(values) > 8 else ""
        return shown + more

    same = len(set(was) & set(now)) - len(changed)
    return (
        f"{same} of {len(now)} cells byte-identical (was {len(was)}); "
        f"added: {listed(added)}; changed: {listed(changed)}; "
        f"removed: {listed(removed)}"
    )


def check_against_base(
    rel_path: str, text: str, base_ref: str, mods, report: Report
) -> None:
    """The rules that hold while a wig stays the SAME wig.

    Same path, same ``wig_id``: proof accumulating on a stable
    description. Exactly one thing legitimately changes here, and it is
    the ledger growing.

    What fails: a file must carry every bundle the repo's copy already
    has. Somebody who attests a stale download produces a perfectly
    clean diff that deletes another person's signed work, and git will
    not say a word about it.

    What does NOT fail here: a content change. Under the supersession
    policy a changed description is a new wig with a new id, so a
    content change at an unchanged id is not repair-in-place, it is a
    hand-edited file. It is reported loudly and the ancestry walk in
    ``check_shelf`` owns the verdict.

    A wig whose id CHANGED at this path is a supersession and this
    function returns immediately: the ancestor's ledger retires with the
    ancestor, so a superset check across that boundary would refuse the
    one PR shape the policy is built around.
    """
    wf = mods["wig_format"]

    previous = git_show(base_ref, rel_path)
    if previous is None:
        return

    old = wf.parse_wig(previous)
    if not old.ok or old.wig is None:
        report.warn(
            rel_path,
            f"the copy at {base_ref} does not parse, so the fittings "
            "superset and overlap checks were skipped",
        )
        return

    new = wf.parse_wig(text)
    if not new.ok or new.wig is None:
        return

    if (old.wig.wig_id or "") != (new.wig.wig_id or ""):
        # Supersession. Handled by the ancestry walk, which pairs by id
        # across the whole shelf rather than by path.
        return

    old_bundles = wf.claims_of(old.wig)
    new_bundles = wf.claims_of(new.wig)

    # Legacy entries are invisible here, and that is the whole reason
    # this needs no special case. They are refused outright by
    # check_claims, ``claims_of`` skips them, and so a wig moving off the
    # old model drops entries this check never counted. No exception
    # window to bound, and no standing licence to delete a fitting by
    # relabelling it.
    old_by_identity = {bundle_identity(b): b for b in old_bundles}
    new_by_identity = {bundle_identity(b): b for b in new_bundles}

    lost = [
        b
        for identity, b in old_by_identity.items()
        if identity not in new_by_identity
    ]
    if lost:
        names = ", ".join(sorted(who(b) for b in lost))
        report.fail(
            rel_path,
            f"this file is missing fittings that are already here "
            f"({names}). You attested an older copy of the wig. Download "
            "the current file from this repo, import it, live with it, "
            "and save it to the closet again. Nothing is wrong with "
            "your fitting; it just needs to ride alongside the others "
            "instead of replacing them",
        )

    joined = sorted(
        who(b)
        for identity, b in new_by_identity.items()
        if identity not in old_by_identity
    )
    if joined:
        report.note(
            rel_path,
            f"fittings added: {', '.join(joined)}",
        )

    # A re-attestation. Since HAIR 0.9.7 one install has one current
    # word on one wig, so a person proving a wig they already proved
    # REPLACES their earlier bundle. In a diff that reads as one bundle
    # removed and one added carrying the same key, which is the
    # legitimate additive shape and must never be read as a trimmed
    # ledger.
    refit = sorted(
        who(new_by_identity[identity])
        for identity in old_by_identity.keys() & new_by_identity.keys()
        if wf.claims_bundle_out(old_by_identity[identity])
        != wf.claims_bundle_out(new_by_identity[identity])
    )
    if refit:
        report.note(
            rel_path,
            f"re-attestation by {', '.join(refit)}: same signing key, "
            "earlier bundle replaced. This is the additive shape, not a "
            "trimmed ledger",
        )

    if old.wig.climate is not None or new.wig.climate is not None:
        old_cells = (
            wf.cells_content_hash(old.wig.climate)
            if old.wig.climate is not None
            else None
        )
        new_cells = (
            wf.cells_content_hash(new.wig.climate)
            if new.wig.climate is not None
            else None
        )
        if old_cells != new_cells:
            # THE MATRIX EXCEPTION (owner ruling 2026-08-08). A flat wig
            # whose codes change becomes a new wig; a matrix repairs in
            # place, keeping its id, because that is what HAIR's Update
            # route does and because the format already makes it safe.
            # Every matrix bundle pins its lattice with cells_hash, so a
            # stale attestation FAILS loudly a few lines up rather than
            # riding along looking current -- which is exactly the thing
            # flat rows cannot do, and the whole reason they are treated
            # differently.
            report.note(
                rel_path,
                "the climate lattice changed in place, which is the "
                "matrix repair path. "
                + lattice_line(old.wig.climate, new.wig.climate, mods)
                + ". Every checklist that pinned "
                f"{old_cells} is orphaned by it and counts toward nothing, "
                "so this wig needs a fresh perfect fit against the "
                "lattice it now carries",
            )
        return

    ov = overlap(old.wig, new.wig, wf)
    if not (ov["changed"] or ov["added"] or ov["removed"]):
        if ov["renamed"]:
            report.note(
                rel_path,
                "rows renamed, recipes unchanged: "
                f"{', '.join(ov['renamed'])}. "
                "No claim is affected; aliases were never in the digest",
            )
        return

    cost = claims_cost(
        old.wig, ov["changed_digests"] | ov["removed_digests"], wf
    )
    proven_away = sorted({n for g in cost.values() for n in g.values()})
    report.fail(
        rel_path,
        "the codes changed but the wig_id did not. " + overlap_line(ov)
        + (
            f". Claims by {', '.join(proven_away)} bind rows this file no "
            "longer carries"
            if proven_away
            else ""
        )
        + ". The shelf holds current descriptions, wholly proven: when a "
        "description changes it becomes a NEW wig. In HAIR, save your "
        "device as a new wig -- it stamps supersedes with this wig's id "
        "automatically -- and submit that file over this one",
    )


@dataclass
class Shelved:
    """One wig as it sits on a shelf, ready to be paired by id."""

    path: str
    wig: object

    @property
    def wig_id(self) -> str:
        return (getattr(self.wig, "wig_id", None) or "").strip()


def read_shelf(paths, reader, wf) -> list[Shelved]:
    """Parse a set of wig paths into Shelved entries, skipping junk."""
    out = []
    for path in paths:
        text = reader(path)
        if text is None:
            continue
        result = wf.parse_wig(text)
        if result.ok and result.wig is not None and result.wig.wig_id:
            out.append(Shelved(path, result.wig))
    return out


def check_shelf(
    root: Path, base_ref: str | None, mods, report: Report
) -> None:
    """The ancestry walk: supersession, variants, and stale attestations.

    KEYED ON ANCESTRY, NEVER ON FILE OPERATIONS. A same-device successor
    composes the same brand-kind-model filename, so the common
    supersession pull request is a MODIFY at one path, and a
    remove-plus-add watcher sleeps straight through it. Pairing by
    ``wig_id`` also covers the moved-filename case for free.

    Five branches, from the supersession policy, with one refinement
    that HAIR 0.9.7 forced. Since 0.9.7 every save route that mints from
    a sourced device stamps ``supersedes`` automatically, including Save
    as New, which keeps both files. So ancestry now arrives on
    essentially every sourced submission, including deliberate revision
    variants that replace nothing at all. Ancestry alone therefore
    cannot flag anything: a new file that leaves its ancestor standing
    is a variant carrying honest lineage, and only a pull request that
    actually replaces something can name the wrong ancestor.
    """
    wf = mods["wig_format"]

    head = read_shelf(
        discover(root),
        lambda p: (root / p).read_text(encoding="utf-8"),
        wf,
    )
    head_by_path = {s.path: s for s in head}

    # Id uniqueness across the shelf, always. Two files with one id are
    # one wig in two places: claims bind to the id, so a fitting on
    # either would read as proof of both. This is branch 5, and it is
    # checked whether or not there is a base to compare against.
    by_id: dict[str, list[Shelved]] = defaultdict(list)
    for shelved in head:
        by_id[shelved.wig_id].append(shelved)
    for wig_id, entries in by_id.items():
        if len(entries) > 1:
            paths = ", ".join(e.path for e in entries)
            for entry in entries:
                report.fail(
                    entry.path,
                    f"wig_id {wig_id} is on {len(entries)} files ({paths}). "
                    "An id is one wig: claims bind to it, so a fitting on "
                    "either file would read as proof of both. A copy that "
                    "is meant to be its own wig needs its own id -- save "
                    "it as new in HAIR rather than duplicating the file",
                )

    if base_ref is None:
        return

    base = read_shelf(
        git_list_wigs(base_ref), lambda p: git_show(base_ref, p), wf
    )
    base_by_path = {s.path: s for s in base}
    base_by_id = {s.wig_id: s for s in base}
    removed_paths = set(base_by_path) - set(head_by_path)

    # A wig whose id is named in a SURVIVING wig's ancestry has already
    # been replaced. Somebody fitted it before its successor landed.
    # They lose minutes, not their contribution.
    superseded_by: dict[str, Shelved] = {}
    for shelved in head:
        for ancestor in getattr(shelved.wig, "supersedes", []) or []:
            superseded_by.setdefault(ancestor.strip(), shelved)

    claimed_ancestors: set[str] = set()

    for shelved in head:
        path = shelved.path
        ancestry = [
            a.strip()
            for a in (getattr(shelved.wig, "supersedes", []) or [])
            if a.strip()
        ]
        base_here = base_by_path.get(path)
        is_new_path = base_here is None
        id_changed = (
            base_here is not None and base_here.wig_id != shelved.wig_id
        )

        if not is_new_path and not id_changed:
            continue  # same wig continuing; check_against_base owns it

        # Shape 3: a stale attestation. The file being INTRODUCED is a
        # wig that something else on the shelf has already replaced.
        #
        # "Introduced" is load-bearing, and getting it wrong is how the
        # shop would bounce its own shelf. Since HAIR 0.9.7 a revision
        # variant carries ancestry naming a wig that stays put, so the
        # ancestry index alone marks perfectly current files as
        # superseded. Only a wig arriving at a new path, or replacing
        # what was at its own path, can be somebody re-adding a
        # description the shelf has moved past.
        stale = superseded_by.get(shelved.wig_id)
        if stale is not None and stale.path != path:
            report.fail(
                path,
                f"this wig was superseded by {stale.path}. You fitted a "
                "wig that has since been replaced -- your proof is real, "
                "it is just about a description the shelf no longer "
                "carries. Download that file, import it, fit it, and "
                "your name goes on the description people actually "
                "download",
            )
            continue

        # What, if anything, does this pull request claim to replace?
        replaced: Shelved | None = None
        if id_changed:
            replaced = base_here
        else:
            for ancestor in ancestry:
                candidate = base_by_id.get(ancestor)
                if candidate is not None and candidate.path in removed_paths:
                    replaced = candidate
                    break

        if replaced is None:
            # A pure addition. Ancestry here is lineage, not a claim to
            # replace anything, and since 0.9.7 nearly every sourced
            # submission carries some. Report it and move on.
            standing = [
                base_by_id[a].path
                for a in ancestry
                if a in base_by_id and base_by_id[a].path not in removed_paths
            ]
            if standing:
                report.note(
                    path,
                    "new wig, ancestry names "
                    f"{', '.join(standing)}, which this pull request "
                    "leaves on the shelf. Read as a variant rather than a "
                    "replacement",
                )
            continue

        claimed_ancestors.add(replaced.path)

        # A backwards supersession: the file being submitted is the
        # ancestor of the file it would overwrite. Same mistake as the
        # stale attestation above, arriving by the other door.
        if shelved.wig_id in (
            a.strip() for a in getattr(replaced.wig, "supersedes", []) or []
        ):
            report.fail(
                path,
                f"this would replace {replaced.path} with its own "
                "ancestor. You fitted an older copy of this wig. Download "
                "the current file, import it, fit it, and submit that",
            )
            continue

        ov = overlap(replaced.wig, shelved.wig, wf)
        # The one number a reviewer needs and cannot see in a diff: how
        # much proof the wig being replaced had accumulated. Stated as a
        # FACT, never as a threshold -- what counts as "a lot" is policy
        # and belongs in the reviewer's instructions, not baked in here
        # where it would silently become the rule.
        incumbent = len({
            bundle_identity(b)
            for b in wf.claims_of(replaced.wig)
            if bundle_is_perfect(b, replaced.wig, mods)
        })
        line = (
            f"replaces a wig with {incumbent} independent fitting(s). "
            + overlap_line(ov)
        )

        if ancestry[:1] == [replaced.wig_id]:
            report.note(path, f"supersedes {replaced.path}. {line}")
        elif replaced.wig_id in ancestry:
            generations = ancestry.index(replaced.wig_id) + 1
            report.note(
                path,
                f"supersedes {replaced.path}, {generations} generations "
                f"in one pull request. {line}",
            )
        else:
            standing = [
                base_by_id[a].path
                for a in ancestry
                if a in base_by_id and base_by_id[a].path not in removed_paths
            ]
            if standing:
                # Branch 4: the ancestry names a wig that is still on the
                # shelf, and it is not the one being replaced.
                report.warn(
                    path,
                    f"wrong ancestor: this replaces {replaced.path} "
                    f"({replaced.wig_id}), but its ancestry names "
                    f"{', '.join(standing)}, which stays on the shelf. "
                    "Either it grew out of a different wig, or this pull "
                    f"request is replacing the wrong file. {line}",
                )
            else:
                # Branch 3: not a supersession the repo can trace.
                report.warn(
                    path,
                    f"this replaces {replaced.path} ({replaced.wig_id}), "
                    "but nothing in its ancestry names that wig"
                    + (
                        f" (ancestry: {', '.join(ancestry)})"
                        if ancestry
                        else " (it carries no ancestry at all)"
                    )
                    + f". The shop cannot trace the lineage. {line}. Worth "
                    "asking the contributor for the story",
                )

        repaired = claims_cost(replaced.wig, ov["changed_digests"], wf)
        if repaired:
            names = sorted({n for group in repaired.values() for n in group})
            report.warn(
                path,
                f"{len(repaired)} repaired row(s) carried claims by "
                f"{', '.join(names)}, which this change orphans. Repair "
                "flowing back to the shelf is the designed path, and a "
                "row somebody proved working is still a different thing "
                "to repair than a row nobody could. Worth reading the "
                "contributor's account of what was wrong with it",
            )

        dropped = claims_cost(replaced.wig, ov["removed_digests"], wf)
        if dropped:
            # Whose proof is being discarded decides whether this is a
            # person changing their mind or a person deleting somebody
            # else's work (owner ruling 2026-08-08). A key still present
            # in the submitted file is withdrawing its own earlier word,
            # which is theirs to withdraw. A key that is nowhere in the
            # file cannot answer for itself, and the row leaves carrying
            # proof nobody here is entitled to retract.
            present = {
                bundle_identity(b) for b in wf.claims_of(shelved.wig)
            }
            foreign = {
                digest: {
                    identity: name
                    for identity, name in group.items()
                    if identity not in present
                }
                for digest, group in dropped.items()
            }
            foreign = {d: g for d, g in foreign.items() if g}
            if foreign:
                report.fail(
                    path,
                    f"{len(foreign)} row(s) removed here carried proof by "
                    f"{named(foreign)}, who is not a fitter on this file. "
                    "Trimming rows to reach a perfect fit is the move the "
                    "gate tempts, and it discards somebody else's work to "
                    "do it. If your hardware revision lacks these "
                    "buttons, submit your revision as its own wig rather "
                    "than cutting them out of the shared one. If the "
                    "codes are genuinely dead, say so in the pull request "
                    "and a maintainer can merge past this",
                )
            own = {d: g for d, g in dropped.items() if d not in foreign}
            if own:
                report.warn(
                    path,
                    f"{len(own)} row(s) removed here carried "
                    f"{named(own)}'s own earlier proof, withdrawn in this "
                    "change. Theirs to withdraw, and still worth a "
                    "sentence about what changed their mind",
                )

    for path in sorted(removed_paths - claimed_ancestors):
        report.warn(
            path,
            "this wig leaves the shelf and nothing in the pull request "
            "supersedes it. The shelf holds current descriptions, so a "
            "wig only retires when something replaces it. Worth "
            "confirming the removal is deliberate",
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


def main(argv: list[str] | None = None) -> int:
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
        help="git ref to compare against for the fittings-superset and "
        "ancestry checks",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="repository root (default: current directory)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    mods = load_hair(args.hair_src)
    report = Report()

    targets = args.files or discover(root)
    if not targets and not args.base_ref:
        print("No wigs to check yet.")
        return 0

    hashes: dict[str, list[str]] = defaultdict(list)

    for rel_path in targets:
        rel_path = Path(rel_path).as_posix()
        full = root / rel_path
        if not full.exists():
            # A deletion in the diff. The ancestry walk accounts for it.
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

    check_shelf(root, args.base_ref, mods, report)

    submitted = (
        {Path(f).as_posix() for f in args.files} if args.files else None
    )
    check_duplicates(root, hashes, submitted, mods, report)

    return emit(report)


def check_duplicates(
    root: Path,
    hashes: dict[str, list[str]],
    submitted: set[str] | None,
    mods,
    report: Report,
) -> None:
    """Two files, one code set. The same remote is already here.

    ``wig_content_hash`` is no longer an attestation binding anywhere,
    despite the name -- claims bind per-row digests. It survives for
    exactly this: spotting the same remote arriving under a second name.

    A duplicate is only ever the incoming file's problem. On a diff run
    the failure is reported against the wig being added, never against
    the one already merged, so a contributor is not shown an error on a
    file they did not touch.
    """
    wf = mods["wig_format"]

    if submitted is not None:
        for rel_path in discover(root):
            if rel_path in submitted:
                continue
            full = root / rel_path
            if not full.exists():
                continue
            result = wf.parse_wig(full.read_text(encoding="utf-8"))
            if result.ok and result.wig is not None:
                digest = wf.wig_content_hash(result.wig)
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


def emit(report: Report) -> int:
    """Print the outcome, and annotate the PR when running in Actions."""
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"

    for level, prefix, bucket in (
        ("notice", "NOTE ", report.notes),
        ("warning", "WARN ", report.warnings),
        ("error", "FAIL ", report.failures),
    ):
        for path in sorted(bucket):
            for message in bucket[path]:
                if in_actions:
                    print(f"::{level} file={path}::{message}")
                else:
                    print(f"{prefix} {path}: {message}")

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

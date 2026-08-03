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
what only means anything against a previous version: what a changed row
cost in orphaned claims, and that no fitting went missing.

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


def fitting_identities(bundle) -> set[str]:
    """Every handle by which one person's bundle can be recognised.

    A SET rather than a single key, and matched by intersection,
    because the thing this feeds is the check that refuses a pull
    request for deleting somebody else's fitting. That check is worth
    having and its false positive is vicious: it tells a contributor
    they attested a stale download when they did nothing of the sort,
    and there is no edit they can make to their own file that answers
    it.

    So identity is generous on purpose. A person who reinstalls Home
    Assistant signs with a new key, and a person who tidies their
    display name changes their handle; either would look like a
    stranger arriving and the original vanishing if identity rested on
    one field. This repo has already seen the handle case, with the
    same install attesting first as "David" and later as "David
    Bailey".

    Two strangers who both attest unsigned, with no GitHub account and
    the same display name, will read as one person. That is the right
    way to be wrong here: the cost is a duplicate nobody is warned
    about, against falsely accusing somebody of destroying work.
    """
    out = set()
    if bundle.key:
        out.add(f"key:{bundle.key.strip()}")
    account = github_key(bundle.github)
    if account:
        out.add(f"gh:{account}")
    if bundle.handle and bundle.handle.strip():
        out.add(f"name:{bundle.handle.strip().casefold()}")
    return out


def check_claims(rel_path: str, wig, mods, report: Report) -> None:
    """Everything the shop asks of a wig's attestations.

    Under hair-wig/3 a fitting is a signed bundle of per-row claims,
    each binding one row's transmit recipe by digest. Every judgment
    here is HAIR's: ``claims_of``, ``wig_row_digests``,
    ``bundle_is_complete``, ``coverage`` and ``verify_fitting`` are all
    imported, so a wig that reads perfect here reads perfect in the
    Closet. The shop adds exactly one idea of its own, and names it
    something HAIR does not use.

    Three words doing three jobs, deliberately not interchangeable:

    - **Admitted**: every current row carries some claim. The shop's
      entry gate, and only the shop's. HAIR has no such concept, which
      is why it does not borrow HAIR's word.
    - **Perfect**: one person claimed every current row worked. HAIR's
      ``bundle_is_complete``, and what the Fittings column counts.
    - **Covered**: the union of rows anybody proved worked. HAIR's
      ``coverage``, which its own docstring hands to the shop as
      judgement rather than a green check.

    The distinction is load-bearing. Three people who each proved a
    different third have not, between them, produced anybody who can
    say the whole wig works, so coverage must never be allowed to read
    as proof the way a perfect fit does.
    """
    wf = mods["wig_format"]
    wfit = mods["wig_fitting"]
    fsign = mods["fitting_signing"]

    raw_entries = wig.extra.get("fittings")
    raw_entries = raw_entries if isinstance(raw_entries, list) else []

    # Legacy fittings are refused, not converted (owner ruling
    # 2026-08-03). A whole-file hash says "these bytes, all of them" and
    # carries nothing about which rows anybody proved, so minting claims
    # from one would manufacture evidence nobody gave. HAIR drops them on
    # import and the shop says so out loud rather than letting a wig look
    # attested when its proof no longer counts anywhere.
    #
    # The test is the SHAPE, never the format stamp. Files exist that
    # stamp hair-wig/3 and carry old-shape fittings, so trusting the
    # major would admit exactly what this refuses.
    legacy = [e for e in raw_entries if wf.is_legacy_fitting(e)]
    if legacy:
        who = ", ".join(
            sorted(
                repr(str(e.get("handle", "?")))
                for e in legacy
                if isinstance(e, dict)
            )
        )
        report.fail(
            rel_path,
            f"{len(legacy)} fitting(s) ({who}) use the pre-claims format. "
            "They cannot be converted, because a whole-file hash does not "
            "record which rows anybody proved. Import this wig into HAIR "
            "0.9.5 or newer, live with the device, and save it to the "
            "closet again to attest it under the claims model",
        )

    bundles = wf.claims_of(wig)
    if not bundles:
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

    # Pair each bundle with the raw entry it came from: verify_fitting
    # checks a signature over the raw JSON, not over the parsed object.
    pairs = []
    for entry in raw_entries:
        if not wf.is_claims_bundle(entry):
            continue
        bundle = wf.parse_claims_bundle(entry)
        if bundle is not None:
            pairs.append((entry, bundle))

    seen_handles: dict[str, list[str]] = defaultdict(list)
    seen_accounts: dict[str, list[str]] = defaultdict(list)
    fingerprints: dict[str, set[str]] = defaultdict(set)
    wont_work: dict[str, list[str]] = defaultdict(list)

    perfect = 0
    unclaimed_by_any = set(digests)

    for entry, bundle in pairs:
        who = bundle.handle or "(unnamed)"
        seen_handles[who.strip().casefold()].append(who)
        account = github_key(bundle.github)
        if account:
            seen_accounts[account].append(who)

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
                f"fitting {who!r} claims wig_id {bundle.wig_id!r}, but "
                f"this file is {wig.wig_id!r}. A bundle is signed over "
                "itself, not over the file it rides in, so a bundle "
                "moved between wigs still verifies. This one is "
                "attesting something else",
            )

        verdict = fsign.verify_fitting(entry)
        if verdict == fsign.SIGNED_INVALID:
            report.fail(
                rel_path,
                f"fitting {who!r} carries a signature that does not "
                "verify. The record was altered after it was recorded",
            )
        elif verdict is None:
            report.warn(
                rel_path,
                f"fitting {who!r} is unsigned. Valid, just self-reported",
            )

        if bundle.key:
            fp = fsign.key_fingerprint(bundle.key)
            if fp:
                fingerprints[fp].add(account or who)

        for row in bundle.rows:
            if row.verdict == wf.VERDICT_WONT_WORK:
                wont_work[row.digest].append(who)

        if wfit.bundle_is_complete(bundle, wig, digests):
            perfect += 1

        if matrix:
            # A checklist samples a lattice rather than walking it, so
            # the bundle pins the lattice it sampled. Per-row presence is
            # not a question that can be asked here: a matrix wig has no
            # flat row digests by design.
            if not bundle.cells_hash:
                report.warn(
                    rel_path,
                    f"fitting {who!r} carries no cells_hash, so there is "
                    "no way to tell which lattice its checklist vouched "
                    "for",
                )
            elif bundle.cells_hash != wf.cells_content_hash(wig.climate):
                report.fail(
                    rel_path,
                    f"fitting {who!r} vouched for a different lattice "
                    f"(cells_hash {bundle.cells_hash}). The matrix "
                    "changed after it was attested, and a checklist that "
                    "sampled the old one says nothing about this one",
                )
            continue

        claimed = {row.digest for row in bundle.rows}
        unclaimed_by_any -= claimed

        orphans = [row for row in bundle.rows if row.digest not in live]
        if orphans:
            names = ", ".join(
                repr(r.alias_at_claim) for r in orphans[:5]
            )
            more = f" and {len(orphans) - 5} more" if len(orphans) > 5 else ""
            report.warn(
                rel_path,
                f"fitting {who!r} has {len(orphans)} orphaned claim(s) "
                f"({names}{more}): rows it proved that the wig no longer "
                "carries. Kept deliberately, since they are somebody's "
                "signed statement about bytes that were once here, but "
                "worth reading before merging",
            )

    if not matrix:
        # The shop's entry gate. Deliberately NOT called complete: HAIR
        # owns that word for one person covering every row, and two
        # definitions of one word is how verifiers drift apart.
        if unclaimed_by_any:
            missing = sorted(unclaimed_by_any)
            aliases = [
                s.alias
                for s in wig.signals
                if wf.signal_row_digest(s) in unclaimed_by_any
            ]
            shown = ", ".join(repr(a) for a in aliases[:5])
            more = f" and {len(missing) - 5} more" if len(missing) > 5 else ""
            report.fail(
                rel_path,
                f"{len(missing)} row(s) carry no claim at all "
                f"({shown}{more}). Every row needs somebody's verdict, "
                "even if that verdict is that the button is not on their "
                "hardware. Fit the wig on the device and save it to the "
                "closet again",
            )

        covered = wf.coverage(bundles, digests)
        if perfect == 0:
            report.warn(
                rel_path,
                f"no perfect fit: {len(covered)} of {len(digests)} row(s) "
                "are proven working, but nobody has covered the whole wig "
                "on their own hardware. Admitted and honest, and the "
                "Fittings count stays at 0 until somebody does",
            )

    for names in seen_handles.values():
        if len(names) > 1:
            report.warn(
                rel_path,
                f"handle {names[0]!r} appears on {len(names)} fittings. "
                "A person re-attesting should replace their own bundle "
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

    # The reason the exclusion reasons are an enum rather than free
    # text: several people reporting wont_work on the SAME recipe is a
    # mechanical signal that the code is wrong for a hardware revision,
    # which no amount of reading prose would surface reliably.
    for digest, names in wont_work.items():
        if len(set(names)) > 1:
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
                f"{len(set(names))} fitters report {alias!r} does not "
                f"work on their hardware ({', '.join(sorted(set(names)))}). "
                "One person is a hardware revision; several is a sign the "
                "code itself is wrong",
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

    check_claims(rel_path, wig, mods, report)

    check_comb(rel_path, wig, report)

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


def check_comb(rel_path: str, wig, report: Report) -> None:
    """Surface what combing found, if anyone combed this wig.

    A fitting attests the dimension checklist, which on a matrix wig is
    nine or so rows out of a lattice of hundreds. Codes outside the
    checklist can be wrong and no fitting will ever say so: the
    Toyotomi example carries three cells that send their neighbour's
    code, none of them in its checklist, under a complete signed
    fitting. The comb receipt is the only thing in the file that knows,
    so reading past it means merging a wig whose own paperwork says it
    is broken.

    Warnings, never failures. Combing reports and never changes a code,
    ``suspects`` is defined as findings a human should look at, and a
    wig with three bad cells out of a hundred and eighty is still worth
    having. This puts it in front of the maintainer and stops there.
    """
    comb = wig.extra.get("comb")

    if comb is None:
        report.warn(
            rel_path,
            "no comb receipt, so nobody has checked this wig's codes "
            "against each other. Not the same as clean: import it into "
            "HAIR 0.9.1 or newer, or press the comb on its closet row, "
            "and share it again to carry the result",
        )
        return

    if not isinstance(comb, dict):
        report.warn(rel_path, '"comb" is not an object; ignored')
        return

    suspects = comb.get("suspects")
    if not isinstance(suspects, int):
        report.warn(rel_path, 'comb receipt has no readable "suspects" count')
        return

    if suspects == 0:
        return

    counts = comb.get("counts")
    detail = ""
    if isinstance(counts, dict) and counts:
        detail = "; ".join(
            f"{k}: {v}" for k, v in sorted(counts.items())
        )
    dated = comb.get("date")
    report.warn(
        rel_path,
        f"combing found {suspects} suspect(s)"
        + (f" ({detail})" if detail else "")
        + (f", recorded {dated}" if dated else "")
        + ". Worth reading the receipt before merging",
    )

    # The one class worth naming individually. A malformed frame is
    # ignored by the device, which is annoying but obvious. A cell
    # sending its neighbour's code makes the device respond and look
    # like it worked while landing on the wrong state, so nobody
    # notices until they wonder why the room is a degree off.
    findings = comb.get("findings")
    if not isinstance(findings, list):
        return
    neighbours = [
        f
        for f in findings
        if isinstance(f, dict) and f.get("check") == "duplicated-neighbour"
    ]
    if not neighbours:
        return

    rows = []
    for f in neighbours[:8]:
        keys = f.get("keys")
        rows.append(" and ".join(keys) if isinstance(keys, list) else "?")
    shown = "; ".join(rows)
    if len(neighbours) > 8:
        shown += f"; and {len(neighbours) - 8} more"
    report.warn(
        rel_path,
        f"{len(neighbours)} cell(s) send a neighbour's code: {shown}. "
        "The device answers and looks like it worked while setting the "
        "wrong state, and a dimension checklist does not sample these, "
        "so no fitting can catch it",
    )

    truncated = comb.get("truncated")
    if isinstance(truncated, int) and truncated > 0:
        report.warn(
            rel_path,
            f"the comb receipt lists 200 findings and omits {truncated} "
            "more; the counts above describe the full result",
        )


def check_against_base(
    rel_path: str, text: str, base_ref: str, mods, report: Report
) -> None:
    """The rules that only exist relative to what is already merged.

    Signals used to be immutable here, because a fitting bound a hash of
    the whole file and any edit invalidated every one of them at once.
    Under hair-wig/3 a claim binds ONE row's transmit recipe, so a
    repair orphans exactly the claims about the row it changed and
    leaves everyone else's standing. Repair flowing back to the shop is
    a designed path now, and the review question is no longer "did the
    codes change" but "what did the change cost, and did anybody
    re-attest what it broke".

    Nothing here fails a pull request for changing a code. It does not
    need to: a repair that changes a row without re-attesting it leaves
    that row with no claim, and the entry gate in ``check_claims``
    refuses it there with a message about the row rather than about the
    diff. This function's job is to price the change for the human.

    What does still fail: a file must carry every bundle the repo's copy
    already has. Somebody who attests a stale download produces a
    perfectly clean diff that deletes another person's signed work, and
    git will not say a word about it.
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
            f"the copy at {base_ref} does not parse, so the repair and "
            "fittings-superset checks were skipped",
        )
        return

    new = wf.parse_wig(text)
    if not new.ok or new.wig is None:
        return

    old_bundles = wf.claims_of(old.wig)
    new_bundles = wf.claims_of(new.wig)

    # Legacy entries are invisible here, and that is the whole reason
    # this needs no special case. They are refused outright by
    # check_claims, ``claims_of`` skips them, and so a wig moving off the
    # old model drops entries this check never counted. No exception
    # window to bound, and no standing licence to delete a fitting by
    # relabelling it.
    present = set().union(*(fitting_identities(b) for b in new_bundles)) \
        if new_bundles else set()
    lost = [
        b for b in old_bundles
        if not (fitting_identities(b) & present)
    ]
    if lost:
        who = ", ".join(sorted(b.handle or "(unnamed)" for b in lost))
        report.fail(
            rel_path,
            f"this file is missing fittings that are already here "
            f"({who}). You attested an older copy of the wig. Download "
            "the current file from this repo, import it, live with it, "
            "and save it to the closet again. Nothing is wrong with "
            "your fitting; it just needs to ride alongside the others "
            "instead of replacing them",
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
            report.warn(
                rel_path,
                "the climate lattice changed, so every checklist that "
                f"pinned {old_cells} now vouches for a lattice this file "
                "no longer carries",
            )
        return

    def recipe(sig) -> tuple[str, int, bool]:
        """The three things a row digest binds, for naming what moved."""
        return (
            wf.normalized_pronto(sig.pronto),
            int(sig.ditto_count),
            bool(sig.bypass_protocol),
        )

    old_rows = {s.alias: wf.signal_row_digest(s) for s in old.wig.signals}
    new_rows = {s.alias: wf.signal_row_digest(s) for s in new.wig.signals}
    old_recipe = {s.alias: recipe(s) for s in old.wig.signals}
    new_recipe = {s.alias: recipe(s) for s in new.wig.signals}

    # Pair by alias for REPORTING only. Claims match rows by digest
    # alone, so a rename with an unchanged digest costs nothing and a
    # row whose digest moved orphans its claims wherever it is named.
    moved = [
        a for a in set(old_rows) & set(new_rows)
        if old_rows[a] != new_rows[a]
    ]
    added = sorted(set(new_rows) - set(old_rows))
    removed = sorted(set(old_rows) - set(new_rows))

    if not (moved or added or removed):
        return

    if moved:
        cost: dict[str, set[str]] = defaultdict(set)
        for bundle in old_bundles:
            for row in bundle.rows:
                if row.verdict != wf.VERDICT_WORKED:
                    continue
                for alias in moved:
                    if row.digest == old_rows[alias]:
                        cost[alias].add(bundle.handle or "(unnamed)")

        def what_moved(alias: str) -> str:
            """Which of the three recipe parts changed.

            Worth naming rather than saying "the recipe changed": a row
            whose Pronto is byte-identical and whose ditto count went
            from 0 to 1 is a real change to what leaves the blaster, and
            it is also completely invisible in a diff of the codes. A
            reviewer told only that twelve rows moved will go looking
            for twelve edited codes and find none.
            """
            was, now = old_recipe[alias], new_recipe[alias]
            parts = []
            if was[0] != now[0]:
                parts.append("pronto")
            if was[1] != now[1]:
                parts.append(f"ditto_count {was[1]} to {now[1]}")
            if was[2] != now[2]:
                parts.append(f"bypass_protocol {was[2]} to {now[2]}")
            return ", ".join(parts) or "unchanged"

        detail = "; ".join(
            f"{alias!r} ({what_moved(alias)}"
            + (
                f", was proven by {', '.join(sorted(cost[alias]))})"
                if cost.get(alias)
                else ", nobody had proven it)"
            )
            for alias in sorted(moved)[:6]
        )
        more = f"; and {len(moved) - 6} more" if len(moved) > 6 else ""
        report.warn(
            rel_path,
            f"{len(moved)} row(s) changed recipe: {detail}{more}. Those "
            "claims are now orphaned. They stay in the file as signed "
            "statements about bytes the wig no longer carries, and they "
            "are worth weighing: a row somebody proved working is a "
            "different thing to repair than a row nobody could",
        )

    if added or removed:
        report.warn(
            rel_path,
            f"rows added: {added or 'none'}; rows removed: "
            f"{removed or 'none'}. Adding a button is ordinary; removing "
            "one discards whatever anybody proved about it, so it is "
            "worth confirming that is deliberate",
        )

    old_perfect = sum(
        1 for b in old_bundles if wfit.bundle_is_complete(b, old.wig)
    )
    new_perfect = sum(
        1 for b in new_bundles if wfit.bundle_is_complete(b, new.wig)
    )
    if new_perfect < old_perfect:
        report.warn(
            rel_path,
            f"perfect fits drop from {old_perfect} to {new_perfect}. The "
            "wig is less proven after this change than before it, which "
            "is expected for a repair and worth seeing plainly",
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

"""Two rows, one transmit recipe. Real devices ship them.

A toggle remote puts one code under two names -- Power and Toggle, On
and Off -- and the row digest binds the recipe, not the name. So one
``worked`` claim satisfies both rows, and ``bundle_is_complete`` can
pass on a bundle naming fewer rows than the wig has.

That is correct: same bytes, same proof, and the person really did press
something that worked. It is also surprising enough that somebody will
eventually read it as a bug in the fittings count, so it is pinned here
with the reasoning attached rather than left to be discovered.
"""

from __future__ import annotations

import pytest
from conftest import PRONTOS, Person, attest, has, make_wig

PATH = "wigs/bench/bench-tv-t-1.wig.json"
WIG_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def david():
    return Person("David", github="DAB-LABS")


@pytest.fixture
def toggle_wig():
    """Power and Toggle send identical bytes."""
    return make_wig(
        WIG_ID,
        kind="tv",
        model="T-1",
        rows=3,
        aliases=["Power", "Toggle", "Mute"],
        prontos=[PRONTOS[0], PRONTOS[0], PRONTOS[1]],
    )


def test_the_two_rows_share_one_digest(mods, toggle_wig):
    wf = mods["wig_format"]
    wig = wf.parse_wig(__import__("json").dumps(toggle_wig)).wig
    digests = wf.wig_row_digests(wig)
    assert digests[0] == digests[1]
    assert len(set(digests)) == 2


def test_one_claim_covers_both_rows(shop, mods, david, toggle_wig):
    """Two claims for three rows, and the wig is perfectly fitted."""
    attest(mods, toggle_wig, david)
    # Drop the Toggle claim: its digest is already covered by Power.
    bundle = toggle_wig["fittings"][0]
    bundle["rows"] = [
        row for row in bundle["rows"] if row["alias_at_claim"] != "Toggle"
    ]
    mods["fitting_signing"].sign_fitting(bundle, david.private_b64)

    shop.put(PATH, toggle_wig)
    report = shop.validate()
    assert report.ok, dict(report.failures)
    assert len(bundle["rows"]) == 2


def test_renaming_one_of_them_orphans_nothing(shop, mods, david, toggle_wig):
    attest(mods, toggle_wig, david)
    shop.put(PATH, toggle_wig)
    base = shop.merge("toggle wig")

    renamed = make_wig(
        WIG_ID,
        kind="tv",
        model="T-1",
        rows=3,
        aliases=["Power", "Standby", "Mute"],
        prontos=[PRONTOS[0], PRONTOS[0], PRONTOS[1]],
    )
    renamed["fittings"] = toggle_wig["fittings"]
    shop.put(PATH, renamed)
    report = shop.validate(PATH, base_ref=base)
    assert report.ok, dict(report.failures)
    assert not has(report.warnings, "orphaned claim", PATH)


def test_changing_the_shared_code_orphans_both_claims(
    shop, mods, david, toggle_wig
):
    """One edit, two rows, and the successor must re-prove both."""
    attest(mods, toggle_wig, david)
    shop.put(PATH, toggle_wig)
    base = shop.merge("toggle wig")

    heir = make_wig(
        "22222222-2222-4222-8222-222222222222",
        kind="tv",
        model="T-1",
        rows=3,
        aliases=["Power", "Toggle", "Mute"],
        prontos=[PRONTOS[2], PRONTOS[2], PRONTOS[1]],
        supersedes=[WIG_ID],
    )
    attest(mods, heir, david)
    shop.put(PATH, heir)
    report = shop.validate(PATH, base_ref=base)
    assert report.ok, dict(report.failures)
    assert has(report.notes, "changed: 'Power', 'Toggle'", PATH)
    assert has(report.warnings, "carried claims by", PATH)

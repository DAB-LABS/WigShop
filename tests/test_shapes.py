"""The three pull request shapes, from the supersession policy.

1. Attestation on current content -- additive, the accumulation path.
2. Supersession -- replacement, a new wig that names its ancestor.
3. Stale attestation -- bounced, kindly, at the successor.

Shape 1 stopped being strictly additive in HAIR 0.9.7: one install has
one current word on one wig, so a re-fit shows a bundle removed and a
bundle added carrying the same key. That is still shape 1.
"""

from __future__ import annotations

import pytest
from conftest import Person, attest, has, make_wig

PATH = "wigs/bench/bench-fan-b-1.wig.json"
WIG_ID = "11111111-1111-4111-8111-111111111111"
HEIR_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def david():
    return Person("David", github="DAB-LABS")


@pytest.fixture
def mira():
    return Person("Mira", github="mira-h")


@pytest.fixture
def shelved(shop, mods, david):
    """One perfectly fitted wig, merged."""
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    base = shop.merge("first wig")
    return base


# ---------------------------------------------------------------------------
# Shape 1: attestation on current content
# ---------------------------------------------------------------------------


def test_a_second_fitter_is_a_clean_additive_pr(
    shop, mods, david, mira, shelved
):
    wig = attest(mods, make_wig(WIG_ID), david)
    attest(mods, wig, mira)
    shop.put(PATH, wig)
    report = shop.validate(PATH, base_ref=shelved)
    assert report.ok, report.failures
    assert has(report.notes, "fittings added: Mira", PATH)


def test_a_refit_from_one_install_replaces_and_is_still_additive(
    shop, mods, david, shelved
):
    """One removed, one added, same key, unchanged content. Shape 1."""
    wig = attest(mods, make_wig(WIG_ID), david, date="2026-09-01")
    shop.put(PATH, wig)
    report = shop.validate(PATH, base_ref=shelved)
    assert report.ok, report.failures
    assert has(report.notes, "re-attestation by David", PATH)
    assert has(report.notes, "not a trimmed ledger", PATH)


def test_deleting_somebody_elses_fitting_is_refused(shop, mods, david, mira):
    """The vicious diff: perfectly clean, and it destroys signed work."""
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, mira)
    shop.put(PATH, wig)
    base = shop.merge("two fitters")

    stale = attest(mods, make_wig(WIG_ID), david)
    shop.put(PATH, stale)
    report = shop.validate(PATH, base_ref=base)
    assert has(report.failures, "missing fittings that are already here", PATH)
    assert has(report.failures, "Mira", PATH)


def test_two_installs_typing_one_github_handle_are_both_protected(
    shop, mods
):
    """The hole the old identity match left, closed.

    Two bundles, two keys, one typed GitHub account. Under the previous
    set-of-aliases match, deleting either left the other satisfying its
    identity by the shared account, and the deletion went unreported.
    """
    one = Person("David Bailey", github="DAB-LABS", install="laptop")
    two = Person("David B", github="DAB-LABS", install="nuc")
    wig = make_wig(WIG_ID)
    attest(mods, wig, one)
    attest(mods, wig, two)
    shop.put(PATH, wig)
    base = shop.merge("two installs, one account")

    trimmed = attest(mods, make_wig(WIG_ID), one)
    shop.put(PATH, trimmed)
    report = shop.validate(PATH, base_ref=base)
    assert has(report.failures, "missing fittings that are already here", PATH)


def test_a_rename_with_an_unchanged_recipe_costs_nothing(
    shop, mods, david, shelved
):
    """Aliases were never in the digest, so a claim survives a rename."""
    wig = make_wig(WIG_ID, aliases=["On", "Power Off", "Speed Low"])
    # Claim under the OLD names, then rename the rows: the digests are
    # what match, so the fitting stays perfect.
    original = make_wig(WIG_ID)
    attest(mods, original, david)
    wig["fittings"] = original["fittings"]
    shop.put(PATH, wig)
    report = shop.validate(PATH, base_ref=shelved)
    assert report.ok, report.failures
    assert has(report.notes, "rows renamed, recipes unchanged", PATH)


def test_editing_codes_without_a_new_id_is_refused(
    shop, mods, david, shelved
):
    """The shelf holds current descriptions. A changed one is a new wig."""
    edited = make_wig(WIG_ID, ditto=[1, 0, 0])
    attest(mods, edited, david)
    shop.put(PATH, edited)
    report = shop.validate(PATH, base_ref=shelved)
    assert has(report.failures, "codes changed but the wig_id did not", PATH)
    assert has(report.failures, "save your device as a new wig", PATH)


# ---------------------------------------------------------------------------
# Shape 2: supersession
# ---------------------------------------------------------------------------


def test_a_clean_supersession_at_the_same_path(shop, mods, david, shelved):
    """The common case: a same-device successor composes the same name."""
    heir = make_wig(HEIR_ID, rows=4, supersedes=[WIG_ID])
    attest(mods, heir, david)
    shop.put(PATH, heir)
    report = shop.validate(PATH, base_ref=shelved)
    assert report.ok, report.failures
    assert has(report.notes, f"supersedes {PATH}", PATH)
    assert has(report.notes, "3 of 4 rows byte-identical", PATH)
    assert has(report.notes, "added: 'Speed Medium'", PATH)


def test_a_supersession_that_moves_the_filename(shop, mods, david, shelved):
    """Pairing is by id, so a kind or model change is followed for free."""
    moved = "wigs/bench/bench-fan-b-2.wig.json"
    heir = make_wig(HEIR_ID, model="B-2", supersedes=[WIG_ID])
    attest(mods, heir, david)
    shop.put(moved, heir)
    shop.remove(PATH)
    report = shop.validate(moved, PATH, base_ref=shelved)
    assert report.ok, report.failures
    assert has(report.notes, f"supersedes {PATH}", moved)


def test_two_generations_in_one_pull_request(shop, mods, david, shelved):
    """Superseded twice locally before submitting. Legitimate."""
    middle = "33333333-3333-4333-8333-333333333333"
    heir = make_wig(HEIR_ID, rows=4, supersedes=[middle, WIG_ID])
    attest(mods, heir, david)
    shop.put(PATH, heir)
    report = shop.validate(PATH, base_ref=shelved)
    assert report.ok, report.failures
    assert has(report.notes, "2 generations in one pull request", PATH)


def test_a_successor_must_clear_the_gate_on_its_own(
    shop, mods, david, mira, shelved
):
    """Nobody has proven the new description until somebody proves it."""
    heir = make_wig(HEIR_ID, rows=4, supersedes=[WIG_ID])
    attest(mods, heir, david, verdicts={"Speed Medium": "wont_work"})
    shop.put(PATH, heir)
    report = shop.validate(PATH, base_ref=shelved)
    assert has(report.failures, "no perfect fit", PATH)


def test_trimming_rows_that_carried_other_peoples_claims_is_flagged(
    shop, mods, david, mira
):
    """The move the perfect-only gate tempts. Visible in the digest diff."""
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, mira)
    shop.put(PATH, wig)
    base = shop.merge("two fitters")

    haircut = make_wig(HEIR_ID, rows=2, supersedes=[WIG_ID])
    attest(mods, haircut, david)
    shop.put(PATH, haircut)
    report = shop.validate(PATH, base_ref=base)
    assert report.ok, report.failures  # a warning, for a human to weigh
    assert has(report.warnings, "carried claims by", PATH)
    assert has(report.warnings, "not a haircut on the shared file", PATH)


# ---------------------------------------------------------------------------
# Shape 3: stale attestation
# ---------------------------------------------------------------------------


def test_a_stale_fitter_is_bounced_at_the_successor(shop, mods, david, mira):
    """They fitted a wig that was replaced while they were fitting it."""
    heir_path = "wigs/bench/bench-fan-b-2.wig.json"
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    shop.merge("first wig")
    heir = make_wig(HEIR_ID, model="B-2", supersedes=[WIG_ID])
    attest(mods, heir, david)
    shop.put(heir_path, heir)
    shop.remove(PATH)
    base = shop.merge("superseded")

    # Mira fitted the old download and puts it back on the shelf.
    old = make_wig(WIG_ID)
    attest(mods, old, david)
    attest(mods, old, mira)
    shop.put(PATH, old)
    report = shop.validate(PATH, base_ref=base)
    assert has(report.failures, f"superseded by {heir_path}", PATH)
    assert has(report.failures, "your proof is real", PATH)


def test_a_backwards_supersession_is_bounced_too(shop, mods, david, mira):
    """Same mistake, arriving by the other door: over the successor."""
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    shop.merge("first wig")
    heir = make_wig(HEIR_ID, rows=4, supersedes=[WIG_ID])
    attest(mods, heir, david)
    shop.put(PATH, heir)
    base = shop.merge("superseded in place")

    old = make_wig(WIG_ID)
    attest(mods, old, david)
    attest(mods, old, mira)
    shop.put(PATH, old)
    report = shop.validate(PATH, base_ref=base)
    assert has(report.failures, "replace", PATH)
    assert has(report.failures, "its own ancestor", PATH)


def test_a_repair_is_reported_as_a_repair_not_a_haircut(
    shop, mods, david, mira
):
    """Repair flowing back to the shelf is the designed path.

    Both a repaired row and a removed one orphan whatever bound the old
    recipe. Saying so in one sentence would describe somebody's repair
    as a trim, which is wrong and reads as an accusation.
    """
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, mira)
    shop.put(PATH, wig)
    base = shop.merge("two fitters")

    repaired = make_wig(HEIR_ID, ditto=[1, 0, 0], supersedes=[WIG_ID])
    attest(mods, repaired, david)
    shop.put(PATH, repaired)
    report = shop.validate(PATH, base_ref=base)
    assert report.ok, report.failures
    assert has(report.notes, "changed: 'Power On'", PATH)
    assert has(report.warnings, "repaired row(s) carried claims by", PATH)
    assert not has(report.warnings, "not a haircut on the shared file", PATH)


def test_a_trim_is_reported_as_a_trim(shop, mods, david, mira):
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, mira)
    shop.put(PATH, wig)
    base = shop.merge("two fitters")

    haircut = make_wig(HEIR_ID, rows=2, supersedes=[WIG_ID])
    attest(mods, haircut, david)
    shop.put(PATH, haircut)
    report = shop.validate(PATH, base_ref=base)
    assert has(report.warnings, "removed here carried claims by", PATH)
    assert not has(report.warnings, "repaired row(s)", PATH)

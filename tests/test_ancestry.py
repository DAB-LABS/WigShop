"""The five branches of the ancestry-keyed overlap check.

Keyed on ancestry, never on file operations: a same-device successor
composes the same filename, so the common supersession pull request is
a modify at one path and a remove-plus-add watcher sleeps through it.

Branch 4 has one refinement HAIR 0.9.7 forced. Every save route that
mints from a sourced device now stamps ``supersedes``, including Save as
New, which keeps both files. Ancestry therefore arrives on essentially
every sourced submission, including revision variants that replace
nothing, so ancestry alone can never flag anything.
"""

from __future__ import annotations

import pytest
from conftest import PRONTOS, Person, attest, has, make_wig

BENCH = "wigs/bench/bench-fan-b-1.wig.json"
OTHER = "wigs/bench/bench-fan-c-1.wig.json"
WIG_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ID = "99999999-9999-4999-8999-999999999999"
HEIR_ID = "22222222-2222-4222-8222-222222222222"
UNKNOWN_ID = "deadbeef-0000-4000-8000-000000000000"


@pytest.fixture
def david():
    return Person("David", github="DAB-LABS")


@pytest.fixture
def two_wig_shelf(shop, mods, david):
    """Two unrelated wigs on the shelf, merged."""
    shop.put(BENCH, attest(mods, make_wig(WIG_ID), david))
    shop.put(
        OTHER,
        attest(
            mods,
            make_wig(OTHER_ID, model="C-1", prontos=PRONTOS[3:6]),
            david,
        ),
    )
    return shop.merge("two wigs")


# ---------------------------------------------------------------------------
# Branch 1 and 2 live in test_shapes.py, where the PR shape is the point.
# ---------------------------------------------------------------------------


def test_branch_3_a_replacement_the_repo_cannot_trace(
    shop, mods, david, two_wig_shelf
):
    """Id changed, and nothing in the ancestry names what it replaced."""
    heir = make_wig(HEIR_ID, rows=4, supersedes=[UNKNOWN_ID])
    attest(mods, heir, david)
    shop.put(BENCH, heir)
    report = shop.validate(BENCH, base_ref=two_wig_shelf)
    assert report.ok, report.failures
    assert has(
        report.warnings, "nothing in its ancestry names that wig", BENCH
    )
    assert has(report.warnings, "asking the contributor for the story", BENCH)


def test_branch_3_a_replacement_with_no_ancestry_at_all(
    shop, mods, david, two_wig_shelf
):
    heir = make_wig(HEIR_ID, rows=4)
    attest(mods, heir, david)
    shop.put(BENCH, heir)
    report = shop.validate(BENCH, base_ref=two_wig_shelf)
    assert has(report.warnings, "carries no ancestry at all", BENCH)


def test_branch_4_wrong_ancestor(shop, mods, david, two_wig_shelf):
    """It replaces one wig while claiming to have grown out of another."""
    heir = make_wig(HEIR_ID, rows=4, supersedes=[OTHER_ID])
    attest(mods, heir, david)
    shop.put(BENCH, heir)
    report = shop.validate(BENCH, base_ref=two_wig_shelf)
    assert report.ok, report.failures
    assert has(report.warnings, "wrong ancestor", BENCH)
    assert has(report.warnings, OTHER, BENCH)


def test_branch_4_does_not_fire_on_a_variant_that_replaces_nothing(
    shop, mods, david, two_wig_shelf
):
    """The 0.9.7 refinement, and the one that matters most in practice.

    A revision variant is a NEW wig at a NEW path whose ancestry names a
    shop wig that stays on the shelf. Under the unrefined branch 4 that
    reads as a wrong ancestor and a valid contribution gets bounced.
    Save as New stamps ancestry on every sourced save, so this is the
    common case, not the exotic one.
    """
    variant = "wigs/bench/bench-fan-b-1-eu.wig.json"
    wig = make_wig(
        HEIR_ID, model="B-1-EU", rows=2, supersedes=[WIG_ID]
    )
    attest(mods, wig, david)
    shop.put(variant, wig)
    report = shop.validate(variant, base_ref=two_wig_shelf)
    assert report.ok, report.failures
    assert not has(report.warnings, "wrong ancestor", variant)
    assert not has(report.warnings, "cannot trace", variant)
    assert has(
        report.notes, "Read as a variant rather than a replacement", variant
    )
    assert has(report.notes, BENCH, variant)


def test_a_brand_new_wig_with_local_only_ancestry_is_silent(
    shop, mods, david, two_wig_shelf
):
    """Ancestry naming wigs the shop has never seen is just lineage."""
    fresh = "wigs/bench/bench-tv-t-9.wig.json"
    wig = make_wig(
        HEIR_ID,
        kind="tv",
        model="T-9",
        prontos=PRONTOS[4:7],
        supersedes=[UNKNOWN_ID],
    )
    attest(mods, wig, david)
    shop.put(fresh, wig)
    report = shop.validate(fresh, base_ref=two_wig_shelf)
    assert report.ok, report.failures
    assert not report.warnings.get(fresh)
    assert not report.notes.get(fresh)


def test_branch_5_two_files_cannot_share_one_id(shop, mods, david):
    """Claims bind to the id, so one id in two places is proof of both."""
    copy = "wigs/bench/bench-fan-b-1-copy.wig.json"
    wig = attest(mods, make_wig(WIG_ID), david)
    shop.put(BENCH, wig)
    shop.put(copy, wig)
    report = shop.validate()
    assert has(report.failures, "is on 2 files", BENCH)
    assert has(report.failures, "is on 2 files", copy)


def test_id_uniqueness_is_checked_without_a_base_ref(shop, mods, david):
    """A full sweep on main must catch it too, not only a pull request."""
    copy = "wigs/bench/bench-fan-b-1-copy.wig.json"
    wig = attest(mods, make_wig(WIG_ID), david)
    shop.put(BENCH, wig)
    shop.put(copy, wig)
    report = shop.validate(base_ref=None)
    assert has(report.failures, "An id is one wig")


def test_removing_a_wig_with_no_successor_is_flagged(
    shop, mods, david, two_wig_shelf
):
    shop.remove(OTHER)
    report = shop.validate(OTHER, base_ref=two_wig_shelf)
    assert report.ok, report.failures
    assert has(
        report.warnings, "nothing in the pull request supersedes it", OTHER
    )


def test_a_supersession_does_not_trip_the_no_successor_warning(
    shop, mods, david, two_wig_shelf
):
    moved = "wigs/bench/bench-fan-b-2.wig.json"
    heir = make_wig(HEIR_ID, model="B-2", supersedes=[WIG_ID])
    attest(mods, heir, david)
    shop.put(moved, heir)
    shop.remove(BENCH)
    report = shop.validate(moved, BENCH, base_ref=two_wig_shelf)
    assert not has(
        report.warnings, "nothing in the pull request supersedes it"
    )


def test_the_ancestors_ledger_retires_with_the_ancestor(
    shop, mods, david
):
    """A supersession is the one case where fittings legitimately go.

    The superset check protects a wig's ledger while it stays the same
    wig. Applying it across a supersession would refuse the one pull
    request shape the whole policy is built around.
    """
    mira = Person("Mira", github="mira-h")
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, mira)
    shop.put(BENCH, wig)
    base = shop.merge("two fitters")

    heir = make_wig(HEIR_ID, rows=4, supersedes=[WIG_ID])
    attest(mods, heir, david)
    shop.put(BENCH, heir)
    report = shop.validate(BENCH, base_ref=base)
    assert report.ok, report.failures
    assert not has(report.failures, "missing fittings")

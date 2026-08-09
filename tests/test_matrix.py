"""Matrix wigs: the completeness hole, and the in-place repair path.

A matrix has thousands of cells and nobody presses thousands of
buttons, so its attestation is a CHECKLIST that samples the lattice.
Two consequences the shop has to handle itself, because HAIR does not.
"""

from __future__ import annotations

import pytest
from conftest import (
    Person,
    attest_matrix,
    checklist_of,
    has,
    make_matrix_wig,
)

PATH = "wigs/bench/bench-ac-a-1.wig.json"
WIG_ID = "aaaa1111-1111-4111-8111-111111111111"


@pytest.fixture
def david():
    return Person("David", github="DAB-LABS")


@pytest.fixture
def mira():
    return Person("Mira", github="mira-h")


# ---------------------------------------------------------------------------
# The completeness hole
# ---------------------------------------------------------------------------


def test_hairs_own_judgment_passes_a_one_row_bundle(mods):
    """The bug this file exists for, stated against HAIR itself.

    Not a criticism of HAIR -- its fix lands in the perfect-or-nothing
    round -- but files minted by 0.9.7 installs are in the wild now, so
    the shop must not trust this answer. If this test ever fails, HAIR
    has fixed it and the shop's own check has become belt and braces.
    """
    import json

    wf, wfit = mods["wig_format"], mods["wig_fitting"]
    wig = attest_matrix(mods, make_matrix_wig(WIG_ID), Person("X"), rows=1)
    parsed = wf.parse_wig(json.dumps(wig)).wig
    bundle = wf.claims_of(parsed)[0]
    assert len(bundle.rows) == 1
    assert len(parsed.climate.cells) == 16
    assert wfit.bundle_is_complete(bundle, parsed) is True


def test_the_shop_refuses_a_one_row_bundle(shop, mods, david):
    """Silence is not a claim."""
    shop.put(PATH, attest_matrix(mods, make_matrix_wig(WIG_ID), david, rows=1))
    report = shop.validate()
    assert has(report.failures, "no perfect fit", PATH)
    assert has(report.failures, "silence is not a claim", PATH)
    assert has(report.failures, "vouched for 1", PATH)


def test_a_whole_checklist_passes(shop, mods, david):
    shop.put(PATH, attest_matrix(mods, make_matrix_wig(WIG_ID), david))
    report = shop.validate()
    assert report.ok, dict(report.failures)


def test_one_missing_checklist_row_is_refused(shop, mods, david):
    wig = make_matrix_wig(WIG_ID)
    total = len(checklist_of(mods, wig))
    shop.put(PATH, attest_matrix(mods, wig, david, rows=total - 1))
    report = shop.validate()
    assert has(report.failures, "no perfect fit", PATH)


def test_an_excluded_checklist_row_is_not_a_perfect_fit(shop, mods, david):
    """Matrix keeps the exclusion enums; an exclusion is still not proof."""
    wig = make_matrix_wig(WIG_ID)
    key = checklist_of(mods, wig)[1].key
    shop.put(PATH, attest_matrix(
        mods, wig, david, verdicts={key: "wont_work"}
    ))
    report = shop.validate()
    assert has(report.failures, "no perfect fit", PATH)


def test_the_index_agrees_with_the_validator(shop, mods, david):
    """One judgement, one function. These used to disagree on matrices."""
    shop.put(PATH, attest_matrix(mods, make_matrix_wig(WIG_ID), david, rows=1))
    row = next(
        line for line in shop.index().splitlines()
        if line.startswith("|") and "Bench AC" in line
    )
    assert "| 0 |" in row


def test_a_bundle_pinning_a_stale_lattice_is_orphaned(shop, mods, david):
    """Not refused: the matrix twin of an orphaned flat claim.

    It cannot be a refusal, because a lattice repairs in place and
    HAIR's update keeps the existing fittings when it writes the new
    one. Failing here would reject the repair path for carrying exactly
    what HAIR put in the file. Kept, reported, counts toward nothing.
    """
    wig = make_matrix_wig(WIG_ID)
    attest_matrix(mods, wig, david)
    repaired = make_matrix_wig(WIG_ID, repair=1)
    wig["climate"] = repaired["climate"]
    shop.put(PATH, wig)
    report = shop.validate()
    assert has(report.warnings, "vouched for a different lattice", PATH)
    assert has(report.warnings, "counts toward nothing", PATH)
    # And with nothing current left, the gate is what refuses it.
    assert has(report.failures, "no perfect fit", PATH)


# ---------------------------------------------------------------------------
# The in-place repair path (owner ruling 2026-08-08)
# ---------------------------------------------------------------------------


def test_a_lattice_repairs_in_place_keeping_its_id(shop, mods, david, mira):
    """The matrix exception. A flat wig would have to become a new wig.

    Safe here in a way it is not on a flat wig: every matrix bundle pins
    its lattice, so a stale attestation fails loudly rather than riding
    along looking current.
    """
    shop.put(PATH, attest_matrix(mods, make_matrix_wig(WIG_ID), david))
    base = shop.merge("matrix wig on the shelf")

    # Exactly what HAIR writes: the existing fittings kept, the fresh
    # one appended, the lattice edited underneath both.
    repaired = make_matrix_wig(WIG_ID, repair=1)
    repaired["fittings"] = list(shop.read(PATH)["fittings"])
    attest_matrix(mods, repaired, mira)
    shop.put(PATH, repaired)
    report = shop.validate(PATH, base_ref=base)
    assert report.ok, dict(report.failures)
    assert has(report.notes, "matrix repair path", PATH)
    assert has(report.notes, "15 of 16 cells byte-identical", PATH)
    assert has(report.warnings, "orphaned", PATH)


def test_a_repaired_lattice_still_needs_a_fresh_perfect_fit(
    shop, mods, david
):
    """David's old checklist pinned the old lattice. It cannot carry."""
    shop.put(PATH, attest_matrix(mods, make_matrix_wig(WIG_ID), david))
    base = shop.merge("matrix wig on the shelf")

    repaired = make_matrix_wig(WIG_ID, repair=1)
    repaired["fittings"] = list(shop.read(PATH)["fittings"])  # stale only
    shop.put(PATH, repaired)
    report = shop.validate(PATH, base_ref=base)
    assert has(report.failures, "no perfect fit", PATH)
    assert has(report.warnings, "vouched for a different lattice", PATH)

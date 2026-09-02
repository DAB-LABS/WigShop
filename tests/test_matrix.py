"""Matrix wigs: the completeness hole, and the in-place repair path.

A matrix has thousands of cells and nobody presses thousands of
buttons, so its attestation is a CHECKLIST that samples the lattice.
Two consequences the shop has to handle itself, because HAIR does not.
"""

from __future__ import annotations

import pytest
from conftest import (
    Person,
    attest,
    attest_matrix,
    checklist_of,
    has,
    make_matrix_wig,
    make_wig,
    repair_cells,
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


def test_hair_now_refuses_a_one_row_bundle(mods):
    """The hole this file was written for, now closed upstream.

    Under 0.9.7 this asserted True: HAIR called a single signed claim
    over a sixteen-cell lattice complete, and the shop had to derive
    the dimension checklist itself to refuse it. The 0.14.0 pin fixes
    that, so the assertion is inverted rather than deleted.

    The shop's own check stays either way. Files minted by 0.9.7
    installs are still in the wild, and the shop must not depend on the
    pin to refuse them; if this ever asserts True again,
    ``test_the_shop_refuses_a_one_row_bundle`` is the only thing left
    standing between a forged bundle and the shelf.
    """
    import json

    wf, wfit = mods["wig_format"], mods["wig_fitting"]
    wig = attest_matrix(mods, make_matrix_wig(WIG_ID), Person("X"), rows=1)
    parsed = wf.parse_wig(json.dumps(wig)).wig
    bundle = wf.claims_of(parsed)[0]
    assert len(bundle.rows) == 1
    assert len(parsed.climate.cells) == 16
    assert wfit.bundle_is_complete(bundle, parsed) is False


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


# ---------------------------------------------------------------------------
# The receipt is a hint. Combing is the evidence.
# ---------------------------------------------------------------------------


def test_the_shop_combs_rather_than_reading_the_receipt(shop, mods, david):
    """A forged clean bill buys nothing.

    Until the 0.14.0 pin the shop read ``comb.suspects`` out of the file
    and believed it, which meant a wig could arrive carrying a clean
    bill nobody ever gave it. The first matrix the shop received stated
    zero suspects and combed to fifty-two, honestly enough -- its
    receipt was simply older than the check. But the same shape works
    on purpose, and nothing in a text file stops it.

    So the receipt is what the fitter saw, and the comb run here is
    what the shop decides on.
    """
    wig = make_matrix_wig(WIG_ID)
    # Two cells swap codes: each now sends its neighbour's, which no
    # dimension checklist samples and no signature can notice.
    cells = wig["climate"]["cells"]
    cells[0]["pronto"], cells[1]["pronto"] = (
        cells[1]["pronto"], cells[0]["pronto"],
    )
    wig["comb"] = {
        "version": 2, "date": "2026-09-01",
        "suspects": 0, "counts": {}, "findings": [],
    }
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.warnings, "combing found", PATH)
    assert has(report.warnings, "current enough to have known", PATH)


def test_an_older_receipt_is_not_accused_of_lying(shop, mods, david):
    """Version 1 predates the checks, so a disagreement is housekeeping.

    Every wig minted before HAIR 0.11.0 carries a version 1 receipt.
    Calling all of them discrepancies would cry wolf across the whole
    shelf and teach a reviewer to skim past the warning that matters.
    """
    wig = make_matrix_wig(WIG_ID)
    cells = wig["climate"]["cells"]
    cells[0]["pronto"], cells[1]["pronto"] = (
        cells[1]["pronto"], cells[0]["pronto"],
    )
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.notes, "older than the checks", PATH)
    assert not has(report.warnings, "current enough to have known", PATH)


def test_an_unreadable_lattice_does_not_read_as_a_clean_one(
    shop, mods, david
):
    """Silence on a lattice is the dangerous answer, so it is a warning.

    A flat remote gets frame self-consistency whatever its protocol, so
    a missing field map costs it nothing worth a line. A lattice is the
    opposite: the fitting attests fourteen cells out of hundreds, and
    with no map the field check cannot run either, which leaves the
    rest examined by nothing at all.
    """
    shop.put(PATH, attest_matrix(mods, make_matrix_wig(WIG_ID), david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.warnings, "no field map covers this lattice", PATH)
    assert has(report.warnings, "Unchecked is not the same as clean", PATH)


def test_a_flat_wig_is_not_nagged_about_field_maps(shop, mods, david):
    """The same silence on a flat remote is not worth saying.

    Almost no flat remote has a field map, and a line on every fan and
    television in the shop would bury the findings that matter.
    """
    flat = "wigs/bench/bench-fan-b-1.wig.json"
    shop.put(
        flat,
        attest(mods, make_wig("33333333-3333-4333-8333-333333333333"), david),
    )
    report = shop.validate()

    assert report.ok, report.failures
    assert not has(report.warnings, "field map", flat)
    assert not has(report.notes, "field map", flat)


# ---------------------------------------------------------------------------
# Repaired wigs: accept and report (owner ruling 2026-09-02)
# ---------------------------------------------------------------------------

REPAIRED = [("cool", "auto", 20), ("cool", "auto", 24)]


def test_a_repaired_wig_says_it_was_repaired(shop, mods, david):
    """A mended lattice and a captured one are not the same object.

    The reader cannot tell them apart from the outside, and only the
    file knows, so the shop says which one it is holding.
    """
    wig = repair_cells(
        make_matrix_wig(WIG_ID), REPAIRED,
        tested=["cool/auto/16", "heat/auto/30"],
    )
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.notes, "were repaired in HAIR", PATH)
    assert has(report.notes, "2 rule-derived", PATH)
    assert has(report.notes, "the file's word rather than proof", PATH)
    assert has(report.notes, "proved on air behind them", PATH)


def test_a_repair_does_not_cost_a_wig_the_gate(shop, mods, david):
    """Ruled: accept and report.

    The lattice already carries cells nobody pressed, because that is
    what a dimension checklist is. A repair run proves a sample on air
    and names it. Refusing the second while accepting the first would
    be inconsistent rather than careful.
    """
    wig = repair_cells(make_matrix_wig(WIG_ID), REPAIRED)
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert not has(report.warnings, "repair", PATH)


def test_an_accepted_repair_is_named_as_untransmitted(shop, mods, david):
    """The one-at-a-time path fires nothing, and that is worth saying."""
    wig = repair_cells(make_matrix_wig(WIG_ID), REPAIRED, tier="accepted")
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.notes, "accepted without a send", PATH)


def test_a_repair_with_no_tier_is_a_warning(shop, mods, david):
    """HAIR writes a tier on everything it mends.

    A record without one did not come from Detangle, so there is no
    saying whether anything was ever transmitted for it. That is the
    only repair shape the shop distrusts.
    """
    wig = make_matrix_wig(WIG_ID)
    repair_cells(wig, REPAIRED)
    for cell in wig["climate"]["cells"]:
        if "hair_repair" in cell:
            del cell["hair_repair"]["tier"]
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.warnings, "carry no tier", PATH)


def test_an_overridden_reading_is_surfaced_not_buried(shop, mods, david):
    """Somebody kept bytes HAIR read as something else.

    Allowed on purpose: a remote sends what its display shows, so a
    consistent mismatch is evidence about the field map rather than
    about the person pressing the button. Repeated overrides are how a
    provisional field gets ratified, which only works if a human reads
    them.
    """
    wig = repair_cells(make_matrix_wig(WIG_ID), REPAIRED, disagreed=True)
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.notes, "read them as something other", PATH)
    assert has(report.notes, "how a field map learns it is wrong", PATH)


def test_a_repair_trail_is_unsigned_and_the_shop_says_so(
    shop, mods, david
):
    """Nothing signs a repair record, so it is reported as a claim.

    ``canonical_cells_json`` builds the matrix hash from mode, fan,
    swing, temp and pronto only. Cell extras sit outside it on purpose,
    because two files differing by nothing but annotations have to hash
    alike or fittings would stop accumulating on one wig.

    The cost is that a repair trail can be stamped onto a finished,
    signed wig without disturbing anything: the cells_hash still
    matches, the signature still verifies, every gate still passes.
    That is worth pinning, because a repair record is a claim about
    human effort and this repo exists to make exactly those
    trustworthy.

    So the shop reports it the way it reports the comb receipt: as what
    the file says about itself.
    """
    wig = attest_matrix(mods, make_matrix_wig(WIG_ID), david)
    repair_cells(wig, REPAIRED)
    shop.put(PATH, wig)
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.notes, "the file's word rather than proof", PATH)


def test_a_repair_that_did_not_take_is_called_out(shop, mods, david):
    """The one thing about a repair the shop can check on its own.

    A cell somebody says they mended should stop being the cell combing
    complains about. Where it still is, the record is decoration,
    whether it was written in good faith or not.
    """
    wig = make_matrix_wig(WIG_ID)
    cells = wig["climate"]["cells"]
    # Two cells in one row end up sending the same code: a partial
    # collapse, which is the defect a whole flat row is not.
    cells[1]["pronto"] = cells[0]["pronto"]
    claimed = [(cells[1]["mode"], cells[1].get("fan"), cells[1].get("temp"))]
    repair_cells(wig, claimed)
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.warnings, "still flagged by combing", PATH)
    assert has(report.warnings, "the codes did not change", PATH)


def test_a_repair_that_took_is_not_accused(shop, mods, david):
    """The same check, the other way round, so it cannot pass vacuously.

    A wig whose repaired coordinates are clean gets the claim reported
    and nothing else. Without this, a cross-check that matched no keys
    at all would look identical to one that worked.
    """
    wig = repair_cells(make_matrix_wig(WIG_ID), REPAIRED)
    shop.put(PATH, attest_matrix(mods, wig, david))
    report = shop.validate()

    assert report.ok, report.failures
    assert has(report.notes, "were repaired in HAIR", PATH)
    assert not has(report.warnings, "still flagged by combing", PATH)

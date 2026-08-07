"""The entry gate, and everything the shop asks of one file's claims.

Perfect fits only, ruled 2026-08-04: a wig lands when at least one
person has claimed every row of it worked on their own hardware.
"""

from __future__ import annotations

import pytest
from conftest import Person, attest, has, make_wig

PATH = "wigs/bench/bench-fan-b-1.wig.json"
WIG_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def david():
    return Person("David", github="DAB-LABS")


@pytest.fixture
def mira():
    return Person("Mira", github="mira-h")


def test_a_perfect_fit_gets_in(shop, mods, david):
    wig = attest(mods, make_wig(WIG_ID), david)
    shop.put(PATH, wig)
    report = shop.validate()
    assert report.ok, report.failures


def test_no_fitting_at_all_is_refused(shop, mods):
    shop.put(PATH, make_wig(WIG_ID))
    report = shop.validate()
    assert has(report.failures, "no fitting", PATH)


def test_a_scoped_fitting_alone_cannot_open_the_door(shop, mods, david):
    """not_on_device is honest, and honesty is not a whole witness."""
    wig = attest(
        mods,
        make_wig(WIG_ID),
        david,
        verdicts={"Speed Low": "not_on_device"},
    )
    shop.put(PATH, wig)
    report = shop.validate()
    assert has(report.failures, "no perfect fit", PATH)
    assert has(report.failures, "'Speed Low'", PATH)


def test_union_coverage_is_not_a_perfect_fit(shop, mods, david, mira):
    """Three people who each proved a third have proved nobody whole."""
    wig = make_wig(WIG_ID)
    attest(mods, wig, david, verdicts={"Speed Low": "wont_work"})
    attest(mods, wig, mira, verdicts={"Power On": "wont_work"})
    shop.put(PATH, wig)
    report = shop.validate()
    assert has(report.failures, "no perfect fit", PATH)
    assert has(report.failures, "no single one of them", PATH)


def test_a_scoped_fitting_may_ride_alongside_a_perfect_one(
    shop, mods, david, mira
):
    """Wig-level, not bundle-level. The gate is the wig, not each bundle."""
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, mira, verdicts={"Speed Low": "not_on_device"})
    shop.put(PATH, wig)
    report = shop.validate()
    assert report.ok, report.failures


def test_legacy_fittings_are_refused_not_converted(shop, mods, david):
    wig = attest(mods, make_wig(WIG_ID), david)
    wig["fittings"].append(
        {
            "handle": "Someone",
            "content_hash": "sha256:" + "0" * 64,
            "date": "2026-07-01",
        }
    )
    shop.put(PATH, wig)
    report = shop.validate()
    assert has(report.failures, "pre-claims format", PATH)


def test_the_legacy_test_is_shape_not_the_format_stamp(shop, mods, david):
    """A file may stamp /3 and still carry an old-shape fitting."""
    wig = make_wig(WIG_ID)
    wig["fittings"].append(
        {"handle": "Someone", "content_hash": "sha256:" + "0" * 64}
    )
    shop.put(PATH, wig)
    report = shop.validate()
    assert wig["format"] == "hair-wig/3"
    assert has(report.failures, "pre-claims format", PATH)
    # And it is not also told it has no fitting, which would read as the
    # tool being confused about a file that visibly contains one.
    assert not has(report.failures, "no fitting.", PATH)


def test_a_bundle_moved_between_wigs_is_caught(shop, mods, david):
    """A signature covers the bundle, never the file it rides in."""
    wig = attest(mods, make_wig(WIG_ID), david)
    wig["wig_id"] = "22222222-2222-4222-8222-222222222222"
    shop.put(PATH, wig)
    report = shop.validate()
    assert has(report.failures, "attesting something else", PATH)


def test_an_altered_bundle_fails_its_signature(shop, mods, david):
    wig = attest(mods, make_wig(WIG_ID), david)
    wig["fittings"][0]["handle"] = "Someone Else"
    shop.put(PATH, wig)
    report = shop.validate()
    assert has(report.failures, "does not verify", PATH)


def test_an_unsigned_bundle_is_a_warning_not_a_failure(shop, mods, david):
    wig = attest(mods, make_wig(WIG_ID), david, sign=False)
    shop.put(PATH, wig)
    report = shop.validate()
    assert report.ok, report.failures
    assert has(report.warnings, "unsigned", PATH)


def test_two_bundles_on_one_key_are_refused(shop, mods, david):
    """One install, one current word. Since HAIR 0.9.7 a re-fit replaces."""
    wig = make_wig(WIG_ID)
    attest(mods, wig, david, date="2026-08-01")
    attest(mods, wig, david, date="2026-08-07", replace=False)
    shop.put(PATH, wig)
    report = shop.validate()
    assert has(report.failures, "share one signing key", PATH)


def test_two_davids_on_different_keys_are_two_people(shop, mods):
    """Handles carry no uniqueness. Never dedupe or count by handle."""
    one = Person("David", github="dab-labs", install="laptop")
    two = Person("David", github="other-dab", install="nuc")
    wig = make_wig(WIG_ID)
    attest(mods, wig, one)
    attest(mods, wig, two)
    shop.put(PATH, wig)
    report = shop.validate()
    assert report.ok, report.failures
    assert not has(report.warnings, "share one signing key", PATH)


def test_one_github_account_on_two_installs_is_flagged_for_promotion(
    shop, mods
):
    one = Person("David Bailey", github="DAB-LABS", install="laptop")
    two = Person("David B", github="dab-labs", install="nuc")
    wig = make_wig(WIG_ID)
    attest(mods, wig, one)
    attest(mods, wig, two)
    shop.put(PATH, wig)
    report = shop.validate()
    assert report.ok, report.failures
    assert has(report.warnings, "independent proof at promotion", PATH)


def test_wont_work_clustering_counts_keys(shop, mods):
    """Several fitters on one digest is a bad code, not a revision."""
    whole = Person("Whole", github="whole")
    a = Person("Ana", github="ana")
    b = Person("Bo", github="bo")
    wig = make_wig(WIG_ID)
    attest(mods, wig, whole)
    attest(mods, wig, a, verdicts={"Speed Low": "wont_work"})
    attest(mods, wig, b, verdicts={"Speed Low": "wont_work"})
    shop.put(PATH, wig)
    report = shop.validate()
    assert report.ok, report.failures
    assert has(report.warnings, "does not work on their hardware", PATH)


def test_one_wont_work_is_a_hardware_revision_not_a_flag(shop, mods, david):
    a = Person("Ana", github="ana")
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, a, verdicts={"Speed Low": "wont_work"})
    shop.put(PATH, wig)
    report = shop.validate()
    assert not has(report.warnings, "does not work on their hardware", PATH)


def test_a_wig_with_no_id_is_refused(shop, mods, david):
    wig = attest(mods, make_wig(WIG_ID), david)
    del wig["wig_id"]
    shop.put(PATH, wig)
    report = shop.validate()
    assert has(report.failures, "no wig_id", PATH)


def test_no_comb_receipt_warns(shop, mods, david):
    wig = attest(mods, make_wig(WIG_ID, comb=False), david)
    shop.put(PATH, wig)
    report = shop.validate()
    assert report.ok, report.failures
    assert has(report.warnings, "no comb receipt", PATH)


def test_a_missing_kind_warns(shop, mods, david):
    wig = attest(mods, make_wig(WIG_ID, kind=None), david)
    shop.put("wigs/bench/bench-b-1.wig.json", wig)
    report = shop.validate()
    assert report.ok, report.failures
    assert has(report.warnings, "no kind set")

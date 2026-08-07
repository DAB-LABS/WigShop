"""Filenames, brand folders, and the download that needs no rename.

HAIR 0.9.7 composes a download name from the wig's own fields --
``<brand>-<kind>-<model>[-<tier>].wig.json`` -- so a file drops into the
shop exactly as it left the closet. These tests pin that, because the
rename step was the single most common friction a contributor hit and
it is now the shop's job not to reintroduce it.
"""

from __future__ import annotations

import pytest
import validate_wigs as vw
from conftest import Person, attest, has, make_wig

WIG_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def david():
    return Person("David", github="DAB-LABS")


def check(path: str) -> vw.Report:
    report = vw.Report()
    vw.check_path_shape(path, report)
    return report


def test_the_shape_hair_composes_is_accepted():
    assert check("wigs/sanmli/sanmli-light-th-05.wig.json").ok


@pytest.mark.parametrize("tier", vw.TIER_SUFFIXES)
def test_a_tier_suffix_is_accepted_so_downloads_need_no_rename(tier):
    assert check(f"wigs/sanmli/sanmli-light-th-05{tier}.wig.json").ok


def test_the_tier_in_a_name_is_never_read_as_evidence(shop, mods, david):
    """A name that could promote a file by being edited defeats claims."""
    wig = attest(
        mods,
        make_wig(WIG_ID, brand="Bench", kind="fan", model="B-1"),
        david,
        verdicts={"Speed Low": "not_on_device"},
    )
    shop.put("wigs/bench/bench-fan-b-1-perfect-fit.wig.json", wig)
    report = shop.validate()
    assert has(report.failures, "no perfect fit")


def test_a_wrong_brand_prefix_is_refused():
    report = check("wigs/sanmli/candles-tea-light.wig.json")
    assert has(report.failures, "must start with the brand folder")


def test_unbranded_is_exempt_from_the_brand_prefix():
    """A wig with no brand has no brand to carry in its name.

    The prefix rule exists so a file sitting in somebody's Downloads
    says what it is for. HAIR falls back to the slug of the wig's name
    when there is no brand, so demanding an ``unbranded-`` prefix would
    send the first unbranded contributor off to rename a file for no
    reason at all.
    """
    assert check("wigs/unbranded/some-fan.wig.json").ok
    assert check("wigs/unbranded/unbranded-fan-b09xyz.wig.json").ok


def test_uppercase_is_refused():
    """macOS folds case and git does not, so two wigs could collide."""
    report = check("wigs/sanmli/Sanmli-Light-TH-05.wig.json")
    assert has(report.failures, "lowercase ascii")


def test_a_wig_outside_a_brand_folder_is_refused():
    report = check("wigs/loose.wig.json")
    assert has(report.failures, "wigs live at")


def test_unbranded_needs_a_product_identifier(shop, mods, david):
    wig = attest(mods, make_wig(WIG_ID, brand=None), david)
    shop.put("wigs/unbranded/bench-remote.wig.json", wig)
    report = shop.validate()
    assert has(report.failures, "at least one entry in identifiers")


def test_unbranded_with_an_identifier_is_fine(shop, mods, david):
    wig = attest(
        mods,
        make_wig(WIG_ID, brand=None, identifiers={"asin": "B0DF7FPV55"}),
        david,
    )
    shop.put("wigs/unbranded/bench-remote.wig.json", wig)
    report = shop.validate()
    assert report.ok, report.failures


def test_a_brand_field_that_disagrees_with_its_folder_warns(
    shop, mods, david
):
    wig = attest(mods, make_wig(WIG_ID, brand="Fujitsu General"), david)
    shop.put("wigs/fujitsu/fujitsu-fan-b-1.wig.json", wig)
    report = shop.validate()
    assert report.ok, report.failures
    assert has(report.warnings, "Worth confirming that is deliberate")


def test_the_same_codes_under_two_names_are_one_wig(shop, mods, david):
    first = attest(mods, make_wig(WIG_ID), david)
    second = attest(
        mods,
        make_wig("44444444-4444-4444-8444-444444444444", brand="Rebadge"),
        david,
    )
    shop.put("wigs/bench/bench-fan-b-1.wig.json", first)
    shop.put("wigs/rebadge/rebadge-fan-b-1.wig.json", second)
    report = shop.validate()
    assert has(report.failures, "identical codes to")

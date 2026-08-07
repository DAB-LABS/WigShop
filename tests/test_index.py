"""INDEX.md: two numbers, both counted by signing key.

Fittings counts perfect fits, which under the perfect-only gate is
every wig on the shelf by at least one. Fitters counts everybody who
attested, whole or partial, so the gap between them is the honest
partial attestations riding alongside.
"""

from __future__ import annotations

import pytest
from conftest import Person, attest, make_wig

PATH = "wigs/bench/bench-fan-b-1.wig.json"
WIG_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def david():
    return Person("David", github="DAB-LABS")


def row_for(shop, name: str) -> str:
    return next(
        line
        for line in shop.index().splitlines()
        if line.startswith("|") and name in line
    )


def test_a_lone_perfect_fit_reads_one_and_one(shop, mods, david):
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    row = row_for(shop, "Bench Remote")
    assert "| 1 | 1 |" in row
    assert "David" in row


def test_a_scoped_fitting_lifts_fitters_but_not_fittings(shop, mods, david):
    mira = Person("Mira", github="mira-h")
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, mira, verdicts={"Speed Low": "not_on_device"})
    shop.put(PATH, wig)
    row = row_for(shop, "Bench Remote")
    assert "| 1 | 2 |" in row
    # Fitted by names whole witnesses only.
    assert "Mira" not in row


def test_both_numbers_count_keys_not_handles(shop, mods):
    """Two people called David are two people when their keys differ."""
    one = Person("David", github="dab-one", install="laptop")
    two = Person("David", github="dab-two", install="nuc")
    wig = make_wig(WIG_ID)
    attest(mods, wig, one)
    attest(mods, wig, two)
    shop.put(PATH, wig)
    row = row_for(shop, "Bench Remote")
    assert "| 2 | 2 |" in row


def test_the_covered_column_is_gone(shop, mods, david):
    """It read 12/12 on every row forever, which is noise as information."""
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    index = shop.index()
    assert "Covered" not in index
    assert "| Fittings | Fitters |" in index


def test_an_empty_shelf_says_so(shop):
    assert "No wigs yet" in shop.index()


def test_an_unreadable_file_is_named_not_dropped(shop, mods, david):
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    shop.put_text("wigs/bench/bench-fan-b-2.wig.json", "{ not json")
    index = shop.index()
    assert "Not readable" in index
    assert "bench-fan-b-2" in index


def test_a_shelf_of_only_unreadable_files_is_not_an_empty_shop(shop):
    """One unreadable wig in a corpus of one once rendered the empty state."""
    shop.put_text(PATH, "{ not json")
    index = shop.index()
    assert "No wigs yet" not in index
    assert "Not readable" in index

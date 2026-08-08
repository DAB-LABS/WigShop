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


def test_king_of_the_hill(shop, mods):
    """The whole promotion mechanic, in one test.

    Proof accumulates on a wig while its content is stable, and a
    successor starts over at one. That reset is not a problem to be
    engineered around, it IS the cost of dethroning: a challenger who
    replaces a four-fitting wig has to earn four again.

    Nothing here is stored or carried. The count is derived from the
    file on every rebuild, so a successor reads one because its
    fittings array holds exactly one bundle, not because anything was
    reset. That is why the mechanic costs nothing to run.
    """
    heir_id = "22222222-2222-4222-8222-222222222222"
    people = [
        Person(name, github=name.lower())
        for name in ("David", "Mira", "Ade", "Jo")
    ]

    def fittings() -> int:
        row = next(
            line for line in shop.index().splitlines()
            if line.startswith("|") and "Bench Remote" in line
        )
        return int(row.split("|")[5].strip())

    wig = make_wig(WIG_ID)
    climb = []
    for person in people:
        attest(mods, wig, person)
        shop.put(PATH, wig)
        climb.append(fittings())
    assert climb == [1, 2, 3, 4]

    # Somebody repairs a code. New description, new wig, nobody has
    # proven it yet -- including the three people who proved its parent.
    heir = make_wig(heir_id, ditto=[1, 0, 0], supersedes=[WIG_ID])
    attest(mods, heir, people[1])
    shop.put(PATH, heir)
    assert fittings() == 1

    for person in people[2:]:
        attest(mods, heir, person)
    shop.put(PATH, heir)
    assert fittings() == 3

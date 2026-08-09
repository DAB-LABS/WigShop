"""INDEX.md: one number, counted by signing key.

Fittings counts perfect fits, which under the perfect-only gate is
every wig on the shelf by at least one. There is no second column: the
gate and the rating are the same thing, so a second number would only
invite the reader to wonder why they differ.
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


def test_a_lone_perfect_fit_reads_one(shop, mods, david):
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    row = row_for(shop, "Bench Remote")
    assert "| 1 |" in row
    assert "David" in row


def test_a_partial_fitting_moves_nothing(shop, mods, david):
    """It never could. The count has only ever been perfect fits."""
    mira = Person("Mira", github="mira-h")
    wig = make_wig(WIG_ID)
    attest(mods, wig, david)
    attest(mods, wig, mira, verdicts={"Speed Low": "not_on_device"})
    shop.put(PATH, wig)
    row = row_for(shop, "Bench Remote")
    assert "| 1 |" in row
    # Fitted by names whole witnesses only.
    assert "Mira" not in row


def test_the_count_is_keys_not_handles(shop, mods):
    """Two people called David are two people when their keys differ."""
    one = Person("David", github="dab-one", install="laptop")
    two = Person("David", github="dab-two", install="nuc")
    wig = make_wig(WIG_ID)
    attest(mods, wig, one)
    attest(mods, wig, two)
    shop.put(PATH, wig)
    assert "| 2 |" in row_for(shop, "Bench Remote")


def test_there_is_exactly_one_number(shop, mods, david):
    """Covered went for reading 12/12 forever; Fitters would have read
    the same as Fittings forever, which is the same fault twice."""
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    index = shop.index()
    assert "Covered" not in index
    assert "Fitters" not in index
    assert "| Fittings | Fitted by |" in index


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
        """Read the Fittings cell, finding the column by its heading.

        Hardcoding the index would keep passing against the wrong number
        the day a column moves, which is exactly the sort of quiet wrong
        answer this whole suite exists to prevent.
        """
        lines = shop.index().splitlines()
        header = next(x for x in lines if x.startswith("| Brand |"))
        column = [c.strip() for c in header.split("|")].index("Fittings")
        row = next(
            x for x in lines
            if x.startswith("|") and "Bench Remote" in x
        )
        return int(row.split("|")[column].strip())

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

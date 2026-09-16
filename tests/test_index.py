"""INDEX.md: two numbers, and they count different things.

**Fittings** counts perfect fits by signing key, which is what
WigFactory watches and what the promotion story rests on. It has not
changed meaning. Since the gate came off on 2026-09-14 a zero there is
an ordinary value rather than an impossible one.

**Proven** counts rows anybody has proven. It exists because a wig
where somebody proved most of it and a wig nobody has touched are now
the same tier, and letting those render identically would throw away
real work. The two are separate columns precisely so a reader who
compares them learns something true.
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


def cell(shop, name: str, column: str) -> str:
    """One cell, found by its column heading rather than its position.

    Hardcoding an index keeps passing against the wrong number the day
    a column moves, which is the sort of quiet wrong answer this suite
    exists to prevent.
    """
    lines = shop.index().splitlines()
    header = next(x for x in lines if x.startswith("| Brand |"))
    where = [c.strip() for c in header.split("|")].index(column)
    row = next(x for x in lines if x.startswith("|") and name in x)
    return row.split("|")[where].strip()


# ---------------------------------------------------------------------------
# A wig with no fitting at all
# ---------------------------------------------------------------------------


def test_a_fitted_wig_reads_zero_with_no_fitter_named(shop, mods):
    """Zero is a real value now, not an impossible one."""
    shop.put(PATH, make_wig(WIG_ID))
    assert cell(shop, "Bench Remote", "Fittings") == "0"
    assert cell(shop, "Bench Remote", "Fitted by") == ""


def test_fitted_wigs_sort_below_perfectly_fitted_ones(shop, mods, david):
    """Most proven first, and the brand tiebreak must not override it.

    Alpha sorts before Zeta alphabetically, so a sort that had quietly
    become alphabetical would put the unproven wig on top.
    """
    alpha = make_wig(
        "33333333-3333-4333-8333-333333333333",
        name="Alpha Remote",
        brand="Alpha",
        model="A-1",
    )
    zeta = attest(
        mods,
        make_wig(
            "44444444-4444-4444-8444-444444444444",
            name="Zeta Remote",
            brand="Zeta",
            model="Z-1",
        ),
        david,
    )
    shop.put("wigs/alpha/alpha-fan-a-1.wig.json", alpha)
    shop.put("wigs/zeta/zeta-fan-z-1.wig.json", zeta)

    lines = [
        line for line in shop.index().splitlines()
        if line.startswith("|") and "Remote]" in line
    ]
    assert "Zeta Remote" in lines[0]
    assert "Alpha Remote" in lines[1]


# ---------------------------------------------------------------------------
# The Proven column
# ---------------------------------------------------------------------------


def test_the_proven_column_counts_rows_not_people(shop, mods, david):
    """Signed partial work stays visible even though it has no tier."""
    wig = make_wig(WIG_ID, rows=7)
    attest(
        mods,
        wig,
        david,
        verdicts={
            "Speed High": "not_on_device",
            "Oscillate": "wont_work",
        },
    )
    shop.put(PATH, wig)
    assert cell(shop, "Bench Remote", "Fittings") == "0"
    assert cell(shop, "Bench Remote", "Proven") == "5 of 7"


def test_the_proven_column_is_blank_for_a_perfect_fit(shop, mods, david):
    """The Fittings column has already said it."""
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    assert cell(shop, "Bench Remote", "Fittings") == "1"
    assert cell(shop, "Bench Remote", "Proven") == ""


def test_the_proven_column_is_blank_when_nobody_has_claimed_anything(
    shop, mods
):
    """An absence, not a finding.

    Printing "0 of 3" on a wig nobody has touched would read as a mark
    against it, which is the one thing the gate change was made to stop.
    """
    shop.put(PATH, make_wig(WIG_ID))
    assert cell(shop, "Bench Remote", "Proven") == ""


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


def test_the_second_number_earns_its_place(shop, mods, david):
    """Two numbers now, and the old objection to a second one expired.

    A column called Covered was rejected once for reading 12/12
    forever, and Fitters for reading the same as Fittings forever. Both
    faults were the same fault: a column that cannot vary teaches a
    reader nothing and invites them to wonder why two numbers differ
    when they never do.

    Under the perfect-only gate every wig on the shelf was covered
    whole, so Covered could not vary. That gate is gone, a wig can now
    sit on the shelf at 5 of 7, and the column varies. So it is kept,
    under a name that says what it counts, and the two rejected names
    stay rejected because they still describe nothing.
    """
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    index = shop.index()
    assert "Covered" not in index
    assert "Fitters" not in index
    assert "| Fittings | Proven | Fitted by |" in index

    # It varies, which is the whole argument for it existing.
    partial = make_wig(
        "55555555-5555-4555-8555-555555555555",
        name="Partial Remote",
        brand="Partial",
        model="P-1",
        rows=7,
    )
    attest(mods, partial, david, verdicts={"Oscillate": "wont_work"})
    shop.put("wigs/partial/partial-fan-p-1.wig.json", partial)
    assert cell(shop, "Partial Remote", "Proven") == "6 of 7"
    assert cell(shop, "Bench Remote", "Proven") == ""


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

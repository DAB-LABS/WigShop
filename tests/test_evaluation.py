"""The evaluation file: one artifact, English first, facts after.

It never posts anything and it never decides anything. Everything here
is about whether what the checks found survives the trip into a file
intact, because the whole reason the file exists is so a reviewing
agent takes facts instead of parsing prose back out of sentences.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from conftest import (
    Person,
    attest,
    attest_matrix,
    make_matrix_wig,
    make_wig,
    repair_cells,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import evaluate as ev

PATH = "wigs/bench/bench-fan-b-1.wig.json"
MATRIX = "wigs/bench/bench-ac-a-1.wig.json"
WIG_ID = "11111111-1111-4111-8111-111111111111"
AC_ID = "aaaa1111-1111-4111-8111-111111111111"


@pytest.fixture
def david():
    return Person("David", github="DAB-LABS")


def evaluate(shop, paths, pr=7):
    """Render an evaluation for a shop, the way CI would."""
    report = shop.validate(*paths) if paths else shop.validate()
    block = ev.facts(report, list(paths), pr, "v0.14.0")
    return block, ev.render(block, report, None)


def test_a_clean_wig_says_so_and_carries_no_findings(shop, mods, david):
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    block, text = evaluate(shop, [PATH])

    assert block["verdict"] in ("accept", "accept-with-notes")
    assert "# Evaluation: PR #7" in text
    assert PATH in text


def test_the_facts_block_round_trips(shop, mods, david):
    """A reader has to get back exactly what was written.

    The block is the contract. If it cannot be parsed out of the file
    it lives in, the delta on the next run has nothing to compare
    against and the artifact is decoration.
    """
    shop.put(MATRIX, attest_matrix(mods, make_matrix_wig(AC_ID), david))
    block, text = evaluate(shop, [MATRIX])

    parsed = json.loads(text.split("```json\n")[1].split("\n```")[0])
    assert parsed == block
    assert parsed["schema"] == ev.SCHEMA
    assert parsed["pr"] == 7


def test_a_refusal_cannot_be_rounded_up(shop, mods, david):
    """The verdict is computed, and it is the one word that must hold.

    A reviewing agent is handed this rather than asked to judge, so
    the value has to be there rather than inferred from whether some
    list happens to be empty.
    """
    wig = make_wig(WIG_ID)
    wig["fittings"] = []
    shop.put(PATH, wig)
    block, text = evaluate(shop, [PATH])

    assert block["verdict"] == "refuse"
    assert "**Verdict: not accepted.**" in text
    assert "Refused" in text


def test_warnings_make_it_the_middle_verdict(shop, mods, david):
    """Accepted with things to read is a value, not a shade of accepted."""
    shop.put(MATRIX, attest_matrix(mods, make_matrix_wig(AC_ID), david))
    block, _ = evaluate(shop, [MATRIX])

    # An unmapped lattice protocol warns, which is the whole point of it.
    assert block["verdict"] == "accept-with-notes"


def test_coded_findings_carry_their_structure(shop, mods, david):
    """params and keys ride along, or the barber has only prose again."""
    wig = repair_cells(
        make_matrix_wig(AC_ID), [("cool", "auto", 20)], tier="accepted"
    )
    shop.put(MATRIX, attest_matrix(mods, wig, david))
    block, _ = evaluate(shop, [MATRIX])

    findings = block["wigs"][0]["findings"]
    claimed = next(f for f in findings if f.get("code") == "repair.claimed")
    assert claimed["params"]["records"] == 1
    assert claimed["params"]["tiers"] == {"accepted": 1}
    assert claimed["level"] == "note"
    assert claimed["text"]


def test_findings_with_no_code_still_reach_the_file(shop, mods, david):
    """Most of the shop's sixty-odd messages have no code yet.

    Dropping them until somebody names them would make the evaluation
    quietly incomplete, which is worse than a finding with no short
    name.
    """
    wig = make_wig(WIG_ID)
    wig["fittings"] = []
    shop.put(PATH, wig)
    block, _ = evaluate(shop, [PATH])

    findings = block["wigs"][0]["findings"]
    assert any("code" not in f for f in findings)
    assert all(f["text"] for f in findings)


def test_only_the_wigs_the_pull_request_touches(shop, mods, david):
    """Owner ruling 2026-09-02.

    A shelf-wide evaluation would bury the one file somebody is waiting
    on underneath everything that was already there.
    """
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    shop.put(MATRIX, attest_matrix(mods, make_matrix_wig(AC_ID), david))
    block, text = evaluate(shop, [MATRIX])

    assert [w["path"] for w in block["wigs"]] == [MATRIX]
    assert PATH not in text


# ---------------------------------------------------------------------------
# The delta, which is the point of keeping the artifacts
# ---------------------------------------------------------------------------


def test_the_delta_names_what_cleared_and_what_is_new():
    before = {
        "verdict": "accept-with-notes",
        "wigs": [{"path": "wigs/a/x.wig.json", "findings": [
            {"code": "comb.suspects", "level": "warn", "text": "..."},
            {"code": "comb.receipt-stale", "level": "note", "text": "..."},
        ]}],
    }
    after = {
        "verdict": "accept",
        "wigs": [{"path": "wigs/a/x.wig.json", "findings": [
            {"code": "repair.claimed", "level": "note", "text": "..."},
        ]}],
    }
    lines = "\n".join(ev.since_last_time(before, after))

    assert "moved from" in lines
    assert "cleared: comb.receipt-stale, comb.suspects" in lines
    assert "new: repair.claimed" in lines


def test_the_delta_counts_uncoded_findings_rather_than_quoting_them():
    """A sentence is not a name.

    The first version of this spliced whole finding texts into a
    comma-joined list and produced a paragraph nobody could read.
    """
    long_text = "a very long sentence about something that went wrong " * 3
    before = {"verdict": "accept", "wigs": [
        {"path": "wigs/a/x.wig.json", "findings": []}]}
    after = {"verdict": "accept", "wigs": [
        {"path": "wigs/a/x.wig.json",
         "findings": [{"level": "note", "text": long_text}]}]}
    lines = "\n".join(ev.since_last_time(before, after))

    assert "other findings: 0 to 1" in lines
    assert long_text not in lines


def test_an_unchanged_resubmission_says_nothing_changed():
    block = {"verdict": "accept", "wigs": [
        {"path": "wigs/a/x.wig.json", "findings": [
            {"code": "comb.suspects", "level": "warn", "text": "..."}]}]}
    lines = "\n".join(ev.since_last_time(block, dict(block)))

    assert "Still **accepted**" in lines
    assert "No finding changed" in lines


def test_a_previous_evaluation_is_read_back_out_of_its_own_file(
    tmp_path, shop, mods, david
):
    """The artifact from the last run is the input to the next one."""
    shop.put(PATH, attest(mods, make_wig(WIG_ID), david))
    block, text = evaluate(shop, [PATH])
    written = tmp_path / "evaluation.md"
    written.write_text(text, encoding="utf-8")

    assert ev.read_previous(written) == block


def test_a_missing_previous_is_not_an_error(tmp_path):
    """First run of a pull request has nothing to compare against."""
    assert ev.read_previous(tmp_path / "nope.md") is None

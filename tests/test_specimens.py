"""Two real HAIR 0.9.7 downloads, checked verbatim.

Everything else in this suite is built by the fixtures. These two files
came off an actual install through the 0.9.7 save flow and are stored
byte-for-byte, so if HAIR's serializer, signer or digest ever drifts
from what the shop reproduces, these are the tests that notice.

They also happen to be the first files that carry ``supersedes`` on a
submission that replaces nothing, which is the shape the 0.9.7 addendum
warned would otherwise bounce.
"""

from __future__ import annotations

import json

from conftest import FIXTURES, has

SPECIMENS = {
    "wigs/fable/fable-fan-ft-9000-perfect-fit.wig.json": (
        "fable-fan-ft-9000-perfect-fit"
    ),
    "wigs/test/test-test-model-perfect-fit.wig.json": (
        "test-test-model-perfect-fit"
    ),
}


def place(shop) -> None:
    for path, name in SPECIMENS.items():
        shop.put_text(
            path, (FIXTURES / f"{name}.wig.json").read_text(encoding="utf-8")
        )


def test_both_specimens_pass_as_fresh_submissions(shop):
    place(shop)
    report = shop.validate()
    assert report.ok, dict(report.failures)


def test_their_signatures_verify_against_hair(mods):
    for name in SPECIMENS.values():
        raw = json.loads(
            (FIXTURES / f"{name}.wig.json").read_text(encoding="utf-8")
        )
        for entry in raw["fittings"]:
            assert (
                mods["fitting_signing"].verify_fitting(entry)
                == mods["fitting_signing"].SIGNED_VALID
            ), name


def test_each_specimen_is_a_perfect_fit_by_hairs_own_judgment(mods):
    wf, wfit = mods["wig_format"], mods["wig_fitting"]
    for name in SPECIMENS.values():
        text = (FIXTURES / f"{name}.wig.json").read_text(encoding="utf-8")
        wig = wf.parse_wig(text).wig
        assert wfit.claims_summary(wig, None)["state"] == "perfect", name


def test_the_download_name_is_the_shop_path(mods):
    """The rename step is gone, and this is the test that keeps it gone."""
    wf = mods["wig_format"]
    for path, name in SPECIMENS.items():
        text = (FIXTURES / f"{name}.wig.json").read_text(encoding="utf-8")
        wig = wf.parse_wig(text).wig
        assert wf.download_filename(wig) == path.rsplit("/", 1)[1], name


def test_their_ancestry_names_wigs_the_shop_has_never_seen(shop):
    """Local-only lineage. Silent, not a wrong-ancestor flag."""
    place(shop)
    base = shop.merge("empty shelf")
    shop.merge("nothing changed")
    report = shop.validate(base_ref=base)
    assert report.ok, dict(report.failures)
    assert not has(report.warnings, "wrong ancestor")
    assert not has(report.warnings, "cannot trace")


def test_a_specimen_carries_supersedes(mods):
    wf = mods["wig_format"]
    for name in SPECIMENS.values():
        text = (FIXTURES / f"{name}.wig.json").read_text(encoding="utf-8")
        assert wf.parse_wig(text).wig.supersedes, name

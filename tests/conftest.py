"""Shared machinery for the shop's tests.

The shop imports HAIR's format modules rather than reimplementing them,
so the tests do too: they build wigs and sign bundles through HAIR's own
serializers, which means a test that passes here is a statement about
what a real install would write, not about a shape invented in a
fixture.

Point ``HAIR_SRC`` at a HAIR checkout, or run from a repo root holding
one at ``.hair`` (which is where CI puts it).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import build_index as bi
import validate_wigs as vw

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def hair_src() -> str:
    configured = os.environ.get("HAIR_SRC")
    if configured:
        return configured
    default = REPO_ROOT / ".hair"
    if (default / "custom_components" / "hair" / "wig_format.py").exists():
        return str(default)
    pytest.skip(
        "no HAIR checkout: set HAIR_SRC, or clone HAIR to .hair in the "
        "repo root"
    )


@pytest.fixture(scope="session")
def mods():
    return vw.load_hair(hair_src())


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


class Person:
    """A fitter: one install, one ed25519 key, one typed handle.

    Keys are derived from the name so a fixture is reproducible and a
    failure is readable. Two Persons with the same name are the same
    install on purpose; that is how the tests exercise the 0.9.7 rule
    that a re-fit from one key replaces rather than appends.
    """

    def __init__(
        self, name: str, github: str | None = None, install: str = ""
    ):
        self.handle = name
        self.github = github
        seed = hashlib.sha256(f"{name}/{install}".encode()).digest()
        self.private_b64 = base64.b64encode(seed).decode("ascii")

    @property
    def public_b64(self) -> str:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        private = Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(self.private_b64)
        )
        return base64.b64encode(
            private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode("ascii")


# ---------------------------------------------------------------------------
# Wigs
# ---------------------------------------------------------------------------

def _specimen(name: str) -> dict:
    """A real HAIR 0.9.7 download, read verbatim from fixtures."""
    return json.loads(
        (FIXTURES / f"{name}.wig.json").read_text(encoding="utf-8")
    )


# Real Pronto codes, lifted from a real HAIR 0.9.7 download rather than
# invented, so the validator's Pronto checks have something legitimate
# to chew on and every fixture row has a distinct transmit recipe.
_SOURCE = _specimen("fable-fan-ft-9000-perfect-fit")
PRONTOS = [signal["pronto"] for signal in _SOURCE["signals"]]
ALIASES = [signal["alias"] for signal in _SOURCE["signals"]]


def make_wig(
    wig_id: str,
    *,
    name: str = "Bench Remote",
    brand: str | None = "Bench",
    kind: str | None = "fan",
    model: str | None = "B-1",
    rows: int = 3,
    supersedes: list[str] | None = None,
    aliases: list[str] | None = None,
    prontos: list[str] | None = None,
    ditto: list[int] | None = None,
    identifiers: dict | None = None,
    comb: bool = True,
) -> dict:
    """A hair-wig/3 wig as a plain dict, ready to be signed and dumped."""
    if prontos is None and rows > len(PRONTOS):
        # Recycling a code would give two rows one digest, which is a
        # real thing devices do and a terrible accident in a fixture:
        # one claim satisfies both rows, so a test meant to be about
        # something else quietly becomes a test about duplicate
        # payloads. test_duplicate_payloads.py covers that on purpose.
        raise ValueError(
            f"only {len(PRONTOS)} distinct codes available; pass prontos="
        )
    aliases = aliases or ALIASES[:rows]
    prontos = prontos or PRONTOS[:rows]
    ditto = ditto or [0] * rows
    wig: dict = {
        "format": "hair-wig/3",
        "name": name,
        "wig_id": wig_id,
        "signals": [
            {
                "alias": aliases[i],
                "pronto": prontos[i],
                "ditto_count": ditto[i],
                "bypass_protocol": False,
            }
            for i in range(rows)
        ],
        "fittings": [],
    }
    for key, value in (
        ("brand", brand),
        ("kind", kind),
        ("model", model),
        ("identifiers", identifiers),
    ):
        if value:
            wig[key] = value
    if supersedes:
        wig["supersedes"] = list(supersedes)
    if comb:
        wig["comb"] = {
            "version": 1,
            "date": "2026-08-07",
            "suspects": 0,
            "counts": {},
            "findings": [],
        }
    return wig


def row_digest(mods, signal: dict) -> str:
    return mods["wig_format"].row_digest(
        signal["pronto"],
        signal.get("ditto_count", 0),
        signal.get("bypass_protocol", False),
    )


def attest(
    mods,
    wig: dict,
    person: Person,
    *,
    verdicts: dict[str, str] | None = None,
    sign: bool = True,
    date: str = "2026-08-07",
    replace: bool = True,
) -> dict:
    """Add ``person``'s claims bundle to ``wig`` and return the wig.

    Defaults to ``worked`` on every row, which is a perfect fit. Pass
    ``verdicts`` keyed by alias to exclude rows.

    ``replace`` models the HAIR 0.9.7 rule: one install has one current
    word on one wig, so re-attesting replaces the earlier bundle rather
    than stacking a second. Pass False to build the hand-edited file the
    invariant is supposed to catch.
    """
    verdicts = verdicts or {}
    entry: dict = {
        "wig_id": wig["wig_id"],
        "handle": person.handle,
        "date": date,
        "rows": [
            {
                "alias_at_claim": signal["alias"],
                "digest": row_digest(mods, signal),
                "verdict": verdicts.get(signal["alias"], "worked"),
            }
            for signal in wig["signals"]
        ],
    }
    if person.github:
        entry["github"] = person.github
    # HAIR writes handle/github/date/note/cells_hash before rows; the
    # signature is over sorted keys either way, but keeping the order
    # honest keeps the fixtures readable.
    if sign:
        mods["fitting_signing"].sign_fitting(entry, person.private_b64)
    if replace:
        wig["fittings"] = [
            e
            for e in wig["fittings"]
            if e.get("key") != entry.get("key") or entry.get("key") is None
        ]
    wig["fittings"].append(entry)
    return wig


def dump(wig: dict) -> str:
    return json.dumps(wig, indent=4) + "\n"


# ---------------------------------------------------------------------------
# A shop, in a temp dir, with git
# ---------------------------------------------------------------------------


class Shop:
    """A throwaway WigShop checkout the base-ref checks can run against."""

    def __init__(self, root: Path):
        self.root = root
        (root / "wigs").mkdir(parents=True, exist_ok=True)
        self._git("init", "-q", ".")
        self._git("config", "user.email", "bench@example.invalid")
        self._git("config", "user.name", "bench")
        self._git("commit", "-q", "--allow-empty", "-m", "empty shelf")

    def _git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def put(self, rel_path: str, wig: dict) -> None:
        target = self.root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dump(wig), encoding="utf-8")

    def put_text(self, rel_path: str, text: str) -> None:
        target = self.root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def remove(self, rel_path: str) -> None:
        (self.root / rel_path).unlink()

    def merge(self, message: str = "shelf") -> str:
        """Commit everything as the merged state, and return the ref."""
        self._git("add", "-A")
        self._git("commit", "-q", "--allow-empty", "-m", message)
        return self._git("rev-parse", "HEAD").strip()

    def validate(self, *files: str, base_ref: str | None = None):
        """Run the validator the way CI runs it. Returns a Report."""
        report = vw.Report()
        mods = vw.load_hair(hair_src())
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            targets = list(files) or vw.discover(self.root)
            hashes: dict[str, list[str]] = {}
            for rel_path in targets:
                full = self.root / rel_path
                if not full.exists():
                    continue
                report.checked += 1
                text = full.read_text(encoding="utf-8")
                brand = vw.check_path_shape(rel_path, report)
                checked = vw.check_wig(rel_path, text, brand, mods, report)
                if checked is not None:
                    hashes.setdefault(checked[1], []).append(rel_path)
                if base_ref:
                    vw.check_against_base(
                        rel_path, text, base_ref, mods, report
                    )
            vw.check_shelf(self.root, base_ref, mods, report)
            vw.check_duplicates(
                self.root,
                hashes,
                set(files) if files else None,
                mods,
                report,
            )
        finally:
            os.chdir(cwd)
        return report

    def index(self) -> str:
        return bi.build(self.root, vw.load_hair(hair_src()))


@pytest.fixture
def shop(tmp_path) -> Shop:
    return Shop(tmp_path / "shop")


# ---------------------------------------------------------------------------
# Reading a Report
# ---------------------------------------------------------------------------


def messages(bucket: dict, path: str | None = None) -> list[str]:
    if path is not None:
        return list(bucket.get(path, []))
    return [m for entries in bucket.values() for m in entries]


def has(bucket: dict, needle: str, path: str | None = None) -> bool:
    return any(needle in m for m in messages(bucket, path))

# The Wig Shop

Proven infrared code sets for [HAIR](https://github.com/DAB-LABS/HAIR), the barbershop for your smart home's IR devices.

A **wig** is one JSON file holding one remote's codes. Download one, drop it on HAIR's Closet, and you have that remote.

**One rule gets a wig in here: one person proved every code in it, on their own hardware.**

That is what makes this different from a code database. Nothing lands in this repo until a named person pointed a blaster at the real device, worked through every button, and signed for what they saw. If a wig is here, somebody watched the whole thing work.

---

## What this is not

This is not a database, and HAIR does not fetch anything from it. There is no index HAIR calls, no lookup, no phoning home. You download a file, you drop it on the Closet, exactly like any other file. The shop is a place people put things, not a service.

It is also not comprehensive and never will be. It covers whatever people proved. That is the whole promise, and it is a small one on purpose.

---

## Using a wig

1. Find the brand folder under [`wigs/`](wigs/), or search [`INDEX.md`](INDEX.md) by brand, kind or product identifier.
2. Download the `.wig.json` file.
3. In Home Assistant, open HAIR, go to the **Closet**, and drop the file on the drop bar.
4. **ADOPT** turns it into a working device, or **CLIP** opens it on the Clipper if you want to look before you commit.

If it works for you, come back and prove it. Your fitting is a vote: it tells the next person this wig is worth downloading, and it is what eventually turns a file in a folder into a real Home Assistant integration.

---

## The fitting

A fitting is the record of somebody proving a wig. The proving ground is the device, not a dialog: you adopt the wig, live with it, and when it has earned your trust you press **SAVE TO CLOSET** and choose **Validate for Perfect Fit**. That opens a checklist -- every command a row, with a TEST button on each -- and you tick what you actually proved.

Fittings ride inside the wig file. One file carries the codes and every proof anyone has recorded against them.

Three things make a fitting worth something:

**It is per row.** Not "this wig works" but "these forty buttons work, one at a time, and I pressed all of them."

**It is bound to the recipe, not to the file.** Each claim carries a digest of one row's transmit recipe: the bytes, the repeat frames appended to them, and whether the encoder is bypassed. Fix one bad code later and only that row's claims retire. Everything else anyone proved still stands, and renaming a button costs nothing, because names were never in the digest.

**It is signed.** HAIR signs with a key generated on your install. The signature proves the record has not been altered since you made it, and that fittings sharing a key came from one install. Identity is the key, not the typed name: two people who both type "David" are two people, and one person re-fitting the same wig replaces their own earlier word rather than stacking a second.

Fittings are social proof, not identity. The handle is what you typed. Nobody is claiming more than that.

**Perfect fits only.** A wig lands here when one person's claims cover every row of it. A file where three people each proved a third is a file nobody has watched work end to end, and that is not the same thing at all.

**It is king of the hill.** One wig per device sits on the shelf, and it stays there until something better takes its place. If you think yours is the better description of that device, prove all of it and send it up. If it is not better, the one already there wins, and the best thing you can do is put your name on it.

---

## Contributing

Everything here is one file. Download it from HAIR, open a pull request, tick the declaration. Full detail in [CONTRIBUTING.md](CONTRIBUTING.md).

### A wig nobody has posted yet

You need your own perfect fit first: every row proven, by you, in one attestation.

1. Adopt the wig in HAIR and use it until you trust it.
2. **SAVE TO CLOSET**, then **Validate for Perfect Fit**, and work the checklist.
3. Download it from the Closet. The filename will say `-perfect-fit` when it is ready.
4. Open a pull request adding it at `wigs/<brand>/<that filename>`, and tick the declaration.

HAIR names the download from the wig's own fields, which is the same shape this repo files under, so you should not need to rename anything.

### A fitting on a wig that is already here

**This is the most valuable thing you can do here,** and it is the same one file.

1. **Download the current wig from this repo**, not an older copy you already had. It carries everyone else's fittings, and you want yours added to theirs rather than replacing them.
2. Drop it on the Closet, adopt it, live with it, then fit it.
3. Download it again and open a pull request replacing that same file.

The checks confirm no existing fitting went missing. If one did, you fitted an older copy, and the pull request is refused with that reason rather than quietly losing somebody's work.

**Why it matters more than it looks.** A wig with one fitting is one person's word. A wig with four is four people, four units, four rooms, four blasters, all reaching the same answer. That is the difference between a file somebody uploaded and a file you can trust on sight, and there is no way to fake it or automate it. Every fitting you add makes the wig easier for the next person to pick up, and it is the number that decides which wigs graduate.

### A wig that needs fixing

Repair the code on your device, not in the file, then let HAIR save your device as the successor: it carries the lineage automatically. Your file replaces the old one on the shelf, and it needs its own perfect fit, because nobody has proven the new description yet. See [CONTRIBUTING.md](CONTRIBUTING.md#when-the-wig-is-wrong-or-your-device-outgrew-it).

The fitting count is the only honest popularity signal a git repo can offer, and it happens to be the right one: the most proven wig is usually also the most used. It is also what [WigFactory](https://github.com/DAB-LABS/WigFactory) watches when it goes looking for wigs to promote.

---

## Naming and layout

```
wigs/
  fujitsu/
    fujitsu-ac-asyg09-perfect-fit.wig.json
    fujitsu-tv-p50xha58eb-perfect-fit.wig.json
  sanmli/
    sanmli-light-th-05-perfect-fit.wig.json
  unbranded/
    fan-b09xyz-perfect-fit.wig.json
```

**One folder per brand.** Lowercase, hyphens, no spaces. No nesting under parent companies: Fujitsu General goes in `fujitsu`.

**Files are named `<brand>-<kind>-<model>-perfect-fit.wig.json`,** which is what HAIR calls your download. Kind is one word with no inner dashes, like `tv`, `soundbar`, `settopbox`, `candles`, `ac`. A piece the wig does not carry is skipped. The brand repeats in the filename on purpose, because the file lands in a Downloads folder with no path around it.

A wig with no brand has no anchor for that shape, so HAIR names it after the wig instead: the unbranded fan above is called "Fan (B09XYZ)" in its file. Those go in `unbranded/`, which is exempt from the brand-prefix rule.

The shop never reads the tier suffix as evidence. It runs the claims in the file, because a name that could promote a wig by being edited would defeat the point of signed per-row claims.

**`unbranded/` needs a product identifier.** If you cannot name a brand, put an FCC ID, UPC or ASIN in the wig's `identifiers` so the thing stays findable. Off-brand hardware is exactly what this repo is for, and an unbranded folder with no anchors is a junk drawer.

**Rebadged hardware gets one file.** Same codes sold under three names is still one wig. File it under the brand you can most defensibly name and list the others in `identifiers`, which accepts several values for exactly this. The index will show it under all of them.

**The shelf holds current descriptions.** A wig here is what the device is now, wholly proven. When the codes have to change, the changed file is a new wig that replaces the old one and says so, and the old one retires with its fittings rather than lingering beside its successor. Git history is the museum; the shelf is the store.

---

## Where wigs go from here

Some of these graduate, and fittings are what decides which ones. The wigs with the most people behind them get picked up by [WigFactory](https://github.com/DAB-LABS/WigFactory), which turns a proven code set into a real installable Home Assistant integration, named for the wig's brand, kind and model. From there the best of them can go further still, into Home Assistant Core itself, where somebody adds your device without ever knowing this repo exists.

That path starts with somebody pressing every button on a remote and signing for it. Nothing else feeds it.

When a wig graduates, its entry stays right here with a pointer to where it went. The shop does not empty out. It becomes the record of how each one got there.

---

## Writing something that emits wigs

The format is documented in [HAIR's wig format contract](https://github.com/DAB-LABS/HAIR/blob/main/docs/wig-format.md). One JSON file, one remote, and everything a writer needs is on that page.

The shop's [checks](.github/workflows/validate.yml) run that same validator, pinned to a HAIR release, so a wig that passes here is a wig that loads there. It does not run the other way: converter output that loads perfectly well in HAIR still will not pass the shop, because what a converter cannot produce is a fitting. Those come off real hardware, one row at a time, which is the whole point.

Convert inbound only. Read your source format, emit a wig, and leave it at that. Do not bundle or redistribute somebody else's code database, here or anywhere: convert files the user already holds.

---

## License and the declaration

Wig data in this repo is released under [CC0 1.0](LICENSE), a public domain dedication. IR codes are functional facts, and CC0 keeps the path into upstream Home Assistant clean with no license question to argue about later.

Attribution here is social, not legal. Your name rides in the fitting and in the git history. That is the point of the whole thing.

Every pull request carries one checkbox:

> These codes came off hardware I have access to, or I verified them on it, and I am releasing them under this repository's license.

Please mean it. A merged wig is permanent, and this repo is worth exactly as much as that sentence is true.

---

## Questions

Open an issue here for anything about the shop. For HAIR itself, the bug tracker is [over on HAIR](https://github.com/DAB-LABS/HAIR/issues).

Thanks for proving things. 🍻

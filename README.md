# The Wig Shop

Proven infrared code sets for [HAIR](https://github.com/DAB-LABS/HAIR), the barbershop for your smart home's IR devices.

A **wig** is one JSON file holding one remote's codes. Download one, drop it on HAIR's Closet, and you have that remote.

**One rule gets a wig in here: somebody proved it on their own hardware first.**

That is what makes this different from a code database. Nothing lands in this repo until a named person pointed a blaster at the real device, pressed every button, and recorded that it worked. If a wig is here, it worked for someone.

---

## What this is not

This is not a database, and HAIR does not fetch anything from it. There is no index HAIR calls, no lookup, no phoning home. You download a file, you drop it on the Closet, exactly like any other file. The shop is a place people put things, not a service.

It is also not comprehensive and never will be. It covers whatever people proved. That is the whole promise, and it is a small one on purpose.

---

## Using a wig

1. Find the brand folder under [`wigs/`](wigs/), or search [`INDEX.md`](INDEX.md) by brand, kind or product identifier.
2. Download the `.wig.json` file.
3. In Home Assistant, open HAIR, go to the **Closet**, and drop the file on the import bar.
4. **ADOPT DEVICE** turns it into a working device, or **CLIP** opens it on the Clipper if you want to look before you commit.

If it works for you, come back and add your fitting. That is how the next person knows it was not a fluke.

---

## The fitting

A fitting is the record of somebody proving a wig. In HAIR you press **FIT** on a closet wig, pick an emitter, send each signal, and mark it WORKED or DID NOT. When every signal works, you sign it with your name and an optional GitHub handle.

Fittings ride inside the wig file. One file carries the codes and every proof anyone has recorded against them.

Three things make a fitting worth something:

**It is per signal.** Not "this wig works" but "these forty buttons work, one at a time, and I pressed all of them."

**It is bound to the codes.** The fitting carries a hash of the exact signals it tested. Change a code afterward, even rename an alias, and the fitting stops matching and shows as outdated instead of quietly claiming codes it never saw.

**It is signed.** HAIR signs recorded fittings with a key generated on your install. The signature proves the record has not been altered since you made it. Unsigned fittings are still fine, they are just self reported.

Fittings are social proof, not identity. The handle is what you typed. The signature proves the record is unaltered and that fittings sharing a key came from one install. Nobody is claiming more than that.

Only **complete** fittings travel. HAIR strips partial and in-progress ones on download and share, so a wig you get from here carries whole claims or none.

---

## Contributing

Everything here is one file. Download it from HAIR, open a pull request, tick the declaration.

### A wig nobody has posted yet

You need your own complete fitting first. HAIR will not export a partial one, so this is not a hurdle you can trip over by accident.

1. Fit the wig in HAIR until every signal is confirmed.
2. Download it from the Closet.
3. Open a pull request adding `wigs/<brand>/<brand>-<kind>-<model>.wig.json`.
4. Tick the declaration in the PR template.

Checks run automatically. A human confirms it is not a duplicate and the brand looks plausible, then it merges.

### A fitting on a wig that is already here

Even better, and it is the same one file.

1. **Download the current wig from this repo**, not an older copy you already had. It carries everyone else's fittings, and you want yours added to theirs rather than replacing them.
2. Drop it on the Closet, fit it, confirm every signal.
3. Download it again and open a pull request replacing that same file.

The checks confirm your signals still hash to the same value and that no existing fitting went missing. If a fitting disappeared, you fitted an older copy, and the PR gets refused with that reason rather than quietly losing somebody's work.

A wig with five independent fittings is the most proven thing in here, and the most used. That count is the only honest popularity signal a git repo can offer, so it is the one we use.

---

## Naming and layout

```
wigs/
  fujitsu/
    fujitsu-ac-asyg09.wig.json
    fujitsu-tv-p50xha58eb.wig.json
  sanmli/
    sanmli-candles-th05.wig.json
  unbranded/
    unbranded-fan-b09xyz.wig.json
```

**One folder per brand.** Lowercase, hyphens, no spaces. No nesting under parent companies: Fujitsu General goes in `fujitsu`.

**Files are `<brand>-<kind>-<model>.wig.json`.** Kind is one word with no inner dashes, like `tv`, `soundbar`, `settopbox`, `candles`, `ac`. Pieces drop out when you genuinely do not have them. The brand repeats in the filename on purpose, because the file lands in a Downloads folder with no path around it.

That stem is also what the wig becomes if it graduates. `sanmli-candles-th05.wig.json` turns into the integration repo `sanmli-candles-th05-infrared`, so a wig carries its own future name from the day it lands.

**`unbranded/` needs a product identifier.** If you cannot name a brand, put an FCC ID, UPC or ASIN in the wig's `identifiers` so the thing stays findable. Off-brand hardware is exactly what this repo is for, and an unbranded folder with no anchors is a junk drawer.

**Rebadged hardware gets one file.** Same codes sold under three names is still one wig. File it under the brand you can most defensibly name and list the others in `identifiers`, which accepts several values for exactly this. The index will show it under all of them.

**Once a wig is merged, its codes never change.** Every fitting is bound to a hash of the exact signals it tested, so editing the codes in a published wig silently invalidates everyone else's work. Fittings get added; signals do not move. Corrections come in as a new file with a note pointing at what changed.

---

## Where wigs go from here

Some of these graduate. A wig with three complete fittings from three different people is eligible for [WigFactory](https://github.com/DAB-LABS/WigFactory), which turns a proven code set into an installable Home Assistant integration. Codes that belong upstream go upstream, to Home Assistant's own `infrared-protocols`, which is the better home when the door is open.

When a wig graduates, its entry stays right here with a pointer to where it went. The shop does not empty out. It becomes the record of how each one got there.

---

## Writing something that emits wigs

The format is documented in [HAIR's wig format contract](https://github.com/DAB-LABS/HAIR/blob/main/docs/wig-format.md). One JSON file, one remote, and everything a writer needs is on that page.

The shop's [checks](.github/workflows/validate.yml) run that same validator, pinned to a HAIR release, so if your output loads in HAIR it passes here.

Convert inbound only. Read your source format, emit a wig, and leave it at that. Do not bundle or redistribute somebody else's code database, here or anywhere: convert files the user already holds.

---

## License and the declaration

Wig data in this repo is released under [CC0 1.0](LICENSE), a public domain dedication. IR codes are functional facts, and CC0 keeps the path into upstream Home Assistant clean with no license question to argue about later.

Attribution here is social, not legal. Your name rides in the fitting and in the git history. That is the point of the whole thing.

Every PR carries one checkbox:

> These codes came off hardware I have access to, or I verified them on it, and I am releasing them under this repository's license.

Please mean it. A merged wig is permanent, and this repo is worth exactly as much as that sentence is true.

---

## Questions

Open an issue here for anything about the shop. For HAIR itself, the bug tracker is [over on HAIR](https://github.com/DAB-LABS/HAIR/issues).

Thanks for proving things. 🍻

# Contributing to the Wig Shop

Everything here arrives as one file, through a pull request, from somebody who proved it on their own hardware.

If that sentence is already clear, the rest of this page is detail you can skim.

---

## What you need

**HAIR 0.8.0 or newer.** Fittings arrived in 0.8.0, and a wig cannot enter the shop without one. Older versions can read and write wigs, they just cannot record the proof.

**Real hardware.** The device itself, a blaster to send with, and the willingness to press every button and watch what happens.

That is the whole barrier. No account here, no build tools, no git beyond opening a PR.

---

## Fitting a wig

A fitting is the record of you proving a wig works. It is per signal, not per wig.

1. Open HAIR, go to the **Closet**, and press **FIT** on the wig.
2. Pick the emitter you want to send through.
3. HAIR sends one signal at a time. Watch the device. Mark **WORKED** or **DID NOT**.
4. Marks save as you make them. Close the dialog, restart Home Assistant, come back next week; pressing FIT again resumes with the untested signals first.
5. When every signal has worked, the session turns green and **FINISH** records the fitting under your name, with an optional GitHub handle.

Put your GitHub handle in. It is optional in the format, but the shop's promotion gate counts distinct handles, and a fitting without one cannot be counted toward it.

**If a signal does not work**, mark it DID NOT and keep going. That fitting stays local and incomplete, which is correct: a wig with a dead button is not proven, and HAIR will not let it travel. Fix the code and refit, or leave it alone.

---

## Contributing a wig nobody has posted yet

1. Fit it until every signal is confirmed.
2. In the Closet, download the wig.
3. Open a pull request adding it at:

   ```
   wigs/<brand>/<brand>-<kind>-<model>.wig.json
   ```

4. Tick the declaration in the PR template.

Checks run on the PR. A human then confirms it is not a duplicate and the brand looks plausible, and merges it.

---

## Adding a fitting to a wig already here

This is the most useful thing you can do here, and it is the same single file.

1. **Download the current wig from this repo.** Not an older copy from your Closet.
2. Drop it on HAIR's Closet, press FIT, confirm every signal.
3. Download it again and open a pull request replacing that same file.

**Why step 1 matters.** The wig in this repo carries every fitting anyone has recorded. If you fit a copy you downloaded last month, your file is missing the fittings that landed since, and replacing the repo's copy with yours would delete somebody else's work. Git will not warn you, because dropping an array entry is a perfectly clean diff. The checks catch it and refuse the PR, but you will save yourself a round trip by starting from the current file.

---

## Naming and placement

**Brand folder.** Lowercase, ASCII, hyphens, no spaces. One folder per brand with no nesting under parent companies, so Fujitsu General goes in `fujitsu`, not `fujitsu-general` or `fujitsu/general`.

**Filename.** `<brand>-<kind>-<model>.wig.json`

- `brand` repeats the folder. That is deliberate: the file lands in somebody's Downloads with no path around it.
- `kind` is one word, no inner dashes. `tv`, `soundbar`, `receiver`, `settopbox`, `projector`, `fan`, `light`, `candles`, `ac`, `heater`, `blinds`. Others are fine if none of those fit.
- `model` is what is printed on the device.

Drop any piece you genuinely do not have. `sanmli-candles.wig.json` is fine if the thing has no model number.

**No brand?** Then it goes in `unbranded/`, and the wig must carry at least one entry in `identifiers`: an FCC ID, a UPC off the box, or an ASIN. Off-brand hardware is a large part of why this repo exists, and an unbranded folder with no anchors is a junk drawer nobody can search.

**Rebadged hardware gets one file.** The same codes sold under three names is still one wig. File it under the brand you can most defensibly name, and list the others in `identifiers`, which accepts several values per key for exactly this reason. It will appear under all of them in the index.

---

## What the checks look at

So you know before you open the PR:

- The file parses as `hair-wig/1`, using HAIR's own validator. Failures come back with the specific field.
- Every fitting is complete: every signal confirmed, none failed.
- Every fitting's `content_hash` matches the signals in the file it sits in.
- On a wig that already exists here, the signals hash is unchanged and no existing fitting has gone missing.
- Signatures verify, where a fitting carries one.
- The filename, brand folder, and `unbranded/` identifier rule.

None of this is new logic invented for the shop. It is the same validation HAIR runs on import.

---

## What a human checks

Two things, and it takes about two minutes:

**Is this a duplicate?** The content hash catches exact matches automatically. Renamed aliases change the hash, so the same remote can arrive twice looking different. If it does, the first one merged keeps the slot. Yours becomes a fitting on it when the codes match, or a separate entry with a distinguishing model suffix when they do not.

**Does the brand look plausible?** Not a judgement of your hardware. Just a check that `fujitsu` did not arrive as `Fujitsu General Ltd.`

---

## What will be turned away

**An incomplete fitting.** HAIR strips those on download, so you would have to work to produce one.

**A wig with no fitting at all.** This is the whole rule. There is no exception for codes you are confident about.

**Edited codes on a published wig.** Once a wig is merged its signals are fixed, because every fitting is bound to a hash of exactly those signals. Corrections arrive as a new file with a note about what changed. Fittings get added; signals do not move.

**A bulk conversion of somebody else's database.** Fittings are per signal and cost real time at real hardware, which is the point. If forty wigs arrive from one person in one afternoon, that will be asked about.

---

## License and the declaration

Wig data here is released under [CC0 1.0](LICENSE). IR codes are functional facts, and CC0 keeps the path into upstream Home Assistant clean with no license question to argue about later.

Attribution is social, not legal. Your name rides in the fitting and in the git history.

Every pull request carries one checkbox:

> These codes came off hardware I have access to, or I verified them on it, and I am releasing them under this repository's license.

Please mean it. A merged wig is permanent and CC0 cannot be withdrawn. This repo is worth exactly as much as that sentence is true.

If your codes came out of another project's code database rather than off your own hardware, say so in the PR rather than ticking the box. A fitting proves the codes work; it does not settle where they came from, and that is worth being straight about.

---

## Questions

Open an issue here for anything about the shop. For HAIR itself, use [HAIR's tracker](https://github.com/DAB-LABS/HAIR/issues).

Thanks for proving things. 🍻

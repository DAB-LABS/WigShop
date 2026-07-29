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
3. **Rename the file.** HAIR names your download after the wig, so you will get something like `candles-tea-light.wig.json`. The shop wants the brand, kind and model instead:

   ```
   sanmli-candles-th05.wig.json
   ```

   Everybody hits this. It is not you doing something wrong, it is two naming schemes meeting. Details under [Naming and placement](#naming-and-placement).

4. Open a pull request adding it at `wigs/<brand>/<that filename>`, so for the example above, `wigs/sanmli/sanmli-candles-th05.wig.json`.
5. Tick the declaration in the PR template.

Checks run on the PR. A human then confirms it is not a duplicate and the brand looks plausible, and merges it.

### Doing it without git

You do not need a terminal, a clone, or any tooling. The whole thing works in a browser.

**If the brand folder does not exist yet**, which it will not for a brand nobody has posted:

1. On your own machine, make a folder named after the brand, lowercase, and put the renamed wig inside it. For the example above that is a folder `sanmli` containing `sanmli-candles-th05.wig.json`.
2. On GitHub, click into the [`wigs/`](wigs/) folder, then **Add file** and **Upload files**.
3. Drag the whole brand folder onto the page. GitHub keeps the folder structure, so it lands at the right path.
4. At the bottom, choose **Create a new branch for this commit and start a pull request**, then **Propose changes**. The template loads and you fill it in.

**If the brand folder already exists**, click into it first, then **Add file** and **Upload files**, and drag the file itself.

The checkboxes in the template are easier to tick after the pull request is open: submit it, then click them in the rendered description. Typing `[x]` by hand works too, but the spacing inside the brackets has to be exact.

---

## Adding a fitting to a wig already here

This is the most useful thing you can do here, and it is the same single file.

1. **Download the current wig from this repo.** Not an older copy from your Closet.
2. Drop it on HAIR's Closet, press FIT, confirm every signal.
3. Download it again, rename it back to the name it has in this repo, and open a pull request replacing that same file.

In the browser: click into the wig's brand folder here, **Add file**, **Upload files**, and drag your renamed copy in. Same filename means GitHub records it as a change to that wig rather than a second one, which is exactly what you want. Then **Create a new branch for this commit and start a pull request**.

**Why step 1 matters.** The wig in this repo carries every fitting anyone has recorded. If you fit a copy you downloaded last month, your file is missing the fittings that landed since, and replacing the repo's copy with yours would delete somebody else's work. Git will not warn you, because dropping an array entry is a perfectly clean diff. The checks catch it and refuse the PR, but you will save yourself a round trip by starting from the current file.

---

## Naming and placement

**Brand folder.** Lowercase, ASCII, hyphens, no spaces. One folder per brand with no nesting under parent companies, so Fujitsu General goes in `fujitsu`, not `fujitsu-general` or `fujitsu/general`.

**Filename.** `<brand>-<kind>-<model>.wig.json`

This is almost never what HAIR names your download. HAIR names the file after the wig, so "Candles (Tea Light)" comes out as `candles-tea-light.wig.json`, and the shop wants `sanmli-candles-th05.wig.json`. Renaming is a normal step, not a sign you did something wrong.

- `brand` repeats the folder. That is deliberate: the file lands in somebody's Downloads with no path around it.
- `kind` is one word, no inner dashes. `tv`, `soundbar`, `receiver`, `settopbox`, `projector`, `fan`, `light`, `candles`, `ac`, `heater`, `blinds`. Others are fine if none of those fit.
- `model` is what is printed on the device.

Drop any piece you genuinely do not have. `sanmli-candles.wig.json` is fine if the thing has no model number.

**No brand?** Then it goes in `unbranded/`, and the wig must carry at least one entry in `identifiers`: an FCC ID, a UPC off the box, or an ASIN. Off-brand hardware is a large part of why this repo exists, and an unbranded folder with no anchors is a junk drawer nobody can search.

**Rebadged hardware gets one file.** The same codes sold under three names is still one wig. File it under the brand you can most defensibly name, and list the others in `identifiers`, which accepts several values per key for exactly this reason. It will appear under all of them in the index.

---

## What the checks look at

So you know before you open the PR:

- The file parses, using HAIR's own validator. Failures come back naming the specific field.
- At least one fitting is there, and every fitting is complete: every row confirmed, none failed.
- Every fitting's `content_hash` matches the codes in the file it sits in.
- On a wig that already exists here, the codes hash is unchanged and no existing fitting has gone missing.
- Signatures verify, where a fitting carries one. Unsigned fittings pass with a note.
- No two fittings on one wig share a handle.
- The filename, the brand folder, and the `unbranded/` identifier rule.
- Nothing else in the repo already has these exact codes.

None of this is new logic invented for the shop. [`validate.yml`](.github/workflows/validate.yml) checks out HAIR at a pinned release and runs the same parser your own install runs on import, so a wig that passes here is a wig that loads there. The format itself is documented in [HAIR's wig format contract](https://github.com/DAB-LABS/HAIR/blob/main/docs/wig-format.md), which is everything you need if you are writing a tool that emits wigs.

A few things come back as warnings rather than failures, because they need a person to look rather than a rule to fire: an unsigned fitting, a brand field that disagrees with its folder, a missing `kind`, or two handles that signed with the same key.

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

### Codes that came from another project

These are fine here, as long as you fitted them yourself.

Pulling a code set out of SmartIR or anywhere else, sending it at your own air conditioner, and confirming every state on the unit in front of you is exactly what the declaration's second clause describes. You verified them on hardware you have access to. Tick the box.

Two things get conflated, so it is worth separating them. What makes CC0 workable here is that IR codes are functional facts: a description of what a device listens for, with very little in them to own. That is a property of the codes themselves, not of your testing. The fitting is what makes a wig worth having, because it proves the thing works on real hardware. It is a quality bar, and it was never meant to settle provenance.

So mention where the codes came from in the PR. It is useful, the next person may want to know, and being straight about it costs nothing. Just do not treat it as a reason to hold back the declaration.

---

## Questions

Open an issue here for anything about the shop. For HAIR itself, use [HAIR's tracker](https://github.com/DAB-LABS/HAIR/issues).

Thanks for proving things. 🍻

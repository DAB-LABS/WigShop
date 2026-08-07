# Contributing to the Wig Shop

Everything here arrives as one file, through a pull request, from somebody who proved it on their own hardware.

If that sentence is already clear, the rest of this page is detail you can skim.

---

## What you need

**HAIR 0.9.5 or newer, and 0.9.7 if you can.** Per-row claims arrived in 0.9.5, so a 0.9.5 or 0.9.6 attestation is perfectly good and will be counted here. What 0.9.7 adds is worth having anyway: it names your download so the file drops straight in without a rename, and it stamps a wig's lineage automatically, which is what a replacement needs. Anything older than 0.9.5 can read and write wigs but cannot attest one under the claims model.

**Real hardware.** The device itself, a blaster to send with, and the willingness to press every button and watch what happens.

That is the whole barrier. No account here, no build tools, no git beyond opening a pull request.

---

## Perfect fits only

**A wig lands here when one person has proven every code in it, on their own hardware, in one attestation.**

Partial fittings, however honest, stay home. A file where three people each proved a third is a file nobody has watched work end to end, and the front page of this shop gets to say one sentence with no asterisk.

Once a wig is here, a partial attestation is welcome alongside the whole one. Somebody whose hardware revision lacks a button can still vouch for the rows they have, and their signature is worth having. It just cannot be the thing that opens the door.

**If your hardware revision is missing buttons a shop wig carries, do not trim the shared file to fit your unit.** Submit your revision as its own wig, named for what it is, with the product identifiers that tell it apart. A smaller wig that wholly works beats a bigger one that mostly does.

---

## Fitting a wig

The proving ground is the device, not a dialog.

1. Adopt the wig in HAIR and **use the thing**. Live with it. That is the test.
2. When it has earned your trust, press **SAVE TO CLOSET**. HAIR asks what you mean, with a one-line summary of how your device differs from its wig.
3. Choose **Validate for Perfect Fit**. That is the fitting.
4. Work the checklist. Every command is a row with a **TEST** button that reports SENT, or SENT and HEARD when a receiver caught it. Tick what you proved.
5. Sign it, with your name and your GitHub handle.

Put your GitHub handle in. On a signed fitting nothing counts it -- the shop counts signing keys, because a name is what somebody typed and a key is which install they typed it on. It still earns its place three ways: it is how somebody can reach you about a code that stopped working, it is how a maintainer notices that two fittings came from one person on two machines when independence is being counted at promotion, and on an *unsigned* fitting it is the only thing the shop can tell you apart by, so leaving it off there really does cost you.

**A row your hardware refuses gets excluded honestly.** *Not on my device* and *could not make it work* are recorded in standard form rather than as prose, so three people excluding the same row reads as a pattern instead of three sentences somebody has to interpret. A row you exclude is a row you did not prove, which means that fitting is not a perfect fit -- see above for what to do about it.

**Your signature binds each row's transmit recipe by digest**, under a key generated on your install. Nobody can alter your verdicts or fit in your name. Fix one bad code later and only that row's claims retire; everything else anyone proved still stands.

**Identity is the key, not the typed name.** Fit the same wig again from the same install and your new signing replaces your old one. One person, one current word. Two people who both type "David" are two people, because their keys differ.

---

## Contributing a wig nobody has posted yet

1. Fit it until every row is proven. The download filename will say `-perfect-fit` when it is ready.
2. In the Closet, download the wig.
3. Open a pull request adding it at `wigs/<brand>/<the filename HAIR gave you>`.
4. Tick the declaration in the pull request template.

**You should not need to rename anything.** Since 0.9.7 HAIR composes the download name from the wig's own fields, `<brand>-<kind>-<model>-perfect-fit.wig.json`, which is exactly the shape this repo files under. If it does need a rename, something is off; say so in the pull request and we will look at it rather than making you fight the name.

The shop never reads the tier from a filename. It runs the claims. A name that could promote a file by being edited would defeat the point of signed per-row claims, so `-perfect-fit` is a courtesy to you at the moment of download and nothing more.

Checks run on the pull request. A human then confirms it is not a duplicate and the brand looks plausible, and merges it.

### Doing it without git

You do not need a terminal, a clone, or any tooling. The whole thing works in a browser.

**If the brand folder does not exist yet**, which it will not for a brand nobody has posted:

1. On your own machine, make a folder named after the brand, lowercase, and put the wig inside it. For a Sanmli light that is a folder `sanmli` containing `sanmli-light-th-05-perfect-fit.wig.json`.
2. On GitHub, click into the [`wigs/`](wigs/) folder, then **Add file** and **Upload files**.
3. Drag the whole brand folder onto the page. GitHub keeps the folder structure, so it lands at the right path.
4. At the bottom, choose **Create a new branch for this commit and start a pull request**, then **Propose changes**. The template loads and you fill it in.

**If the brand folder already exists**, click into it first, then **Add file** and **Upload files**, and drag the file itself.

The checkboxes in the template are easier to tick after the pull request is open: submit it, then click them in the rendered description. Typing `[x]` by hand works too, but the spacing inside the brackets has to be exact.

---

## Adding your fitting to a wig already here

This is the most useful thing you can do here, and it is the easiest pull request there is.

1. **Download the current wig from this repo.** Not an older copy from your Closet.
2. Drop it on HAIR's Closet, adopt it, live with it.
3. **SAVE TO CLOSET**, then **Validate for Perfect Fit**, and work the checklist.
4. Download it again and open a pull request replacing that same file.

The diff should be one appended fitting and zero changed codes.

**Why step 1 matters.** The wig in this repo carries every fitting anyone has recorded. If you fit a copy you downloaded last month, your file is missing the fittings that landed since, and replacing the repo's copy with yours would delete somebody else's work. Git will not warn you, because dropping an array entry is a perfectly clean diff. The checks catch it and refuse the pull request, but you will save yourself a round trip by starting from the current file.

**Re-fitting a wig you already proved is fine.** Your new signing replaces your old one, so the diff shows one fitting removed and one added carrying the same key. The checks read that as what it is.

---

## When the wig is wrong, or your device outgrew it

The shelf holds **current descriptions of devices, wholly proven**. While a wig's content is stable, proof accumulates on it. When the content has to change, the changed file is a **new wig** that replaces the old one.

So: do not edit a shop wig's codes and submit that. Fix the device, not the file.

1. Repair the code on the device, in the command editor. Paste a Pronto, or press **LISTEN** and capture it off the real remote. Add the button the wig was missing the same way.
2. **SAVE TO CLOSET**, and choose **Update Closet Wig**. HAIR names the stakes before you commit, mints the successor, and stamps its lineage automatically -- the device remembered where it came from.
3. Fit the successor. Nobody has proven the new description until somebody proves it, which is why it has to arrive as a perfect fit.
4. Open a pull request replacing the old file, and say in the comment what was wrong and what you changed.

Usually that is a change to the file already here, because a successor for the same device composes the same filename. It becomes a rename only when the kind or model changed, and the checks follow it either way, because they pair wigs by identity rather than by path.

The old wig retires with its fittings. That is not the shop throwing away somebody's work: their proof was about a description that no longer exists, and git history keeps every word of it. The checks will report exactly which rows changed and whose claims each change retires, so a maintainer can read what your repair cost before merging it.

**If a wig you fitted was replaced before your pull request landed**, the check will tell you so and point at the file that replaced it. Download that one, fit it, and your name goes on the description people actually download. You lose minutes, not your contribution.

---

## Naming and placement

**Brand folder.** Lowercase, ASCII, hyphens, no spaces. One folder per brand with no nesting under parent companies, so Fujitsu General goes in `fujitsu`, not `fujitsu-general` or `fujitsu/general`.

**Filename.** `<brand>-<kind>-<model>-perfect-fit.wig.json`, which is what HAIR names your download.

- `brand` repeats the folder. That is deliberate: the file lands in somebody's Downloads with no path around it.
- `kind` is one word, no inner dashes. `tv`, `soundbar`, `receiver`, `settopbox`, `projector`, `fan`, `light`, `candles`, `ac`, `heater`, `blinds`. Others are fine if none of those fit.
- `model` is what is printed on the device, slugified. `TH-05` becomes `th-05`.
- A piece the wig does not carry is skipped, so a wig with no model is `<brand>-<kind>-perfect-fit.wig.json`.

**Brand is the exception.** With no brand there is nothing to anchor the name to, so HAIR falls back to the slug of the wig's own name and drops kind and model with it: a wig called "Fan (B09XYZ)" downloads as `fan-b09xyz-perfect-fit.wig.json`. That is a fine name and it belongs in `unbranded/`, which is exempt from the brand-prefix rule for exactly this reason. Give the wig a name worth reading before you download it.

Lowercase is not a style preference. macOS treats `TH-05` and `th-05` as one file while git treats them as two, so allowing case would let two wigs coexist in the repo and collide on checkout. The exact string you typed survives in the wig's `model` field and prints verbatim in the index, which is where people read it.

**No brand?** Then it goes in `unbranded/`, and the wig must carry at least one entry in `identifiers`: an FCC ID, a UPC off the box, or an ASIN. Off-brand hardware is a large part of why this repo exists, and an unbranded folder with no anchors is a junk drawer nobody can search. Unbranded files are exempt from the brand-prefix rule, since there is no brand to put in front.

**Rebadged hardware gets one file.** The same codes sold under three names is still one wig. File it under the brand you can most defensibly name, and list the others in `identifiers`, which accepts several values per key for exactly this reason. It will appear under all of them in the index.

---

## What the checks look at

So you know before you open the pull request:

- The file parses, using HAIR's own validator. Failures come back naming the specific field.
- At least one fitting claims every row of the wig worked. This is the gate.
- Every fitting's signature verifies, and every fitting names this wig. An unsigned fitting passes, with a warning.
- No two fittings share a signing key, since one install has one current word.
- No fitting that is already here has gone missing.
- On a wig that replaces one already here, the check reports what changed: rows added, rows repaired, rows removed, and whose claims each of those retires. Lineage the shop cannot trace, or lineage naming a wig other than the one being replaced, is a warning for a maintainer to read rather than a refusal.
- Nothing else in the repo already has these exact codes, and no two files share one wig identity.
- The filename, the brand folder, and the `unbranded/` identifier rule.
- What combing found, if anyone combed the wig.

None of this is new logic invented for the shop. [`validate.yml`](.github/workflows/validate.yml) checks out HAIR at a pinned release and runs the same parser your own install runs on import, so a wig that passes here is a wig that loads there. The format itself is documented in [HAIR's wig format contract](https://github.com/DAB-LABS/HAIR/blob/main/docs/wig-format.md), which is everything you need if you are writing a tool that emits wigs.

A good deal comes back as a warning rather than a failure, because it needs a person to look rather than a rule to fire: an unsigned fitting, a brand field that disagrees with its folder, a missing `kind`, claims about rows the wig no longer carries, lineage the shop cannot trace, rows leaving a wig that carried somebody else's proof, and several people reporting the same code does not work on their hardware. That last one is why the exclusion reasons are a fixed set rather than free text: one person is a hardware revision, several is a sign the code itself is wrong.

---

## What a human checks

Two things, and it takes about two minutes:

**Is this a duplicate?** Identical codes are caught automatically. Renamed aliases change the comparison, so the same remote can arrive twice looking different. If it does, the first one merged keeps the slot. Yours becomes a fitting on it when the codes match, or a separate entry with a distinguishing model when they do not.

**Does the story fit?** On a wig that replaces one already here, the checks say what moved and the maintainer reads whether your account of it makes sense. That is the only judgement call in the process, and it is why the pull request comment matters on a replacement and barely matters on a plain fitting.

---

## What will be turned away

**A wig no single person has proven whole.** This is the rule. There is no exception for codes you are confident about, and none for a wig three people have proven between them.

**Edited codes submitted over a shop wig.** Not because repair is unwelcome; it is a designed path. But a changed description is a new wig, so it arrives as a replacement with its lineage, not as an edit in place. See [above](#when-the-wig-is-wrong-or-your-device-outgrew-it).

**Rows trimmed out of a shared wig to reach a perfect fit.** If your unit does not have those buttons, submit your revision as its own wig. Deleting rows other people proved, to get your own file green, is the one move this gate could tempt somebody into, and the checks make it visible.

**A pre-0.9.5 fitting.** The old whole-file model recorded that some bytes were proved, not which rows, so there is no honest way to turn one into per-row claims. Import the wig into current HAIR and fit it again. It takes a few minutes; a fabricated claim lasts forever.

**A bulk conversion of somebody else's database.** Fittings are per row and cost real time at real hardware, which is the point. If forty wigs arrive from one person in one afternoon, that will be asked about.

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

So mention where the codes came from in the pull request. It is useful, the next person may want to know, and being straight about it costs nothing. Just do not treat it as a reason to hold back the declaration.

---

## Questions

Open an issue here for anything about the shop. For HAIR itself, use [HAIR's tracker](https://github.com/DAB-LABS/HAIR/issues).

Thanks for proving things. 🍻

<!--
Thanks for contributing. Fill in the lines below and tick the boxes.
Details on any of this: CONTRIBUTING.md
-->

**Device:**
<!-- Brand, kind and model as best you know them. e.g. Fujitsu, ac, ASYG09 -->

**What this pull request does:**
<!--
One of:
  - New wig
  - Adding my fitting to a wig already here
  - Replacing a wig whose codes needed to change
  - A revision of a wig already here, as its own file
-->

---

## The declaration

- [ ] These codes came off hardware I have access to, or I verified them on it, and I am releasing them under this repository's license ([CC0 1.0](../LICENSE)).

If that is not quite true, do not tick it. Say where the codes came from instead and we will work out where they belong.

Codes that started life in another project's database are fine here, as long as you fitted them yourself on your own hardware. That is what the second clause covers, so tick the box and mention the source below.

## Always

- [ ] I did not add a code to this file that I have not watched work on real hardware.
- [ ] The file is at `wigs/<brand>/<the name HAIR gave the download>`, brand folder lowercase with hyphens.

## Opening a wig: new, or replacing one that is here

Skip this section if you are adding your fitting to a wig that is already on the shelf.

- [ ] **I proved every row of this wig myself, in one fitting.** Not "between us" and not "all but one" -- the whole thing, by me. This is the gate, and it applies to a replacement exactly as it does to a new wig, because nobody has proven the new description until somebody proves it.
- [ ] This wig is in `unbranded/`, and it carries an FCC ID, UPC or ASIN in `identifiers`.
- [ ] This replaces a wig whose codes had to change. I fixed the device and let HAIR save it as the successor, so it carries its own lineage, and I have accounted for every changed and removed row below.
- [ ] My hardware revision differs from a wig already here, so this is a separate wig for that revision rather than an edit to the shared file.

## Adding your fitting to a wig already here

- [ ] I downloaded the current file from this repo before fitting it, so my file carries everyone else's fittings alongside mine.
- [ ] **My fitting may be partial, and that is fine here.** A row your unit does not have, or one you could not make work, is an honest exclusion rather than a failure. Somebody has already proven this wig whole; your signature rides alongside theirs and does not have to repeat the feat.

<!--
A note on the filename, since it misleads: the -perfect-fit suffix
describes the WIG, not you. A wig somebody else proved whole downloads
as -perfect-fit no matter how much of it you personally vouched for. The
shop reads the claims in the file and never the name.
-->

**Leave any box unticked if it is not your situation.** That is the right answer, not a gap.

## What changed, and why

<!--
Required on a replacement, optional otherwise. The checks will say WHAT
moved: rows added, rows repaired, rows removed, and whose fittings each
of those retires. This is where you say why, which is the one thing the
checks cannot work out.

Also useful, on any pull request:
  - the emitter and receiver you used
  - buttons the remote has that this wig deliberately leaves out
  - where the codes originally came from
  - anything odd about the device
-->

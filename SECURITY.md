# Security

This repository holds data, not code. That shapes everything below, so it
is worth saying plainly before anything else.

## What a wig can actually do

A wig is a JSON file full of infrared codes. Infrared is a one-way,
line-of-sight, unauthenticated signal with no return path. The worst a
malicious or wrong wig can do is transmit the wrong code at whatever is
in front of the blaster: turn on a TV, set an air conditioner badly,
change an input.

That is a reputational problem and an annoyance. It is not a compromise
of anything. Nothing in a wig executes, nothing in it reaches the
network, and HAIR never fetches from this repository. You download a
file and drop it on the Closet yourself.

Saying this out loud is deliberate. It keeps the review burden
proportionate: validate mechanically, trust socially, fix fast. A repo
that treated every wig as hostile code would need a review process
nobody would sustain, and it would be defending against a threat that
does not exist.

## So what is worth reporting

**A wig that does the wrong thing.** Open a normal issue. This is public
data, there is nothing to embargo, and the fix is usually a note on the
entry or deleting a file. Please say which wig and what your device
actually did.

**A wig you believe was contributed dishonestly**, such as fittings that
look rubber-stamped, or a bulk conversion of somebody else's database
presented as hardware-proven work. Open an issue or email
**david.a.bailey@gmail.com** if you would rather not do it in public.
Contributions here rest on one declaration being true, and that is worth
protecting.

**A real vulnerability in the tooling.** The validator and the workflows
in `.github/workflows/` are code, and code can be wrong. If you find a
way to make CI execute something it should not, leak a token, or push to
the repository, do not open a public issue. Email
**david.a.bailey@gmail.com** with what you found and how to reproduce
it. You should get an acknowledgment within a couple of days.

## What signatures do and do not prove

Fittings can carry an ed25519 signature, made with a key generated on
the fitter's own HAIR install.

A valid signature proves one thing: the fitting record has not been
altered since it was recorded on that install. It also means fittings
sharing a key came from one install, which is why CI flags two different
handles signing with the same key.

It does not prove identity. Nobody verified who the fitter is, the
handle is whatever they typed, and a GitHub handle is checkable only by
asking that person. It does not prove the codes are safe, correct, or
that they came from anywhere in particular. Unsigned fittings are
perfectly valid here; they are simply self-reported.

None of this is a chain of trust and the documentation should not
pretend otherwise. It is tamper-evidence on a social claim.

## Where the strict gate actually is

Entering this repository needs one complete fitting from a named person.
If that turns out to be wrong, a wig does not work and the file gets
deleted.

[WigFactory](https://github.com/DAB-LABS/WigFactory) is the gate that
matters, because that is where a code set becomes generated code people
install. It needs three complete fittings from three distinct GitHub
handles with no failed signals. Being wrong there means a published
integration misbehaving under the project's name, so the bar sits there
rather than here.

## Reporting HAIR itself

Anything about the integration rather than the data belongs on
[HAIR's security policy](https://github.com/DAB-LABS/HAIR/blob/main/SECURITY.md).

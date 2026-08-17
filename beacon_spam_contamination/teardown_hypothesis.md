# Beacon Spam / Wardrive Cross-Contamination - Teardown Hypothesis

**Status: CLOSED. Hypothesis ruled out.** See Resolution below.

## Background

WiGLE has flagged accounts (including my own, later cleared) for beacon-spam-poisoned
uploads, across multiple files over many months. WiGLE staff have separately confirmed
seeing similar cases predominantly from Biscuit/Marauder devices.

The assumption that this requires a second party running a spam tool nearby doesn't fit
that pattern well. Alternative hypothesis: **a firmware/app teardown bug**, not third-party
interference. Beacon spam and wardriving both run through the same radio chip and the same
underlying scan/attack code. If stopping a spam mode doesn't fully kill the background
transmit task before wardrive mode starts, the device could pick up its own leftover spam
beacons and log them as "discovered" networks with no second device or bad actor required.

This was consistent with a known issue: the Biscuit app has occasionally failed to actually
stop the active mode while indicating it had, requiring a manual reset to clear.

## Method

Two identical Biscuit Ultra units:
- **Device A - Ground Truth.** Runs a continuous, independent WiFi scan for the session.
  Never runs spam mode. Confirms what's actually being transmitted, independent of what
  Device B's own log says about itself.
- **Device B - Test Unit.** Runs the actual spam → stop → wardrive transition under test.

Both stationary, close enough that A can clearly hear B.

For each trial: start a spam mode on B, stop it (varying method/speed), start wardrive
immediately after, run ~30s, then check both logs for the known spam SSIDs (exact
joke-pack and Rick Roll lyric lists pulled directly from the firmware) appearing after
the stop timestamp.

## Results (2026-08-17)

| # | Spam mode | Stop method | Device | Result |
|---|---|---|---|---|
| 1 | Random | Normal stop | Android | Clean |
| 2 | Funny | Normal stop | Android | Clean |
| 3 | Funny | Rapid-cycled, force-stop via warning screen | Android | Clean |
| 4 | Funny | Normal stop | iPhone | Clean |
| 5 | Rick Roll | Rapid-cycled, force-stop via warning screen | iPhone | Clean |
| 6 | Rick Roll | Rapid-cycle, normal stop | iPhone | Clean |
| 7 | Funny | Rapid-cycle, normal stop | iPhone | Clean |
| 8 | Funny | Rapid-cycled, force-stop via warning screen | iPhone | Clean |

**8/8 clean.** No joke-pack or Rick Roll SSIDs, and no unfamiliar high-entropy/open
SSIDs, appeared in any wardrive log across either platform, any spam mode tested, or any
stop method (normal, rapid-cycled, or force-stop via warning screen).

App/firmware at time of testing: app `1.0.20` (Beta 5 on some Android runs, no Beta tag
on iPhone runs), firmware `v1.5.0`.

## Resolution

I asked Hedge directly, since he knows the app/firmware internals: **is the "stuck,
needs reset" issue capable of leaving spam mode silently running while the device
also logs a wardrive?**

His answer: **"0 chance."**

The "stuck" symptom is a real issue, but it's an **app/device desync** - the app can
lose sync with what the device is actually doing (e.g. showing the wrong state, or
requiring a reset to resync) - not a case where the device is simultaneously running
spam and wardrive. The firmware architecture doesn't allow a dual scan/attack state
at all; that's not a mode the device can enter, stuck or otherwise. My original framing
of this as a possible incomplete-teardown bug was based on a mistaken assumption about
how the app/device relationship works. Hedge corrected this directly and it rules the
hypothesis out.

**Bottom line: I was wrong about the mechanism.** The 8/8 clean test results are
consistent with that -- there was nothing to catch, because the thing I was testing
for isn't possible on this firmware.

The original question -- what actually caused the multi-month contamination WiGLE
found across my account and others with "similar conditions" -- remains open. This
write-up is being kept as a record of a hypothesis that was tested rigorously and
ruled out, not deleted, since a documented dead end is still useful context for anyone
else looking at this problem.

## What's still unknown

- What the actual contamination mechanism was, if not this.
- Whether it's still an active issue on current firmware, or something that's already
  been resolved incidentally by unrelated fixes.

If you're reading this because you're chasing the same problem: this specific theory
doesn't hold up. Worth ruling out other angles (client-side app bugs unrelated to
device state, third-party interference after all, or something in WiGLE's own
ingestion pipeline) before revisiting device-side teardown theories.

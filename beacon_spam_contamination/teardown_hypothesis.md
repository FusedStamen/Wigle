# Beacon Spam / Wardrive Cross-Contamination - Teardown Hypothesis

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

This is consistent with a known issue: the Biscuit app has occasionally failed to actually
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
stop method (normal, rapid-cycled, or force-stop via warning screen). Rick Roll and Funny favored for easier detection.

App/firmware at time of testing: app `1.0.20` (Beta 5 on some Android runs, no Beta tag
on iPhone runs), firmware `v1.5.0`.

## Interpretation

This doesn't rule the hypothesis out, but it means it isn't reproducible on current
firmware under the conditions tested. Possibilities:
- The bug was real and has since been patched in a recent app/firmware update
  (there have been recent releases, it's worth checking changelogs for anything touching
  scan-mode transitions, task cleanup, or the stop/scan command path).
- The actual contamination mechanism is something other than a live orphaned task such as
  stale in-memory SSID list state rather than a still-transmitting background
  process - which wouldn't necessarily show up the way these trials were designed to
  catch it.
- The trigger condition is more specific than anything tried here (particular timing
  window, a different mode combination, an older firmware version, specific hardware).

## Next steps (if picked back up)

- Check Biscuit changelog for any recent fix touching mode transitions / scan-stop /
  task cleanup.
- Ask Hedge whether the "stuck, needs reset" symptom he's seen maps to the same code
  path tested here, or something else.
- If a changelog entry turns up something relevant, that alone may be enough to
  corroborate the theory without further live testing.

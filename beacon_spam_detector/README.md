## wigle_beacon_spam_detector.py *(in progress)*

Scans WiGLE-format CSVs for signatures consistent with beacon spam / SSID spoofing tools, without requiring a personal baseline or historical dataset. Built after a false-positive ban investigation revealed WiGLE's anti-cheat cannot currently distinguish a contributor who broadcasts spoofed beacons from a contributor who simply drives past someone else's spoofing device and picks it up passively in a normal scan.

**Goal:** give contributors and platform maintainers a way to independently verify whether flagged data was likely fabricated by the account holder or picked up incidentally, rather than relying on presence-of-fake-data alone as a proxy for fault.

---

### Detection modules

| Module | Signal | Notes |
| --- | --- | --- |
| Dictionary/joke-pack matcher | SSID text against a known canned-phrase wordlist | Catches common "funny" spam packs (e.g. templated joke SSID lists) |
| Sequential/template matcher | Structural check for numbered or incrementing SSID prefixes | Catches lyric/message-spelling spam regardless of content |
| Entropy × AuthMode scorer | SSID randomness (character entropy) cross-referenced against AuthMode | High-entropy SSID + `[OPEN]` auth is a strong indicator; real networks with unusual/randomized names are still almost always encrypted - validated against real-world false-positive cases (factory-default-looking SSIDs on legitimately secured networks) |
| Burst-density scorer | New-BSSID rate per second, evaluated against the log's own internal distribution | Self-normalizing - no external baseline needed, so it doesn't false-positive on multi-antenna/multi-node rigs with naturally higher capture rates |
| GPS-churn scorer | Implied speed between consecutive fixes | Flags physically implausible location jitter consistent with spoofed or simulated GPS |

Each module scores independently; results are aggregated per cluster/time-window into a single report showing which signal(s) tripped and why, rather than a single opaque flag.

---

### Validation

Tested against:
- Real wardrive logs (clean, no known spam) - zero false positives, including on unusually-named-but-legitimately-encrypted networks
- Synthetic test files covering three known spam styles (randomized SSIDs, canned joke-list SSIDs, templated/sequential SSIDs)

---

### Status

Early-stage, self-contained (no baseline dataset required) - designed to be pointed at a single log file with zero setup.

Built for two audiences:
- **Contributors** who want to check their own logs before uploading, or investigate a suspicious flag/ban, without needing to trust a black-box platform decision.
- **Platform maintainers** evaluating whether flagged data was likely fabricated by the account holder versus picked up passively from a nearby spoofing source - a distinction current detection doesn't appear to make.

This project exists because that gap cost a long-time contributor their account and years of data temporarily while an investigation took place. The aim isn't to attack detection systems - it's to make attribution checkable by anyone, not just assumed from the presence of fake data alone.

It's also meant to close the loop before a ban happens, not after. Right now the only way to find out your data looks suspicious is to upload it, get flagged, and hope someone investigates. This lets anyone check a log on their own machine first - same detection logic a platform would use, just accessible before the upload, not as a consequence of it.

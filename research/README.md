# `research/` — raw working notes

These are the **unpolished source notes** behind [the main writeup](../README.md). They are kept
verbatim (minus any private network details) so you can see the sourcing and the confidence level
behind each claim rather than taking the summary on faith.

They are **working documents** — several are marked `IN PROGRESS` and will be updated as findings
land on real hardware.

| File | Topic | Key takeaway |
|---|---|---|
| [`01-chip-id.md`](01-chip-id.md) | Chip / module identification | "FFS" is Amazon Frustration-Free Setup, not a brand. This is genuine Sengled with in-house modules (FCC `2AGN8`). Only the **ESP8266EX / WF863** variants are flashable. |
| [`02-ota-path.md`](02-ota-path.md) | Is there a no-solder OTA path? | No. `tuya-convert` / `tuya-cloudcutter` are disqualified twice over — wrong silicon *and* wrong vendor. But Sengled's dead cloud can be replaced locally. |
| [`03-uart-flash.md`](03-uart-flash.md) | Serial flashing procedure | Mains safety first: the driver is a **non-isolated SMPS**, so board "ground" can sit at line potential. Adapter ON ⇒ mains OFF, always. |
| [`04-ha-endstate.md`](04-ha-endstate.md) | Firmware choice + HA end state | Target: one `light` entity per bulb, RGBCW, zero outbound internet. |

## Reading these

- **Confidence is marked inline.** Claims tagged *high confidence* are backed by primary sources
  (FCC grant records, upstream README text). Anything tagged 🚧 or "unconfirmed" has not been
  verified on hardware.
- **Findings are numbered** (`Finding 1`, `F1`, …) and referenced from the main README.
- **Nothing upstream is vendored here.** Prior-art projects are referenced by URL only — see the
  [credits section](../README.md#7-credits--prior-art).

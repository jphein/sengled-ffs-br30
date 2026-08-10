# `research/` — raw working notes

These are the **unpolished source notes** behind [the main writeup](../README.md). They are kept
verbatim (minus private network details) so you can see the sourcing and confidence level behind
each claim rather than taking the summary on faith.

| File | Topic | Key takeaway |
|---|---|---|
| [`01-chip-id.md`](01-chip-id.md) | Module identification | Read the **FCC ID** on the bulb body. `WF863` = ESP8266 = flashable; `WF864`/`EMW3091` = MXCHIP MX1290 = not. The **antenna is the fastest visual tell**: white ceramic block vs plain etched trace. |
| [`02-ota-path.md`](02-ota-path.md) | Is there a no-solder path? | **Yes — and it's better than flashing.** The bulb is a Sengled **W12-N15**; `SengledTools` provisions it locally and `sengled_udp` drives it from HA over UDP 9080. No cloud, no broker, no flashing. PR #63 was tested on this exact model. |
| [`03-uart-flash.md`](03-uart-flash.md) | Serial flashing procedures | Full mains-safety treatment first: the driver is a **non-isolated SMPS**, so board "ground" can sit at line potential. Adapter ON ⇒ mains OFF, always. |
| [`04-ha-endstate.md`](04-ha-endstate.md) | Firmware choice + HA end state | Probably **4-channel RGBW**, not 5-channel RGBCW — and possibly a driver IC rather than direct PWM. `restore_mode: ALWAYS_ON` is non-negotiable for a bulb. |

## Where the notes and the writeup diverge

The notes are a **record of the investigation, including its wrong turns**. Where they contradict
each other, the main README states the resolution:

- **`04` predates the module identification** and guesses Beken/ESP8285. `01` and `02` supersede it:
  the silicon is Sengled's own WF86x family, most likely MXCHIP MX1290.
- **`01` states no LibreTiny port exists for MX1290**; `02` verified LibreTiny's CPU list entry
  *"MX1290 (RTL8710BN)"*. The README resolves toward `02` — the **silicon** is supported, the
  **device** is unexplored.
- **`01` reads "FFS" as Amazon Frustration-Free Setup**; `02` traces it to the SKU fragment
  `W12-N15WFFS2P`. Both land in the same place: FFS is not a third-party brand.
- **`01` rates the WF863/WF864 split near 50/50**; `02` pins the model via a Best Buy SKU and calls
  WF864 likely. The README presents WF864 as *expected* while telling you to read the label —
  because the recommended path works either way.

## Reading these

- **Confidence is marked inline.** Claims tagged *verified* are backed by primary sources (FCC grant
  exhibits, upstream README text, locally installed tooling). Anything tagged 🚧 or *inferred* has
  not been confirmed on this hardware.
- **Findings are numbered** (`Finding 1`, `F1`, `C1`, …) and referenced from the main README.
- **Nothing upstream is vendored here.** Prior-art projects are referenced by URL only — see the
  [credits section](../README.md#9-credits--prior-art). FCC exhibit photographs are likewise linked,
  not reproduced: the test lab's report carries a *"not to be reproduced except in full"* notice.

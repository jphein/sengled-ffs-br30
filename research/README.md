# `research/` — raw working notes

These are the **unpolished source notes** behind [the main writeup](../README.md). They are kept
verbatim (minus private network details) so you can see the sourcing and confidence level behind
each claim rather than taking the summary on faith.

| File | Topic | Key takeaway |
|---|---|---|
| [`01-chip-id.md`](01-chip-id.md) | Module identification | Module is `WF864SM-M6` = MXCHIP MX1290 = **Realtek RTL8710BN**. The `BOOT`-vs-`IO0` pad is the sharpest discriminator; the antenna is the fastest. Includes the verified UART2 procedure. |
| [`02-ota-path.md`](02-ota-path.md) | Is there a no-solder path? | **Yes, and it's better than flashing.** SengledTools provisions locally; `sengled_udp` drives the bulb from HA over UDP 9080. Also documents the `--force-flash` brick hazard. |
| [`03-uart-flash.md`](03-uart-flash.md) | Serial flashing procedures | Full mains-safety treatment. The driver is a **non-isolated SMPS**, so board "ground" can sit at line potential. Adapter ON ⇒ mains OFF, always. |
| [`04-ha-endstate.md`](04-ha-endstate.md) | Firmware choice + HA end state | Written before the module was identified — see the divergence table below. |
| [`05-ha-features.md`](05-ha-features.md) | Feature → HA entity matrix | The full UDP capability surface, what's MQTT-only, the protocol caveats that shape the design, and a smoke-test plan. |

## Where the notes and the writeup diverge

These are **working documents** — a record of the investigation *including its wrong turns*. Where
they contradict each other, the main README states the resolution:

| Conflict | Resolution in the writeup |
|---|---|
| `04` assumes ESP8266/Beken and builds ESPHome configs around it | Superseded. The module is RTL8710BN — those configs apply to *other* Sengled models, not this bulb. |
| `01` first said **no LibreTiny port exists** for MX1290, then corrected itself | The correction is right: MX1290 **is** an RTL8710BN rebadge, so ESPHome `rtl87xx:` and OpenBeken both support it. Wired flashing is a real target. |
| `01` reads "FFS" as Amazon Frustration-Free Setup; `02` traces it to SKU `W12-N15WFFS2P` | Both. It's Amazon's feature name, which Sengled encoded into its own SKU. Not a brand either way. |
| `01` rated the WF863/WF864 split near 50/50 | Closed by physical evidence: `2AGN8-WF864`. |
| `01`/`02` carry an unsourced claim about the vendor's finances, and a flat "zero prior art" | **Both narrowed.** The financial claim is unverified and is deliberately **not** published — only the documented outages are. And prior art is zero for *WF864 specifically*; the same silicon has strong precedent (Solis S3 / EMW3080-E). |
| `03` documents ESP8285 and Beken procedures | Neither matches the hardware. The applicable route is RTL8710BN + `ltchiptool` + `realtek-ambz`. |

## Reading these

- **Confidence is marked inline.** Claims tagged *verified* are backed by primary sources — FCC
  grant exhibits, upstream source code, locally installed tooling. Anything tagged 🚧 or *inferred*
  is not confirmed on this hardware.
- **Findings are numbered** (`Finding 1`, `F1`, `C1`, …) and referenced from the main README.
- **Some notes flag errors in their siblings** rather than editing them (see `01`'s Findings 15–16).
  That's deliberate — the flag and the flagged claim are both preserved.
- **Nothing upstream is vendored.** Prior-art projects are referenced by URL only. FCC exhibit
  photographs are likewise linked, not reproduced: the test lab's report carries a *"not to be
  reproduced except in full"* notice.
- **Scrubbed for publication.** Real SSIDs, private LAN addresses, internal hostnames, device MACs
  and absolute local paths have been replaced with placeholders. The `B0:CE:18` OUI is a public IEEE
  vendor registration — not a device address — and is kept deliberately as evidence of Sengled
  provenance.

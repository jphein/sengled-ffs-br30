# `research/` — raw working notes

These are the **unpolished source notes** behind [the main writeup](../README.md). They are kept
verbatim (minus private network details) so you can see the sourcing and confidence level behind
each claim rather than taking the summary on faith.

| File | Topic | Key takeaway |
|---|---|---|
| [`01-chip-id.md`](01-chip-id.md) | Module identification | Module is `WF864SM-M6` = MXCHIP MX1290 = **Realtek RTL8710BN**. The `BOOT`-vs-`IO0` pad is the sharpest discriminator; the antenna is the fastest. Includes the verified UART2 procedure. |
| [`02-ota-path.md`](02-ota-path.md) | Is there a no-solder path? | **Yes, and it's better than flashing.** SengledTools provisions locally; `sengled_udp` drives the bulb from HA over UDP 9080. Also documents the `--force-flash` brick hazard. |
| [`03-uart-flash.md`](03-uart-flash.md) | RTL8710BN UART procedure | Rewritten for the confirmed silicon: download-mode entry, `ltchiptool`, building ESPHome for `rtl87xx`, and the full mains-safety treatment. |
| [`05-ha-features.md`](05-ha-features.md) | Feature → HA entity matrix | The full UDP capability surface, what's MQTT-only, the protocol caveats that shape the design, and a smoke-test plan. |
| [`06-our-ha-app.md`](06-our-ha-app.md) | The replacement-cloud add-on | **The bulb persists absolute URLs baked in at pairing time** — pair from the wrong subnet and only re-pairing fixes it. Also: effects/gradient/groups are reachable over MQTT, so they were missing from the *pipe*, not the bulb. |
| [`07-w12n15-join-debug.md`](07-w12n15-join-debug.md) | The join-failure investigation | **The wizard's success messages are false positives** (`except socket.timeout: pass` falls through to `success()`). Then the network evidence: association completes, DHCP dies at OFFER→REQUEST. |

## Where the notes and the writeup diverge

These are **working documents** — a record of the investigation *including its wrong turns*. Where
they contradict each other, the main README states the resolution:

| Conflict | Resolution in the writeup |
|---|---|
| A fourth note (`04-ha-endstate.md`) built ESPHome configs on an ESP8266/Beken assumption | **Withdrawn from this repo.** It predates the module identification and its conclusions don't apply to RTL8710BN hardware. `05-ha-features.md` is the current, correct source for the Home Assistant surface. |
| `01` first said **no LibreTiny port exists** for MX1290, then corrected itself | The correction is right: MX1290 **is** an RTL8710BN rebadge, so ESPHome `rtl87xx:` and OpenBeken both support it. Wired flashing is a real target. |
| `01` reads "FFS" as Amazon Frustration-Free Setup; `02` traces it to SKU `W12-N15WFFS2P` | Both. It's Amazon's feature name, which Sengled encoded into its own SKU. Not a brand either way. |
| `01` rated the WF863/WF864 split near 50/50 | Closed by physical evidence: `2AGN8-WF864`. |
| `01`/`02` carry an unsourced claim about the vendor's finances, and a flat "zero prior art" | **Both narrowed.** The financial claim is unverified and is deliberately **not** published — only the documented outages are. And prior art is zero for *WF864 specifically*; the same silicon has strong precedent (Solis S3 / EMW3080-E). |
| `03` documents ESP8285 and Beken procedures | Neither matches the hardware. The applicable route is RTL8710BN + `ltchiptool` + `realtek-ambz`. |

## ✅ Resolved

The blocker in these notes is **solved**: the W12-N15 clears the DHCP `BROADCAST` flag and silently
discards a broadcast `OFFER`. An unconditional `dhcp-broadcast` on the DHCP server was overriding
that for every client. Scoping it (`dhcp-broadcast=tag:needs-broadcast`) produced a compliant unicast
offer, and the bulb immediately sent its first-ever `DHCPREQUEST` → `DHCPACK`, took a lease, stayed
stable, and reached the add-on's endpoints. **No soldering required.** Full write-up in
[the main README](../README.md#-solved-the-bulb-only-accepts-a-unicast-dhcp-offer).

Also settled by that lease: the bulb's own DHCP hostname is **`Sengled_WiFi_Color_W12-N15`**,
confirming it is the **colour** variant — upstream's compatibility matrix calls `W12-N15` a "WiFi
white LED", which is a documentation error.

## Field-test reality check

**The symptom description changed three times, and each change killed hypotheses.** Worth reading in
order if you want the actual epistemics:

1. *"Bulb accepts credentials but never joins"* → suggested tool-side incompatibility (RC4 key or
   schema) or AP-side association failure. `07` §6–§7 works through both.
2. *"The wizard's success messages prove nothing"* (`07` §1–§4) → correct about the code, but it turned
   out the credentials really were accepted, so this was a **methodology** finding rather than the
   fault.
3. *"Association completes; DHCP dies at OFFER→REQUEST"* → the real localisation, and it voided every
   earlier candidate at once.
4. *"The server was forcing broadcast; the bulb had asked for unicast"* → the actual cause. Note the
   contents of the offer were never the problem — its **framing** was. Every options-based hypothesis
   (119, bloat, option 54) was looking at the wrong field of the packet.

`07` also contains an explicit **⛔ do-not-run** finding: the "build a minimal test SSID" experiment
is pointless here, because the SSID already *is* that minimal configuration across all nine APs. That
kind of negative result is as valuable as a fix and is why it's published.

`06` was written before the add-on met a bulb, and its §5 ranked *"whether the W12-N15 / RTL8710BN
bulb works with SengledTools at all"* as **risk #1**. That risk materialised: provisioning does not
complete on our hardware. See
[the open issue](../README.md#-open-issue-provisioning-does-not-complete-on-w12-n15).

Two things worth noting about how that played out:

- **The prediction was right but the stated reason wasn't.** `06` pinned the risk on upstream's
  `SUPPORTED_TYPECODES` / `COMPATIBLE_IDENTIFY_MARKERS` constants. Reading the code, those only
  categorise *flashing* support for a later prompt — they don't gate `--setup-wifi`, and there's no
  early abort before credentials are sent. So the risk was real, the mechanism named for it was not.
- **`06`'s §5.6 predicted the add-on plumbing (apk package names, `bashio` option rendering) would
  "fail loudly at build/start, not subtly."** Both did exactly that — see the build notes in the
  main writeup.

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

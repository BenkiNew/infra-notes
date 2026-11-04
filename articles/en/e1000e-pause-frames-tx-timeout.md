# "Transmit queue timed out" on Intel I219-LM: it looks like a pause-frame storm, not memory pressure or Wi-Fi

**Author:** [BenkiNew](https://github.com/BenkiNew) · **Date:** 04.11.2026

Original notes, per-minute counters (CSV), and the collection script: [Gist](https://gist.github.com/BenkiNew/8309e06fb9810ba6a5f988dbc1efb552).

This is a write-up of one recurring network-adapter failure on a Linux server, the evidence we collected, and the limits of the conclusion. Host names, addresses, and internal service names are omitted; counter values come from real measurements. These are three incidents on one server: a small sample, not statistics.

## Symptom

A server on a local network with an Intel Ethernet Connection (2) I219-LM, `e1000e` driver, Linux 7.2.x and 7.3.x. Three times in a week the adapter stopped transmitting:

- `NETDEV WATCHDOG: transmit queue 0 timed out`;
- `Reset adapter unexpectedly`;
- in the severe case, thousands of `Detected Hardware Unit Hang` messages about every 2 s.

Carrier stayed "up", but the network did not work. In the severe case only a reboot recovered it. Link down/up, unbind, PCI reset, and reloading the module did not help, and unbind left the system without the interface (`Failed to disable ULP`, probe error -3). Do not repeat unbind on a production system.

## What we ruled out, and how

| Hypothesis | Check | Result |
| --- | --- | --- |
| Memory shortage or swap storm | `sar -B/-u/-S` in the event windows, compared with the day's percentiles | in two incidents paging and iowait were below the day's median (27-46th percentile); only the third was an outlier (98th). No common cause |
| Wi-Fi failure as the trigger | NetworkManager and wpa_supplicant logs before each event | in two incidents Wi-Fi dropped 1.5-2 min earlier; in the third it was healthy. Not a required condition |
| PCI runtime PM / D3 | `power/control`, `runtime_status`, `runtime_suspended_time` | `on`, `active`, 0 s suspended |
| ASPM | `lspci -vv` | no LnkCap entry for the integrated I219, not applicable |
| EEE, GSO/GRO, TSO | `ethtool -k`, `--show-eee` | already disabled; the failure still recurred |
| K1 (PHY power state) | `ethtool --set-priv-flags ... disable-k1 on` | disabled; the failure still happened |
| Kernel version | 7.2.8 -> 7.3.1 | failure on both |
| Physical link loss | `NIC Link is Down` before the event | absent |

## What matched: unbalanced XOFF

`ethtool -S` exposes `rx_flow_control_xon` and `rx_flow_control_xoff`: pause frames from the link partner (the switch). We began saving these counters once a minute together with `tx_timeout_count`.

Normally XON and XOFF grow in pairs: the partner pauses transmission and then releases it. During the failures it was different:

| Event | Δ XOFF per minute | Δ XON in the same minute | tx_timeout |
| --- | --- | --- | --- |
| incident 2, minute of the first timeout | +225 | +8 | 0 -> 1 |
| incident 3, first minute | +231 | +10 | 0 -> 1 |
| incident 3, second minute | +337 | +14 | 1 -> 3 |
| incident 3, third minute | +240 | +11 | 3 -> 5 |

Control: before and after those minutes the pairs were equal. Large balanced bursts (+201/+201, +258/+258, +225/+225) caused no timeouts. One more indirect match: after the reboot that followed the first incident, the counters already showed 51 XOFF against 4 XON.

## Mechanism: a hypothesis this supports but does not prove

The switch sends XOFF when its port buffer overflows, for example because of a slow client. If XON is late or lost, the adapter cannot transmit for more than 5 s, `e1000e` reports "transmit queue timed out" and resets the adapter. In the severe case the reset does not bring the transmit queue back.

## What we did

- Disabled receiving and sending pause frames and their autonegotiation: `ethtool -A <interface> autoneg off rx off tx off`; in NetworkManager, `ethtool.pause-autoneg=no`, `ethtool.pause-rx=no`, `ethtool.pause-tx=no`. Side effect: when the switch is congested, packets are dropped (TCP copes) instead of stalling the whole port.
- Added a watchdog with bounded steps: one soft link down/up, then a controlled reboot with a per-day limit.
- Enabled the hardware watchdog and per-minute counter logging.

Note: changing pause parameters resets the adapter, so apply it on a live system at a quiet moment.

## What we do not know

- The sample is three incidents. The correlation with an XOFF burst is accurate to the minute, but the counters were sampled once a minute.
- Who actually sends the XOFF, the switch or another device on the network, is not established; we have no access to the switch.
- Whether disabling pause removes the failures is not yet verified. The success criterion: several weeks without unbalanced XOFF bursts and without `tx_timeout_count` > 0. We will add the result to this text.
- A physical fault of this particular adapter or port cannot be excluded. The most reliable workaround is a second network card with a different chip.

## How to check on your system

Save once a minute:

```bash
ethtool -S eth0 | grep -E 'rx_flow_control_(xon|xoff)|tx_timeout_count'
```

The suspicious sign is XOFF growing by hundreds per minute with little XON. If you see the same, write in [Discussions](https://github.com/BenkiNew/infra-notes/discussions) with your adapter model, kernel, and a minimal excerpt of the counters.

# A Comprehensive History of USB Charging Standards

*From 2.5 W origins to the 240 W universal future | 1996 – 2026 and beyond*

---

## Introduction

USB was conceived in the mid-1990s as a data bus for low-speed peripherals. Its power capabilities were incidental — just enough to power a mouse or keyboard. Nobody planned it to charge anything meaningful. Yet over three decades, through fierce proprietary competition, open standardisation efforts, and ultimately regulatory intervention, USB became the universal power delivery standard for virtually every consumer electronic device on the planet.

This document traces that journey from the very first 2.5 W USB specification through to the 240 W Extended Power Range standard of today and the unified future ahead.

---

## Era 1: The Origins (1996–2009)

In the beginning, USB was purely about data. The original USB 1.0 specification, published in 1996, defined a maximum of 500 mA at 5 V — just 2.5 W. This was enough to power attached peripherals but completely inadequate for charging batteries. USB 2.0 in 2000 dramatically improved data speeds but left the power budget unchanged.

The arrival of smartphones changed everything. Suddenly millions of people needed to charge battery-powered devices from USB ports, and 500 mA was painfully slow. The USB Implementers Forum responded with Battery Charging 1.0 in 2007 (revised to 1.1 in 2009 and 1.2 in 2010), which formally defined how a dedicated charging port could bypass USB data negotiation and deliver up to 1.5 A at 5 V — bringing the maximum to 7.5 W.

Apple, however, took a different path. Rather than following the BC 1.2 specification, Apple used proprietary resistive voltage dividers on the D+ and D− data pins to signal charger capacity. This allowed Apple chargers to deliver up to 12 W but created an incompatibility with generic USB chargers that would persist for years. This set the template for the decade of fragmentation that followed.

---

## Era 2: The Proprietary Wars (2012–2016)

As smartphones became more powerful and batteries larger, the industry fragmented into competing proprietary fast-charging ecosystems. Each major manufacturer developed their own protocol, incompatible with everyone else's.

### USB Power Delivery 1.0 (2012)

The USB Implementers Forum attempted to get ahead of fragmentation by publishing USB Power Delivery 1.0 in 2012. It defined five fixed power profiles supporting 5 V, 12 V, and 20 V — allowing up to 60–100 W over a USB connection. However, it used complex BFSK (Binary Frequency Shift Keying) signalling on the VBUS power line, was expensive to implement, and was slow to be adopted. Few devices used it at launch.

### Qualcomm Quick Charge 2.0 (2013)

Qualcomm's Quick Charge 2.0, launched in 2013, became the first widely adopted fast-charging technology. By negotiating between fixed voltage levels (5 V, 9 V, and 12 V), it achieved up to 18 W — dramatically faster than BC 1.2. However, it required Qualcomm silicon on both sides of the connection and was completely proprietary. Its success sparked a fast-charge arms race.

### USB-C Connector and USB PD 2.0 (2014)

The USB Type-C connector specification was finalised in August 2014. Its reversible 24-pin design included dedicated CC (Configuration Channel) pins — a clean, separate channel for power negotiation rather than overloading the data or power lines. USB PD 2.0, released alongside the USB 3.1 specification, moved signalling to these CC pins, enabling faster and cleaner negotiation. PD 2.0 defined four fixed voltage levels: 5 V, 9 V, 15 V, and 20 V, supporting up to 100 W.

### VOOC and the Chinese Manufacturers (2014)

Oppo introduced VOOC in 2014 with a fundamentally different approach: deliver high current at low voltage, moving heat management from the phone into the charger brick. This achieved up to 25 W while keeping the phone cool but required proprietary cables and connectors, making it entirely incompatible with USB PD. The same technology was licensed to OnePlus as Warp Charge and Realme as Dart Charge.

### Qualcomm Quick Charge 3.0 (2016)

QC 3.0 introduced INOV — Intelligent Negotiation for Optimum Voltage — allowing the charger and device to negotiate the ideal voltage in fine 200 mV steps rather than jumping between fixed tiers. This reduced heat generation and improved efficiency while staying within the 18 W ceiling. Still proprietary, still widespread in mid-range Android devices even today.

---

## Era 3: Convergence Begins (2017–2020)

The release of USB PD 3.0 with PPS in 2017 marked the pivotal turning point. For the first time, the open standard could match or exceed the capabilities of proprietary systems. The industry began a slow but irreversible convergence toward the open standard.

### USB PD 3.0 with PPS (2017)

PPS — Programmable Power Supply — was the key innovation of PD 3.0. Unlike fixed voltage tiers, PPS allows millivolt-level dynamic voltage and current adjustment in real time, negotiated continuously as the battery charges. The charger can dial in exactly the voltage the battery needs at each moment in the charging cycle, dramatically reducing heat generation and enabling faster, healthier charging.

Samsung adopted PPS for its Galaxy S-series, making it mainstream almost immediately. Apple, Google, and Dell standardised their charging ecosystems around PD 3.0. The USB-IF introduced a 'Certified USB Fast Charger' logo for PPS-compliant chargers in 2018.

### Quick Charge 4.0 and 4.0+ (2017)

Quick Charge 4.0 represented a strategic retreat from proprietary exclusivity. Instead of a new independent protocol, QC 4.0 was built on top of USB PD 3.0 with PPS. For the first time, a QC 4.0 device could charge on any generic USB PD charger, just at reduced speed. QC 4.0+ added thermal telemetry — the phone tells the charger its real-time temperature and the charger adjusts output accordingly. Maximum power reached 27 W.

### GaN Chargers Go Mainstream (2019)

Gallium Nitride (GaN) transistors began replacing silicon in consumer chargers from around 2019. GaN switches at much higher frequencies than silicon, requiring smaller transformers and capacitors. The result was dramatic: a 65 W GaN charger could fit in the same physical package as a 20 W silicon charger. GaN permanently changed the form factor of charging hardware.

### Quick Charge 5 (2020)

Quick Charge 5 fully embraced the PD 3.1 foundation and added sophisticated real-time thermal telemetry. The phone continuously streams battery temperature data to the charger, enabling output adjustment at millisecond precision. With QC 5, Qualcomm effectively ended the format war and joined the open standard ecosystem. Maximum power reached 100 W or more.

---

## Era 4: Unification and Regulation (2021–Present)

The combination of USB PD 3.1 breaking the 100 W barrier and the European Union mandating USB-C created the conditions for the complete convergence of the charging ecosystem.

### USB PD 3.1 — Extended Power Range (2021)

USB PD 3.1 shattered the 100 W ceiling by introducing EPR (Extended Power Range). Three new fixed voltage levels (28 V, 36 V, and 48 V) allow charging at up to 240 W (48 V × 5 A). EPR cables with upgraded E-Marker chips are required for voltages above 20 V — the E-Marker chip signals to the charger that the cable can safely handle the higher voltage before power is applied.

PD 3.1 also introduced AVS (Adjustable Voltage Supply) for the EPR range: 15–48 V in 100 mV steps. For the first time, gaming laptops, high-resolution monitors, and mobile workstations could be powered over a single USB-C cable, eliminating proprietary barrel connectors.

### EU Radio Equipment Directive 2022/2380

On October 4, 2022, the European Parliament voted 602 to 13 to mandate USB-C as the universal charger for small consumer electronics. The directive had two phases:

- **From 2024:** all new mobile phones, tablets, cameras, earbuds, handheld games consoles, and similar devices must use USB-C for charging.
- **From April 28, 2026:** all laptops with power consumption up to 100 W (and devices up to 240 W covered by EPR) must charge via USB-C.

Apple was forced to abandon Lightning on iPhone 15 in 2023. Proprietary laptop barrel connectors are now illegal for new products in Europe. The single most powerful force in the history of charging standardisation was not a technical specification but a regulatory instrument.

### USB PD 3.2 — SPR AVS (2023)

PD 3.2 brought AVS down from the EPR realm to the standard power range (SPR). Any device requesting more than 27 W must now support SPR AVS — adjustable voltage from 9–20 V in 100 mV steps. This makes fine-grained dynamic voltage adjustment mandatory for the mainstream charging market, not just high-power devices. The iPhone 17 adopted PD 3.2 SPR AVS at 40 W peak charging.

### UFCS — The Late Proprietary Attempt (2022)

In 2022, a consortium of Chinese manufacturers — Huawei, Honor, Oppo, Vivo, and Xiaomi — introduced UFCS (Universal Fast Charging Specification) aiming for cross-brand compatibility within the group. UFCS 2.0 followed in May 2025. It arrived years after USB PD had effectively won the format war, adding another layer of complexity rather than solving fragmentation. Its global relevance remains limited.

---

## Complete Timeline Reference

| Year | Standard | Max Power | Type | Key Detail |
|------|----------|-----------|------|------------|
| 1996 | USB 1.0 | 2.5 W | Open | First USB spec. Power purely incidental. Designed for mice and keyboards. |
| 2000 | USB 2.0 | 2.5 W | Open | Faster data, same power budget. Became universal connector for a decade. |
| 2007 | Battery Charging 1.0 | 7.5 W | Open | First spec exceeding 500 mA. Introduced dedicated charging ports. |
| 2009 | Apple proprietary | 12 W | Proprietary | Resistive D+/D− signalling. Incompatible with BC 1.2. Set fragmentation precedent. |
| 2010 | Battery Charging 1.2 | 7.5 W | Open | Formalised SDP, CDP, DCP port types. Still in every USB-A charger today. |
| 2012 | USB PD 1.0 | 100 W | Open | First real PD spec. Fixed profiles, BFSK signalling. Poorly adopted. |
| 2013 | Quick Charge 2.0 | 18 W | Proprietary | First widely-adopted fast charging. Sparked the proprietary arms race. |
| 2014 | USB-C + PD 2.0 | 100 W | Open | Reversible connector with CC pins. Fixed 5/9/15/20 V tiers. |
| 2014 | VOOC (Oppo) | 25 W | Proprietary | High current at low voltage. Heat in charger, not phone. Spawned Warp/Dart. |
| 2016 | Quick Charge 3.0 | 18 W | Proprietary | INOV: fine 200 mV voltage steps. More efficient than QC 2.0. |
| 2017 | USB PD 3.0 + PPS | 100 W | Open | Pivotal release. PPS: 20 mV steps, real-time dynamic voltage control. |
| 2017 | Quick Charge 4.0/4.0+ | 27 W | Mixed | Built on USB PD 3.0 + PPS. QC 4.0+ adds thermal telemetry. |
| 2018 | Huawei SuperCharge | 40 W+ | Proprietary | Proprietary system, later reaching 135 W. Limited to Huawei hardware. |
| 2019 | GaN mainstream | All wattages | Technology | GaN replaces silicon. Same power in dramatically smaller charger. |
| 2020 | Quick Charge 5 | 100 W+ | Mixed | Built on PD 3.1 foundation. Real-time thermal telemetry at ms precision. |
| 2021 | USB PD 3.1 EPR + AVS | 240 W | Open | Broke 100 W ceiling. New 28/36/48 V tiers. Needs EPR cable. |
| 2022 | EU Directive 2022/2380 | Law | Regulation | USB-C mandatory for phones 2024, laptops April 2026. |
| 2022 | UFCS | 240 W | Proprietary | Chinese OEM consortium standard. Limited global relevance. |
| 2023 | USB PD 3.2 SPR AVS | 100 W | Open | AVS mandatory for >27 W. 9–20 V in 100 mV steps. iPhone 17 uses it. |
| 2024 | EU phones mandate | Law | Regulation | All new phones must be USB-C. Lightning officially dead. |
| 2026 | EU laptops mandate | Law | Regulation | Proprietary laptop barrel connectors banned for new products. |

---

## Quick Reference Summary

| Standard | Max Power | Year | Summary |
|----------|-----------|------|---------|
| USB BC 1.2 | 7.5 W | 2010 | Foundation of USB-A charging. 3 port types. Still in every USB-A charger today. |
| USB PD 2.0 | 100 W | 2014 | First practical USB-C power. Fixed 5/9/15/20 V tiers. Foundation most chargers are built on. |
| USB PD 3.0 + PPS | 100 W | 2017 | Added PPS: fine 20 mV voltage steps. Dominant standard in 2026 smartphones. |
| Quick Charge 3.0 | 18 W | 2016 | Proprietary. Fine voltage via INOV. Still widespread in mid-range Android. |
| Quick Charge 4/5 | 27–100 W | 2017/2020 | Built on USB PD + PPS. QC5 adds thermal telemetry. Falls back to PD on any charger. |
| USB PD 3.1 EPR | 240 W | 2021 | Broke 100 W barrier. 28/36/48 V tiers. Needs EPR cable. Gaming laptops and monitors. |
| AVS | 240 W | 2021 | Fine voltage for EPR (15–48 V, 100 mV steps). PPS equivalent for high power. |
| USB PD 3.2 SPR AVS | 100 W | 2023 | Mandatory for >27 W devices. AVS to standard range. Used in iPhone 17. |
| VOOC / SuperVOOC | 240 W | 2014+ | Oppo/OnePlus proprietary. High current, low voltage. Fastest raw speed. Not PD compatible. |
| UFCS | 240 W | 2022 | Chinese OEM consortium. Cross-brand within Huawei/Oppo/Xiaomi group. Limited global relevance. |

---

## How the Future Looks

The charging ecosystem is converging toward a unified, intelligent, and ubiquitous standard.

### USB PD 3.2 with SPR AVS as the Universal Baseline

With >27 W devices now required to support SPR AVS, fine-grained dynamic voltage adjustment becomes the new normal for the entire mainstream charging market. By 2027 virtually every new phone, tablet, and laptop will negotiate PD 3.2 with AVS automatically.

### Proprietary Protocols Fade but Do Not Disappear

VOOC and SuperVOOC will persist in Oppo and OnePlus flagships where raw charging speed records matter to marketing. However, even proprietary systems will increasingly support USB PD as a fallback, reducing the frustration of incompatibility. The era of entirely non-PD charging hardware is ending.

### EPR 240 W Becomes Standard for High-Performance Laptops

Gaming laptops, workstations, and external GPU enclosures will fully transition away from proprietary barrel connectors. The legal mandate is already in force in Europe. The practical market shift is following globally even without legal compulsion, simply because USB-C EPR is more convenient for both manufacturers and consumers.

### Thermal Intelligence as the New Differentiator

Raw wattage is no longer the primary competition. The next frontier is smarter thermal management — chargers and devices that adapt in real time to battery chemistry, cell temperature, ambient temperature, and battery age to maximise charging speed while preserving long-term battery health. This is already happening in QC 5 and PPS implementations and will become more sophisticated.

### USB PD Everywhere in Infrastructure

USB-C PD ports are already appearing in aircraft seats, hotel rooms, conference tables, and street furniture. The long-term goal, articulated by both USB-IF and regulators, is charging as ubiquitous and invisible as Wi-Fi — a single cable that works everywhere for every device with no thought required.

### A Possible USB PD 4.0 Beyond 240 W

Specialised industrial, medical, robotic, and AI compute applications may eventually push requirements beyond 240 W. A future USB PD 4.0 specification is theoretically possible for these use cases. However, for all consumer devices, 240 W covers virtually every foreseeable application — the next USB PD revision is likely to focus on smarter protocols, better thermal reporting, and improved cable certification rather than simply higher wattage.

---

*End of document — USB Charging Standards History — May 2026*

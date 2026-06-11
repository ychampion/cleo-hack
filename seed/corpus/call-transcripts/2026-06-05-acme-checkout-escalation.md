# Call — Acme Robotics: checkout incident + renewal check-in

Date: 2026-06-05
Account: Acme Robotics
Participants: Maya Chen (Lumen), Sam Idris (Lumen), Dan Porter (Acme Robotics), Gina Tran (Acme Robotics)

---

**Sam Idris (Lumen):** Dan, Gina — thanks for jumping on. We wanted to talk live rather than keep going back and forth on tickets.

**Dan Porter (Acme Robotics):** Good, because email wasn't working. Here's where we are: three days of trying to upgrade from Team to Business and the checkout still throws a 500 every single time. I have 30 engineers starting Monday with no licenses. My CFO has asked me to price out Linear plus Geckoboard as a fallback. I'm not bluffing when I say this week decides whether we're a customer next quarter.

**Gina Tran (Acme Robotics):** To add detail for your engineers: it fails on the POST to /billing/checkout right after the card form submits. We've tried two corporate cards, three browsers, and an incognito session. Same 500 each time. It started the night your v2.3 release went out — it worked fine in May when we added two seats.

**Maya Chen (Lumen):** That timing matches what we're seeing. Engineering has it flagged P0; the regression is in the new billing flow that shipped with 2.3.

**Dan Porter (Acme Robotics):** Honestly, the frustrating part is the silence. If the upgrade page had a banner saying "we know, fix coming Thursday", I could plan around it. Instead each attempt looks like it might work and then dies. Tell me a date and I can defend it internally.

**Sam Idris (Lumen):** Fair. We'll get you a written ETA today and a manual seat provision in the meantime. While we have you — Gina, you had a list for the renewal conversation?

**Gina Tran (Acme Robotics):** Yes, three things. First, CSV export. Finance transcribes engagement numbers by hand every month for headcount planning and we already had one reporting error from a typo. Every other tool in our stack exports; it's genuinely odd that Lumen doesn't.

**Dan Porter (Acme Robotics):** Second, dashboard speed. Since 2.3 the main dashboard takes 12 to 30 seconds for us — before, maybe 8. Sixty engineers open it every morning. Gina thinks the new widget gallery loads assets for widgets we never use.

**Gina Tran (Acme Robotics):** And third, smaller one — the comparison view re-fetches everything on each filter change, around 10 seconds per click. Exploring a question across teams takes minutes of cumulative waiting.

**Maya Chen (Lumen):** All noted, with the perf regression tied to 2.3 specifically. Anything positive we should protect?

**Dan Porter (Acme Robotics):** The sprint health alerts. Two leads caught burnout patterns early because of them — that's the reason I'm fighting to stay rather than just switching. Fix the checkout, give me export, and this renewal is easy.

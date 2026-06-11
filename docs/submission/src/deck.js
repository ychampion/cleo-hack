/**
 * Cleo — hackathon submission deck (16:9, 9 slides)
 * Design law: white bg, ink #0A0A0A, accent #1F6FEB (sparing), hairlines #E5E7EB,
 * generous whitespace, system sans (Segoe UI) + Consolas mono for numerals/ids.
 * No gradients, no stock imagery, <= ~40 words per slide.
 */
const pptxgen = require("pptxgenjs");

const ROOT = "C:/Users/gamin/OneDrive/Documents/cleo-hack";
const A = {
  arch: `${ROOT}/docs/assets/architecture.png`, // 600 x 608
  archSimple: `${ROOT}/docs/assets/architecture-simple.png`, // 600 x 224 — slide-legible
  themes: `${ROOT}/docs/assets/screenshots/cleo-themes.png`, // 1280 x 720
  agent: `${ROOT}/docs/assets/screenshots/cleo-agent.png`,
  brief: `${ROOT}/docs/assets/screenshots/cleo-brief.png`,
  inbox: `${ROOT}/docs/assets/screenshots/cleo-inbox.png`,
  directives: `${ROOT}/docs/assets/screenshots/cleo-directives.png`,
};

const INK = "0A0A0A";
const MUTED = "6B7280";
const FAINT = "9CA3AF";
const HAIR = "E5E7EB";
const ACCENT = "1F6FEB";
const SANS = "Segoe UI";
const MONO = "Consolas";

const W = 10, H = 5.625, MX = 0.6;
const CW = W - 2 * MX; // 8.8 content width
const SHOT = 1280 / 720; // screenshot aspect

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "Cleo";
pres.title = "Cleo — the autonomous product-feedback operator";

function hairline(s, x, y, w) {
  s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color: HAIR, width: 0.75 } });
}
function tick(s, x, y) {
  // the one accent rule line per slide
  s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.28, h: 0.045, fill: { color: ACCENT } });
}
function imgFrame(s, x, y, w, h) {
  s.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: "FFFFFF", transparency: 100 },
    line: { color: HAIR, width: 0.75 },
  });
}
function header(s, kicker, title) {
  tick(s, MX, 0.515);
  s.addText(kicker, {
    x: MX + 0.42, y: 0.40, w: 6.5, h: 0.26, margin: 0,
    fontFace: MONO, fontSize: 8.5, color: MUTED, charSpacing: 2, align: "left", valign: "middle",
  });
  s.addText(title, {
    x: MX, y: 0.72, w: CW, h: 0.5, margin: 0,
    fontFace: SANS, fontSize: 22, bold: true, color: INK, align: "left", valign: "middle",
  });
  hairline(s, MX, 1.42, CW);
}
function footer(s, n) {
  s.addText("Cleo · Google Agent Hackathon", {
    x: MX, y: 5.30, w: 3.4, h: 0.2, margin: 0,
    fontFace: MONO, fontSize: 7.5, color: FAINT, align: "left", valign: "middle",
  });
  s.addText(`${String(n).padStart(2, "0")} / 09`, {
    x: W - MX - 1.2, y: 5.30, w: 1.2, h: 0.2, margin: 0,
    fontFace: MONO, fontSize: 7.5, color: FAINT, align: "right", valign: "middle",
  });
}
function logo(s, x, y, size = 0.4) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w: size, h: size, fill: { color: INK }, rectRadius: 0.07,
  });
  s.addText("C", {
    x, y: y - 0.01, w: size, h: size, margin: 0,
    fontFace: SANS, fontSize: 15, bold: true, color: "FFFFFF", align: "center", valign: "middle",
  });
  s.addText("Cleo", {
    x: x + size + 0.14, y, w: 1.2, h: size, margin: 0,
    fontFace: SANS, fontSize: 15, bold: true, color: INK, align: "left", valign: "middle",
  });
}

/* ---------------------------------------------------------------- slide 1 — title */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  logo(s, MX, 0.55);

  tick(s, MX, 1.98);
  s.addText(
    [
      { text: "Cleo — the autonomous", options: { breakLine: true } },
      { text: "product-feedback operator", options: {} },
    ],
    {
      x: MX, y: 2.18, w: 8.6, h: 1.3, margin: 0, lineSpacingMultiple: 1.04,
      fontFace: SANS, fontSize: 30, bold: true, color: INK, align: "left", valign: "top",
    }
  );
  s.addText("Declarative intent, not static code.", {
    x: MX, y: 3.55, w: 8.6, h: 0.35, margin: 0,
    fontFace: SANS, fontSize: 14, color: MUTED, align: "left", valign: "middle",
  });

  hairline(s, MX, 4.25, CW);
  s.addText(
    [
      { text: "Built on ", options: { color: MUTED } },
      { text: "Google ADK", options: { color: INK } },
      { text: " · every connector speaks ", options: { color: MUTED } },
      { text: "MCP", options: { color: INK } },
      { text: " · ", options: { color: MUTED } },
      { text: "gemini-3.5-flash", options: { color: INK } },
    ],
    {
      x: MX, y: 4.42, w: CW, h: 0.3, margin: 0,
      fontFace: MONO, fontSize: 11, align: "left", valign: "middle",
    }
  );
  s.addText("01 / 09", {
    x: W - MX - 1.2, y: 5.30, w: 1.2, h: 0.2, margin: 0,
    fontFace: MONO, fontSize: 7.5, color: FAINT, align: "right", valign: "middle",
  });
}

/* ---------------------------------------------------------------- slide 2 — problem */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "01 · THE PROBLEM", "Feedback is everywhere. Insight is nowhere.");

  const lines = [
    ["Scattered", "across chats, tickets, sales calls, and docs."],
    ["Hand-read", "founders and PMs read, tag, and guess."],
    ["Hidden", "urgent issues sit unseen for days."],
  ];
  lines.forEach(([lead, rest], i) => {
    const y = 1.78 + i * 0.78;
    s.addText(
      [
        { text: lead, options: { bold: true, color: INK } },
        { text: " — " + rest, options: { color: MUTED } },
      ],
      {
        x: MX, y, w: 4.15, h: 0.62, margin: 0,
        fontFace: SANS, fontSize: 12.5, align: "left", valign: "top", lineSpacingMultiple: 1.1,
      }
    );
  });

  // inbox screenshot, right
  const iw = 4.3, ih = iw / SHOT;
  s.addImage({ path: A.inbox, x: 5.1, y: 1.72, w: iw, h: ih });
  imgFrame(s, 5.1, 1.72, iw, ih);
  s.addText("The raw inbox — 5 sources, untriaged", {
    x: 5.1, y: 1.72 + ih + 0.08, w: iw, h: 0.22, margin: 0,
    fontFace: MONO, fontSize: 8.5, color: MUTED, align: "left", valign: "middle",
  });

  // stat line
  s.addText(
    [
      { text: "~90", options: { color: ACCENT, bold: true } },
      { text: " raw signals/week", options: { color: MUTED } },
      { text: "   ·   ", options: { color: FAINT } },
      { text: "5", options: { color: ACCENT, bold: true } },
      { text: " sources", options: { color: MUTED } },
      { text: "   ·   ", options: { color: FAINT } },
      { text: "0", options: { color: ACCENT, bold: true } },
      { text: " read end-to-end", options: { color: MUTED } },
    ],
    {
      x: MX, y: 4.62, w: CW, h: 0.4, margin: 0,
      fontFace: MONO, fontSize: 14, align: "left", valign: "middle",
    }
  );
  footer(s, 2);
}

/* ---------------------------------------------------------------- slide 3 — what cleo does */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "02 · WHAT CLEO DOES", "One directive in. Accountable action out.");

  const steps = [
    ["Directive", "standing intent, not a script"],
    ["Gather", "MCP connectors, in parallel"],
    ["Synthesize", "themes · urgency · contradictions"],
    ["Bet", "evidence-backed, typed output"],
    ["Act", "GitHub issues · weekly brief"],
    ["Ledger", "every action audited"],
  ];
  const cw = 1.38, gap = 0.104, y0 = 1.72;
  steps.forEach(([name, desc], i) => {
    const x = MX + i * (cw + gap);
    hairline(s, x, y0, cw);
    s.addText(String(i + 1).padStart(2, "0"), {
      x, y: y0 + 0.10, w: cw, h: 0.2, margin: 0,
      fontFace: MONO, fontSize: 8, color: FAINT, align: "left", valign: "middle",
    });
    s.addText(name, {
      x, y: y0 + 0.32, w: cw, h: 0.26, margin: 0,
      fontFace: SANS, fontSize: 11.5, bold: true, color: INK, align: "left", valign: "middle",
    });
    s.addText(desc, {
      x, y: y0 + 0.60, w: cw, h: 0.55, margin: 0, lineSpacingMultiple: 1.05,
      fontFace: SANS, fontSize: 8.5, color: MUTED, align: "left", valign: "top",
    });
  });

  // left statement
  s.addText(
    [
      { text: "Autonomy with accountability", options: { color: INK } },
      { text: ".", options: { color: ACCENT } },
    ],
    {
      x: MX, y: 3.55, w: 4.1, h: 0.45, margin: 0,
      fontFace: SANS, fontSize: 17, bold: true, align: "left", valign: "middle",
    }
  );
  s.addText("A guardrail callback gates every external write; the ledger keeps the receipts.", {
    x: MX, y: 4.05, w: 3.9, h: 0.7, margin: 0, lineSpacingMultiple: 1.15,
    fontFace: SANS, fontSize: 11, color: MUTED, align: "left", valign: "top",
  });

  // directives screenshot, right
  const dw = 3.7, dh = dw / SHOT;
  s.addImage({ path: A.directives, x: 5.7, y: 2.82, w: dw, h: dh });
  imgFrame(s, 5.7, 2.82, dw, dh);
  s.addText("Standing directives — declarative intent", {
    x: 5.7, y: 2.82 + dh + 0.07, w: dw, h: 0.2, margin: 0,
    fontFace: MONO, fontSize: 8.5, color: MUTED, align: "left", valign: "middle",
  });
  footer(s, 3);
}

/* ---------------------------------------------------------------- slide 4 — architecture */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "03 · ARCHITECTURE", "An ADK engine that touches the world only through MCP.");

  // Slide-legible simplified diagram, full-bleed-ish and centered; the detailed
  // diagram lives in the repo (docs/assets/architecture.png) for close reading.
  const aw = 7.0, ah = aw * (224 / 600), ax = (W - aw) / 2, ay = 1.58;
  s.addImage({ path: A.archSimple, x: ax, y: ay, w: aw, h: ah });
  imgFrame(s, ax, ay, aw, ah);

  const blocks = [
    ["The ADK engine orchestrates", "Sequential triage pipeline, parallel ingest, bounded watch loop, coder handoff."],
    ["MCP is the only world access", "Feedback store, GitHub, filesystem — each behind narrow tool allow-lists."],
    ["One engine, every surface", "The same runner serves the Web UI, the cleo CLI, and any MCP client."],
  ];
  const colGap = 0.45, colW = (CW - 2 * colGap) / 3, by = ay + ah + 0.28;
  blocks.forEach(([lead, body], i) => {
    const x = MX + i * (colW + colGap);
    hairline(s, x, by, colW);
    s.addText(lead, {
      x, y: by + 0.1, w: colW, h: 0.24, margin: 0,
      fontFace: SANS, fontSize: 11, bold: true, color: INK, align: "left", valign: "middle",
    });
    s.addText(body, {
      x, y: by + 0.38, w: colW, h: 0.62, margin: 0, lineSpacingMultiple: 1.1,
      fontFace: SANS, fontSize: 9.5, color: MUTED, align: "left", valign: "top",
    });
  });
  footer(s, 4);
}

/* ---------------------------------------------------------------- slide 5 — ADK table */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "04 · BUILT ON ADK", "The core concepts, not just the import.");

  const rows = [
    ["LlmAgent · gemini-3.5-flash", "every reasoning unit, operator through coder"],
    ["Sequential · Parallel · Loop", "staged pipeline · concurrent ingest · bounded autonomy"],
    ["output_schema (Pydantic)", "bets as typed JSON, not prose"],
    ["callbacks as guardrails", "action_guard gates writes; every run lands in the ledger"],
    ["sub-agent transfer", "operator hands work to a sandboxed coder agent"],
    ["McpToolset · stdio + HTTP", "the only world access — store, GitHub, filesystem"],
    ["Runner + get_fast_api_app", "one engine behind the UI, the CLI, and the API"],
  ];
  const y0 = 1.66, rh = 0.485;
  rows.forEach(([k, v], i) => {
    const y = y0 + i * rh;
    s.addText(k, {
      x: MX, y, w: 3.45, h: rh, margin: 0,
      fontFace: MONO, fontSize: 10.5, color: INK, align: "left", valign: "middle",
    });
    s.addText(v, {
      x: 4.25, y, w: 5.15, h: rh, margin: 0,
      fontFace: SANS, fontSize: 10.5, color: MUTED, align: "left", valign: "middle",
    });
    if (i < rows.length - 1) hairline(s, MX, y + rh, CW);
  });
  footer(s, 5);
}

/* ---------------------------------------------------------------- slide 6 — two closed loops */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "05 · TWO CLOSED LOOPS", "It learns, and it ships.");

  // vertical hairline divider
  s.addShape(pres.shapes.LINE, { x: 5.0, y: 1.85, w: 0, h: 2.9, line: { color: HAIR, width: 0.75 } });

  // left — skills loop
  s.addText("LOOP 01 — SKILLS", {
    x: MX, y: 1.85, w: 3.9, h: 0.24, margin: 0,
    fontFace: MONO, fontSize: 8.5, color: MUTED, charSpacing: 2, align: "left", valign: "middle",
  });
  s.addText("It writes its own runbooks.", {
    x: MX, y: 2.18, w: 3.95, h: 0.62, margin: 0, lineSpacingMultiple: 1.05,
    fontFace: SANS, fontSize: 16, bold: true, color: INK, align: "left", valign: "top",
  });
  s.addText(
    [
      { text: "Agents consult versioned skills before multi-step work — and after succeeding at uncovered work, write a new one via ", options: { color: MUTED, fontFace: SANS } },
      { text: "save_skill", options: { color: INK, fontFace: MONO } },
      { text: ". Intelligence compounds across runs.", options: { color: MUTED, fontFace: SANS } },
    ],
    {
      x: MX, y: 2.80, w: 3.9, h: 1.7, margin: 0, lineSpacingMultiple: 1.22,
      fontSize: 11.5, align: "left", valign: "top",
    }
  );

  // right — fix loop
  const rx = 5.45, rw = 3.95;
  s.addText("LOOP 02 — THE FIX", {
    x: rx, y: 1.85, w: rw, h: 0.24, margin: 0,
    fontFace: MONO, fontSize: 8.5, color: MUTED, charSpacing: 2, align: "left", valign: "middle",
  });
  s.addText("It fixes the code it hears about.", {
    x: rx, y: 2.18, w: rw, h: 0.62, margin: 0, lineSpacingMultiple: 1.05,
    fontFace: SANS, fontSize: 16, bold: true, color: INK, align: "left", valign: "top",
  });
  s.addText(
    [
      { text: "Feedback → bet → handoff → a coder subagent with its own context and sandboxed tools fixes real code, proven ", options: { color: MUTED, fontFace: SANS } },
      { text: "red → green", options: { color: ACCENT, fontFace: MONO } },
      { text: " by the target repo's test suite. Ledgered as ", options: { color: MUTED, fontFace: SANS } },
      { text: "code_fix", options: { color: INK, fontFace: MONO } },
      { text: ".", options: { color: MUTED, fontFace: SANS } },
    ],
    {
      x: rx, y: 2.80, w: rw, h: 1.9, margin: 0, lineSpacingMultiple: 1.22,
      fontSize: 11.5, align: "left", valign: "top",
    }
  );
  footer(s, 6);
}

/* ---------------------------------------------------------------- slide 7 — live output */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "06 · LIVE OUTPUT", "Real screenshots — the agent's work, not a mock.");

  const tw = 5.85, th = tw / SHOT; // 3.29
  s.addImage({ path: A.themes, x: MX, y: 1.62, w: tw, h: th });
  imgFrame(s, MX, 1.62, tw, th);
  s.addText("Agent-synthesized themes from ~90 multi-source items — urgency flagged by the agent", {
    x: MX, y: 1.62 + th + 0.09, w: tw, h: 0.4, margin: 0, lineSpacingMultiple: 1.1,
    fontFace: MONO, fontSize: 8.5, color: MUTED, align: "left", valign: "top",
  });

  const gx = MX + tw + 0.35, gw = W - MX - gx; // ~2.6
  const gh = gw / SHOT;
  s.addImage({ path: A.agent, x: gx, y: 1.62, w: gw, h: gh });
  imgFrame(s, gx, 1.62, gw, gh);
  s.addText("Live trace view — runs streamed over SSE · 5 skills available", {
    x: gx, y: 1.62 + gh + 0.09, w: gw, h: 0.42, margin: 0, lineSpacingMultiple: 1.1,
    fontFace: MONO, fontSize: 8.5, color: MUTED, align: "left", valign: "top",
  });

  // stats under right caption
  s.addText("7", {
    x: gx, y: 3.78, w: gw, h: 0.42, margin: 0,
    fontFace: MONO, fontSize: 26, bold: true, color: ACCENT, align: "left", valign: "middle",
  });
  s.addText("themes from one live run", {
    x: gx, y: 4.20, w: gw, h: 0.2, margin: 0,
    fontFace: SANS, fontSize: 9, color: MUTED, align: "left", valign: "middle",
  });
  s.addText("31", {
    x: gx, y: 4.50, w: gw, h: 0.42, margin: 0,
    fontFace: MONO, fontSize: 26, bold: true, color: ACCENT, align: "left", valign: "middle",
  });
  s.addText("signals behind the urgent checkout theme", {
    x: gx, y: 4.92, w: gw, h: 0.2, margin: 0,
    fontFace: SANS, fontSize: 9, color: MUTED, align: "left", valign: "middle",
  });
  footer(s, 7);
}

/* ---------------------------------------------------------------- slide 8 — adopt today */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  header(s, "07 · ADOPT IT TODAY", "Not wired to demo data — sources are configuration.");

  const cols = [
    ["cleo.config.json", "Point it at your repo and your docs — transcripts, support exports, notes."],
    ["cleo CLI", "init · triage · status · skills — every command takes --json for scripts and agents."],
    ["Standard MCP server", "stdio + HTTP. Operate Cleo from Claude Code, Cursor, or Gemini CLI. Ships AGENTS.md + llms.txt."],
  ];
  const colW = 2.75, colGap = 0.275, y0 = 1.78;
  cols.forEach(([k, v], i) => {
    const x = MX + i * (colW + colGap);
    hairline(s, x, y0, colW);
    s.addText(k, {
      x, y: y0 + 0.14, w: colW, h: 0.28, margin: 0,
      fontFace: MONO, fontSize: 12, bold: true, color: INK, align: "left", valign: "middle",
    });
    s.addText(v, {
      x, y: y0 + 0.50, w: colW, h: 1.6, margin: 0, lineSpacingMultiple: 1.2,
      fontFace: SANS, fontSize: 10.5, color: MUTED, align: "left", valign: "top",
    });
  });

  hairline(s, MX, 4.02, CW);
  s.addText(
    [
      { text: "151", options: { color: ACCENT, bold: true } },
      { text: " automated tests", options: { color: MUTED } },
      { text: "   ·   ", options: { color: FAINT } },
      { text: "architecture docs", options: { color: MUTED } },
      { text: "   ·   ", options: { color: FAINT } },
      { text: "15", options: { color: ACCENT, bold: true } },
      { text: "-minute setup", options: { color: MUTED } },
    ],
    {
      x: MX, y: 4.26, w: CW, h: 0.4, margin: 0,
      fontFace: MONO, fontSize: 14, align: "left", valign: "middle",
    }
  );
  footer(s, 8);
}

/* ---------------------------------------------------------------- slide 9 — close */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  logo(s, MX, 0.45);

  s.addShape(pres.shapes.RECTANGLE, { x: (W - 0.28) / 2, y: 1.02, w: 0.28, h: 0.045, fill: { color: ACCENT } });
  s.addText(
    [
      { text: "From a Tuesday-night complaint to a test-proven fix —", options: { breakLine: true } },
      { text: "one directive, full audit trail.", options: {} },
    ],
    {
      x: 0.8, y: 1.22, w: W - 1.6, h: 0.95, margin: 0, lineSpacingMultiple: 1.12,
      fontFace: SANS, fontSize: 21, bold: true, color: INK, align: "center", valign: "top",
    }
  );

  const bw = 4.7, bh = bw / SHOT; // 2.64
  const bx = (W - bw) / 2;
  s.addImage({ path: A.brief, x: bx, y: 2.30, w: bw, h: bh });
  imgFrame(s, bx, 2.30, bw, bh);
  s.addText("The weekly brief writes itself", {
    x: bx, y: 2.30 + bh + 0.07, w: bw, h: 0.2, margin: 0,
    fontFace: MONO, fontSize: 8.5, color: MUTED, align: "center", valign: "middle",
  });

  s.addText(
    [
      { text: "github.com/ychampion/cleo-hack", options: { color: INK } },
      { text: "   ·   ", options: { color: FAINT } },
      { text: "3-minute demo: docs/DEMO.md", options: { color: MUTED } },
    ],
    {
      x: 0.8, y: 5.28, w: W - 1.6, h: 0.26, margin: 0,
      fontFace: MONO, fontSize: 10.5, align: "center", valign: "middle",
    }
  );
}

pres
  .writeFile({ fileName: `${ROOT}/docs/submission/cleo-deck.pptx` })
  .then((f) => console.log("WROTE", f))
  .catch((e) => { console.error(e); process.exit(1); });

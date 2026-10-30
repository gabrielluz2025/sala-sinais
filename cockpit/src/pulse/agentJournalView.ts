function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function inlineMd(text: string): string {
  let s = esc(text);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  return s;
}

function parseTableBlock(lines: string[]): string {
  if (lines.length < 2) return lines.map((l) => `<p>${inlineMd(l)}</p>`).join("");
  const rows = lines.filter((l) => l.trim().startsWith("|"));
  if (rows.length < 2) return lines.map((l) => `<p>${inlineMd(l)}</p>`).join("");
  const splitRow = (row: string) =>
    row
      .split("|")
      .slice(1, -1)
      .map((c) => c.trim());
  const header = splitRow(rows[0]);
  const bodyRows = rows.slice(2).map(splitRow);
  const isKv = header.length === 2 && header[0].toLowerCase() === "campo";
  const tableClass = isKv ? "journal-kv-table" : "journal-data-table";
  const headHtml = isKv
    ? ""
    : `<thead><tr>${header.map((h) => `<th>${inlineMd(h)}</th>`).join("")}</tr></thead>`;
  const bodyHtml = bodyRows
    .map((cells) => {
      const cls =
        !isKv && cells[1]?.toLowerCase() === "acerto"
          ? " class=\"journal-row-win\""
          : !isKv && cells[1]?.toLowerCase() === "erro"
            ? " class=\"journal-row-loss\""
            : "";
      return `<tr${cls}>${cells.map((c) => `<td>${inlineMd(c)}</td>`).join("")}</tr>`;
    })
    .join("");
  return `<div class="journal-table-wrap"><table class="${tableClass}">${headHtml}<tbody>${bodyHtml}</tbody></table></div>`;
}

function renderBlock(body: string): string {
  const lines = body.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) {
      i += 1;
      continue;
    }
    if (trimmed.startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i]);
        i += 1;
      }
      out.push(parseTableBlock(tableLines));
      continue;
    }
    if (trimmed.startsWith(">")) {
      const quotes: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith(">")) {
        quotes.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }
      out.push(`<blockquote class="journal-quote">${quotes.map((q) => inlineMd(q)).join("<br />")}</blockquote>`);
      continue;
    }
    if (trimmed.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("- ")) {
        items.push(lines[i].trim().slice(2));
        i += 1;
      }
      out.push(`<ul class="journal-list">${items.map((it) => `<li>${inlineMd(it)}</li>`).join("")}</ul>`);
      continue;
    }
    if (trimmed.startsWith("### ")) {
      out.push(`<h4 class="journal-h4">${inlineMd(trimmed.slice(4))}</h4>`);
      i += 1;
      continue;
    }
    if (trimmed.startsWith("*") && trimmed.endsWith("*") && !trimmed.startsWith("**")) {
      out.push(`<p class="journal-footnote muted">${inlineMd(trimmed.replace(/^\*|\*$/g, ""))}</p>`);
      i += 1;
      continue;
    }
    out.push(`<p>${inlineMd(trimmed)}</p>`);
    i += 1;
  }
  return out.join("");
}

function sectionVariant(title: string): { variant: string; folded: boolean } {
  const t = title.toLowerCase();
  if (t.includes("último acerto") || t.includes("ultimo acerto")) {
    return { variant: "journal-section-win", folded: false };
  }
  if (t.includes("último erro") || t.includes("ultimo erro")) {
    return { variant: "journal-section-loss", folded: false };
  }
  if (t.includes("histórico") || t.includes("historico")) {
    return { variant: "journal-section-history", folded: false };
  }
  if (t.includes("biblioteca estudada") || t.includes("estudo autônomo") || t.includes("nível atual")) {
    return { variant: "journal-section-meta", folded: true };
  }
  return { variant: "journal-section-default", folded: true };
}

function normalizeTitle(title: string): string {
  return title.trim();
}

export function renderAgentJournalHtml(markdown: string | null | undefined): string {
  const raw = markdown?.trim();
  if (!raw) {
    return `<p class="journal-empty muted">Diário vazio — o agente escreve após fechamentos (acertos e erros).</p>`;
  }

  const parts = raw.split(/^## /m);
  const intro = parts[0]?.trim() ?? "";
  const sections = parts.slice(1).map((chunk) => {
    const nl = chunk.indexOf("\n");
    const title = nl >= 0 ? normalizeTitle(chunk.slice(0, nl)) : normalizeTitle(chunk);
    const body = nl >= 0 ? chunk.slice(nl + 1).trim() : "";
    return { title, body };
  });

  let introHtml = "";
  if (intro) {
    const introLines = intro.split("\n");
    const titleLine = introLines[0]?.startsWith("# ")
      ? `<h4 class="journal-doc-title">${inlineMd(introLines[0].slice(2))}</h4>`
      : "";
    const rest = introLines[0]?.startsWith("# ") ? introLines.slice(1).join("\n") : intro;
    introHtml = `${titleLine}${renderBlock(rest.trim())}`;
  }

  const winLoss: string[] = [];
  const main: string[] = [];
  const folded: string[] = [];

  for (const sec of sections) {
    const { variant, folded: isFolded } = sectionVariant(sec.title);
    const inner = `<div class="journal-section-body">${renderBlock(sec.body)}</div>`;
    const card = `<article class="journal-section ${variant}">
      <h4 class="journal-section-title">${esc(sec.title)}</h4>
      ${inner}
    </article>`;
    if (variant === "journal-section-win" || variant === "journal-section-loss") {
      winLoss.push(card);
    } else if (variant === "journal-section-history") {
      main.push(card);
    } else if (isFolded) {
      folded.push(
        `<details class="journal-section ${variant} journal-section-details">
          <summary class="journal-section-title">${esc(sec.title)}</summary>
          ${inner}
        </details>`,
      );
    } else {
      main.push(card);
    }
  }

  const winLossGrid =
    winLoss.length > 0 ? `<div class="journal-win-loss-grid">${winLoss.join("")}</div>` : "";

  return `<div class="agent-journal-view">
    ${introHtml ? `<div class="journal-intro">${introHtml}</div>` : ""}
    ${winLossGrid}
    ${main.join("")}
    ${folded.length ? `<div class="journal-folded">${folded.join("")}</div>` : ""}
  </div>`;
}

import { fmtAge } from "../fmt.js";

const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (url) => {
  try {
    const u = new URL(url);
    return (u.protocol === "http:" || u.protocol === "https:") ? u.href : "#";
  } catch {
    return "#";
  }
};

export function renderNews(panel) {
  const body = document.querySelector("#panel-news .panel-body");
  body.innerHTML = panel.items.map((n) =>
    `<div class="news-item">
       <a href="${safeUrl(n.url)}" target="_blank" rel="noopener noreferrer">${esc(n.headline ?? "")}</a>
       <div class="news-meta">${esc(n.feed ?? "—")} · ${fmtAge(n.published_at)}</div>
     </div>`
  ).join("");
}

function renderRows(title, rows, cls) {
  if (!rows.length) return "";
  return `<div class="insight-block">
    <div class="insight-title">${title}</div>
    ${rows.map((row) => `<div class="insight-item ${cls}">
      <div class="insight-name">${row.name}</div>
      <div class="insight-summary">${row.summary}</div>
    </div>`).join("")}
  </div>`;
}

export function renderInsights(panel) {
  const body = document.querySelector("#panel-insights .panel-body");
  const bullets = (panel.newsletter?.bullets ?? []).map((line) =>
    `<li>${line}</li>`
  ).join("");
  body.innerHTML = `
    <div class="newsletter-headline">${panel.newsletter?.headline ?? "No digest yet"}</div>
    ${renderRows("Alerts", panel.alerts ?? [], "alert")}
    ${renderRows("Trends", panel.trends ?? [], "trend")}
    <ul class="newsletter-list">${bullets}</ul>
  `;
}

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
  const delivery = panel.delivery ?? {};
  const deliveryBits = [
    delivery.enabled ? "email on" : "email off",
    delivery.state ?? "disabled",
    delivery.recipient ? delivery.recipient : null,
    delivery.last_sent_at ? `last sent ${delivery.last_sent_at}` : null,
    delivery.last_error ? `error: ${delivery.last_error}` : null,
  ].filter(Boolean).join(" · ");
  body.innerHTML = `
    <div class="newsletter-headline">${panel.newsletter?.headline ?? "No digest yet"}</div>
    <div class="news-meta">${deliveryBits}</div>
    ${renderRows("Alerts", panel.alerts ?? [], "alert")}
    ${renderRows("Trends", panel.trends ?? [], "trend")}
    ${renderRows("Predictions", panel.predictions ?? [], "prediction")}
    <ul class="newsletter-list">${bullets}</ul>
  `;
}

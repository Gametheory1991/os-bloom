const STORAGE_KEY = "osbloom:last-insight";

let registrationPromise = null;

function stateLabel(permission) {
  if (permission === "granted") return "ALERTS ON";
  if (permission === "denied") return "ALERTS BLOCKED";
  return "ENABLE ALERTS";
}

function updateButton() {
  const btn = document.getElementById("alerts-toggle");
  if (!btn) return;
  btn.textContent = stateLabel(Notification.permission);
  btn.disabled = Notification.permission === "denied";
}

export function initNotifications() {
  const btn = document.getElementById("alerts-toggle");
  if (!("Notification" in window) || !("serviceWorker" in navigator)) {
    if (btn) {
      btn.textContent = "ALERTS UNSUPPORTED";
      btn.disabled = true;
    }
    return;
  }
  registrationPromise = navigator.serviceWorker.register("/sw.js").catch(() => null);
  updateButton();
  btn?.addEventListener("click", async () => {
    if (Notification.permission !== "default") return;
    await Notification.requestPermission();
    updateButton();
  });
}

export async function notifyInsights(panel) {
  if (!panel?.generated_at || Notification.permission !== "granted" || !registrationPromise) return;
  const signature = [
    panel.digest_id ?? panel.generated_at,
    panel.alerts?.[0]?.id ?? "",
    panel.trends?.[0]?.id ?? "",
  ].join("|");
  if (localStorage.getItem(STORAGE_KEY) === signature) return;
  localStorage.setItem(STORAGE_KEY, signature);
  const lead = panel.alerts?.[0] ?? panel.trends?.[0];
  const registration = await registrationPromise;
  if (!registration) return;
  await registration.showNotification("os-bloom digest", {
    body: lead ? `${lead.name}: ${lead.summary}` : (panel.newsletter?.headline ?? "Digest updated"),
    tag: "osbloom-digest",
    data: { url: "/#/mkt" },
  });
}

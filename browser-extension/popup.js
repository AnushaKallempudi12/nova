const status = document.getElementById("status");
const autofill = document.getElementById("autofill");
const clear = document.getElementById("clear");

chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  const url = tab?.url || "";
  if (url.startsWith("https://nova-frontend-production-fe57.up.railway.app/") ||
      url.startsWith("http://localhost:5173/")) {
    status.textContent = "You're on Nova. Use the Career Profile page's Sync to extension action first.";
    autofill.disabled = true;
  } else {
    chrome.runtime.sendMessage({ type: "NOVA_GET_PROFILE" }, (response) => {
      status.textContent = response?.ok
        ? "Nova profile is saved on this device."
        : "No profile saved yet. Open Nova → Career Profile → Sync to extension.";
    });
  }
});

autofill.addEventListener("click", async () => {
  status.textContent = "Preparing this page…";
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    status.textContent = "Could not identify the active tab.";
    return;
  }
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["autofill.js"] });
    status.textContent = "Nova autofill started. Review every field on the employer page.";
  } catch {
    status.textContent = "This page does not allow extension injection. Try another employer page.";
  }
});

clear.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "NOVA_CLEAR_PROFILE" }, (response) => {
    status.textContent = response?.ok
      ? "Saved Nova profile cleared from this device."
      : "Could not clear the saved profile.";
  });
});
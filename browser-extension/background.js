chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "NOVA_SAVE_PROFILE") {
    const profile = message.profile;
    if (!profile || typeof profile !== "object" || Array.isArray(profile)) {
      sendResponse({ ok: false, error: "Invalid profile payload." });
      return false;
    }
    chrome.storage.local.set({ novaProfile: profile }).then(
      () => sendResponse({ ok: true }),
      () => sendResponse({ ok: false, error: "Could not save the profile locally." })
    );
    return true;
  }
  if (message?.type === "NOVA_GET_PROFILE") {
    chrome.storage.local.get("novaProfile").then(
      ({ novaProfile }) => sendResponse({ ok: Boolean(novaProfile), profile: novaProfile || null }),
      () => sendResponse({ ok: false, error: "Could not read the saved profile." })
    );
    return true;
  }
  if (message?.type === "NOVA_CLEAR_PROFILE") {
    chrome.storage.local.remove("novaProfile").then(
      () => sendResponse({ ok: true }),
      () => sendResponse({ ok: false, error: "Could not clear the saved profile." })
    );
    return true;
  }
  return false;
});
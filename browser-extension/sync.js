(() => {
  const trustedOrigins = new Set([
    "https://nova-frontend-production-fe57.up.railway.app",
    "http://localhost:5173"
  ]);
  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== window.location.origin) return;
    if (!trustedOrigins.has(event.origin) || event.data?.type !== "NOVA_PROFILE_SYNC") return;
    chrome.runtime.sendMessage(
      { type: "NOVA_SAVE_PROFILE", profile: event.data.profile },
      (response) => {
        window.postMessage({
          type: "NOVA_PROFILE_SYNC_RESULT",
          ok: Boolean(response?.ok),
          message: response?.ok
            ? "Profile synced to the Nova extension on this device."
            : (response?.error || "Could not sync the profile.")
        }, window.location.origin);
      }
    );
  });
})();
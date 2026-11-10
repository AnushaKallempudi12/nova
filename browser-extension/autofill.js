(() => {
  if (window.__novaAutofillRunning) return;
  window.__novaAutofillRunning = true;
  const normalize = (value) => String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  const sensitive = /work authorization|authorized to work|visa|sponsorship|sponsor|citizenship|immigration|gender|race|ethnicity|disability|veteran|salary|compensation|criminal|background check|date of birth|social security|ssn|relocation|legally eligible|demographic|pronouns/i;

  const getLabelText = (element) => {
    const parts = [
      element.getAttribute("aria-label"), element.getAttribute("placeholder"),
      element.getAttribute("name"), element.id,
      element.labels ? Array.from(element.labels).map((label) => label.innerText).join(" ") : ""
    ];
    const parent = element.closest("label");
    if (parent) parts.push(parent.innerText);
    const container = element.closest(".field, .form-group, .application-question, [class*='field'], [class*='question']");
    if (container) parts.push(container.innerText?.slice(0, 220));
    return normalize(parts.filter(Boolean).join(" "));
  };

  const resolveField = (label) => {
    if (sensitive.test(label)) return null;
    if (/first name|given name|forename/.test(label)) return "first_name";
    if (/last name|family name|surname/.test(label)) return "last_name";
    if (/full name|your name|legal name/.test(label) || /^(name|applicant name)$/.test(label)) return "full_name";
    if (/email/.test(label)) return "email";
    if (/phone|mobile|telephone/.test(label)) return "phone";
    if (/address line|street address|mailing address/.test(label)) return "address";
    if (/postal code|zip code|postcode/.test(label)) return "postal_code";
    if (/city|town/.test(label)) return "city";
    if (/state|province|region/.test(label)) return "state";
    if (/country/.test(label)) return "country";
    if (/linkedin/.test(label)) return "linkedin_url";
    if (/github/.test(label)) return "github_url";
    if (/portfolio|personal website|website url|personal url/.test(label)) return "portfolio_url";
    if (/university|college|school|institution/.test(label)) return "institution_name";
    if (/field of study|major|discipline/.test(label)) return "field_of_study";
    if (/degree/.test(label)) return "degree";
    if (/graduation year|year graduated/.test(label)) return "graduation_year";
    if (/current employer|current company|employer name|company name/.test(label)) return "employer";
    if (/current job title|current position|job title|position title/.test(label)) return "job_title";
    if (/employment start|start date.*employment|from date/.test(label)) return "employment_start";
    if (/employment end|end date.*employment|to date/.test(label)) return "employment_end";
    if (/technical skills|programming skills|skills/.test(label)) return "technical_skills";
    if (/professional summary|experience summary|about you|summary/.test(label)) return "experience_summary";
    if (/address|street/.test(label)) return "address";
    if (/location/.test(label) && /current|home|residential/.test(label)) return "location";
    return null;
  };

  const setValue = (element, value) => {
    const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype
      : element instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
    if (descriptor?.set) descriptor.set.call(element, value);
    else element.value = value;
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  };

  const chooseSelectOption = (element, value) => {
    const wanted = normalize(value);
    const option = Array.from(element.options).find((candidate) => {
      const candidateText = normalize(candidate.textContent);
      return candidate.value && (candidateText === wanted ||
        (wanted.length > 2 && candidateText.includes(wanted)) ||
        (candidateText.length > 2 && wanted.includes(candidateText)));
    });
    if (!option) return false;
    setValue(element, option.value);
    return true;
  };

  const showNotice = (message) => {
    document.getElementById("nova-autofill-notice")?.remove();
    const banner = document.createElement("div");
    banner.id = "nova-autofill-notice";
    banner.textContent = message;
    Object.assign(banner.style, {
      position: "fixed", top: "12px", right: "12px", zIndex: "2147483647",
      maxWidth: "360px", padding: "12px 16px", borderRadius: "10px",
      background: "#102b4e", color: "#fff", font: "13px/1.5 system-ui,sans-serif",
      boxShadow: "0 8px 28px rgba(0,0,0,.25)"
    });
    document.documentElement.appendChild(banner);
    window.setTimeout(() => banner.remove(), 9000);
  };

  chrome.runtime.sendMessage({ type: "NOVA_GET_PROFILE" }, (response) => {
    if (!response?.ok || !response.profile) {
      showNotice("Nova profile not found. Sync your profile from Nova first.");
      window.__novaAutofillRunning = false;
      return;
    }
    const profile = response.profile;
    let filled = 0;
    const controls = Array.from(document.querySelectorAll("input, textarea, select"));
    for (const element of controls) {
      if (element.disabled || element.readOnly || element.type === "hidden" ||
          element.type === "password" || element.type === "file" ||
          element.type === "checkbox" || element.type === "radio" ||
          element.type === "submit" || element.type === "button") continue;
      const label = getLabelText(element);
      if (sensitive.test(label)) continue;
      const key = resolveField(label);
      const value = key ? profile[key] : "";
      if (!value || !String(value).trim() || String(element.value || "").trim()) continue;
      const didFill = element instanceof HTMLSelectElement
        ? chooseSelectOption(element, String(value))
        : (setValue(element, String(value)), true);
      if (didFill) filled += 1;
    }
    showNotice("Nova filled " + filled + " supported fields. Sensitive questions and file uploads were left for you. Review every answer before submitting.");
    window.__novaAutofillRunning = false;
  });
})();
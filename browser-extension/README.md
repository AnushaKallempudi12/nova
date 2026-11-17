# Nova Application Autofill Extension

This optional Chrome/Chromium Manifest V3 extension copies the profile details you choose to sync from Nova into the extension's local storage, then fills supported fields on the employer page currently open in your browser.

## Install locally

1. Open Chrome and visit chrome://extensions.
2. Turn on Developer mode.
3. Select Load unpacked.
4. Choose this browser-extension folder.
5. Pin Nova Application Autofill to the browser toolbar.

## Use it

1. Sign in to Nova and open Career Profile.
2. Select Sync profile to browser extension. Nova sends the visible profile fields to the extension running on this device.
3. Open a verified employer application page from Nova.
4. Select the Nova extension icon and choose Autofill this page.
5. Review the employer form carefully, attach your resume manually if requested, answer sensitive questions yourself, and submit only when you are ready.

You can also sync the application-specific details from Nova's application review window before opening the employer page.

## Safety and limitations

- The extension only injects autofill code after you click its toolbar action on the current tab (activeTab permission).
- It does not store employer passwords, submit applications, or answer work authorization, visa, sponsorship, demographic, salary, disability, veteran, criminal-history, or other sensitive eligibility questions.
- File upload fields are not filled. Select your resume file manually on the employer website.
- It fills ordinary text, email, telephone, textarea and matching select controls. Custom widgets, multi-step forms, shadow DOM fields, and some dynamic forms may need manual completion.
- Existing non-empty fields are never overwritten.
- The synced profile is stored in Chrome extension local storage on this device. Use Clear saved profile from this device in the extension popup when you no longer want it stored here.
- This is a local developer extension, not yet published to the Chrome Web Store.

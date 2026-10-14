// content_script.js

function getMessageId() {

  console.log("[ContentScript] Extracting REAL Gmail message ID...");

  // Gmail stores message ID in data attributes
  const emailElement = document.querySelector('[data-legacy-message-id]');

  if (emailElement) {
    const legacyId = emailElement.getAttribute('data-legacy-message-id');
    console.log("[ContentScript] Found legacy message ID:", legacyId);

    // It looks like: "178c9f8c1a2b3d4e"
    return legacyId;
  }

  console.warn("[ContentScript] No legacy message ID found.");
  return null;
}

async function getEmailContentAnalysis() {
  const extractorModule = await import(chrome.runtime.getURL("modules/content/extractor.js"));
  const analyzerModule = await import(chrome.runtime.getURL("modules/content/analyzer.js"));

  const emailContent = extractorModule.extractEmailContent();
  const analysis = analyzerModule.analyzeEmailContent(emailContent);

  console.log("[ContentScript] Email content + analysis ready:", { emailContent, analysis });
  return { emailContent, analysis };
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log("[ContentScript] Message received:", request.type);
  if (request.type === "GET_MESSAGE_ID") {
    const id = getMessageId();
    console.log("[ContentScript] Responding with messageId:", id);
    sendResponse({ messageId: id });
    return;
  }

  if (request.type === "GET_EMAIL_CONTENT") {
    getEmailContentAnalysis()
      .then((result) => {
        sendResponse({
          ok: true,
          emailContent: result.emailContent,
          analysis: result.analysis
        });
      })
      .catch((error) => {
        console.error("[ContentScript] Failed to analyze email content:", error);
        sendResponse({ ok: false, error: error.message });
      });
    return true;
  }
});

console.log("[ContentScript] content_script.js loaded on:", window.location.href);
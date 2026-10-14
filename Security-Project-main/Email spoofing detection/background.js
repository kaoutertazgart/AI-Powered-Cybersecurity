// background.js

function sendProgress(text) {
  console.log(`[Progress] ${text}`);
  chrome.runtime.sendMessage({ type: "PROGRESS", text });
}

async function getToken() {
  console.log("[Auth] Requesting Google auth token...");
  return new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive: true }, (token) => {
      if (chrome.runtime.lastError) {
        console.error("[Auth] Failed to get token:", chrome.runtime.lastError.message);
        reject(new Error(chrome.runtime.lastError.message));
      } else {
        console.log("[Auth] Token obtained successfully:", token?.slice(0, 10) + "...");
        resolve(token);
      }
    });
  });
}

async function getGmailTab() {
  console.log("[Tab] Querying active tab...");
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || tabs.length === 0) {
        console.error("[Tab] No active tab found");
        reject(new Error("No active tab found"));
      } else {
        const tab = tabs[0];
        
        // Validate it's actually Gmail
        if (!tab.url.includes("mail.google.com")) {
          reject(new Error("Active tab is not Gmail. Please open Gmail first."));
          return;
        }
        
        console.log("[Tab] Active tab found:", {
          id: tab.id,
          url: tab.url,
          title: tab.title
        });
        resolve(tab);
      }
    });
  });
}

async function injectContentScript(tabId) {
  console.log(`[Inject] Ensuring content script is loaded in tab ${tabId}...`);
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content_script.js"]
    });
    console.log("[Inject] Content script injected successfully");
  } catch (e) {
    console.warn("[Inject] Injection note:", e.message);
  }

  // Wait a bit for the script to initialize
  await new Promise(resolve => setTimeout(resolve, 500));
}

async function getMessageId(tabId) {
  console.log(`[MessageID] Starting extraction for tab ${tabId}`);

  await injectContentScript(tabId)

  return new Promise((resolve) => {
    console.log("[MessageID] Sending GET_MESSAGE_ID to content script...");
    
    chrome.tabs.sendMessage(tabId, { type: "GET_MESSAGE_ID" }, (response) => {
      if (chrome.runtime.lastError) {
        console.error("[MessageID] Error:", chrome.runtime.lastError.message);
        resolve({ messageId: null, context: null });
      } else {
        console.log("[MessageID] Received from content script:", response);
        
        // Log context for debugging
        if (response?.context) {
          console.log(`[MessageID] Gmail context: Folder=${response.context.folder}, EmailOpen=${response.context.isEmailOpen}`);
        }
        
        resolve({
          messageId: response?.messageId || null,
          context: response?.context || null
        });
      }
    });
  });
}

async function getEmailContent(tabId) {
  console.log(`[Content] Starting extraction for tab ${tabId}`);

  await injectContentScript(tabId)

  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, { type: "GET_EMAIL_CONTENT" }, (response) => {

      if (chrome.runtime.lastError) {
        console.error("[Content] Error:", chrome.runtime.lastError.message);
        resolve({ analysis: null, error: chrome.runtime.lastError.message });
        return;
      }

      console.log("[Content] Received from content script:", response);
      resolve({
        analysis: response?.analysis || null,
        emailContent: response?.emailContent || null,
        error: response?.ok === false ? response?.error || "Unknown content analysis error" : null
      });
    });
  });
}

async function fetchRawHeaders(messageId, token) {
  console.log("[API] Fetching headers for ID:", messageId);

  const headersWeNeed = [
    "From", "Return-Path", "Reply-To",
    "Received", "Authentication-Results",
    "DKIM-Signature", "Received-SPF",
    "Date", "Message-ID", "Subject"
  ];

  const metaParams = headersWeNeed
    .map(h => `metadataHeaders=${encodeURIComponent(h)}`)
    .join("&");

  // Try as message ID first
  const messageUrl = `https://gmail.googleapis.com/gmail/v1/users/me/messages/${messageId}?format=metadata&${metaParams}`;
  console.log("[API] Attempt 1 — message endpoint:", messageUrl);

  let response = await fetch(messageUrl, {
    headers: { Authorization: `Bearer ${token}` }
  });

  console.log("[API] Attempt 1 response status:", response.status);

  if (response.ok) {
    const data = await response.json();
    console.log("[API] ✅ Successfully fetched as message");
    console.log("[API] Subject:", data.payload?.headers?.find(h => h.name === "Subject")?.value || "No subject");
    
    const headers = {};
    for (const h of data.payload.headers) {
      headers[h.name.toLowerCase()] = h.value;
    }
    return headers;
  }

  // Try as thread ID
  console.warn(`[API] Attempt 1 failed (${response.status}). Trying as thread ID...`);
  const threadUrl = `https://gmail.googleapis.com/gmail/v1/users/me/threads/${messageId}?format=metadata&${metaParams}`;

  const threadResponse = await fetch(threadUrl, {
    headers: { Authorization: `Bearer ${token}` }
  });

  console.log("[API] Attempt 2 response status:", threadResponse.status);

  if (!threadResponse.ok) {
    const errorBody = await threadResponse.text();
    console.error("[API] Both attempts failed:", errorBody);
    throw new Error(`Gmail API error: ${threadResponse.status}`);
  }

  const threadData = await threadResponse.json();
  console.log("[API] ✅ Successfully fetched as thread with", threadData.messages?.length, "messages");

  const messages = threadData.messages;
  if (!messages || messages.length === 0) {
    throw new Error("No messages found in thread");
  }

  const lastMessage = messages[messages.length - 1];
  console.log("[API] Using last message in thread, ID:", lastMessage.id);
  
  const headers = {};
  for (const h of lastMessage.payload.headers) {
    headers[h.name.toLowerCase()] = h.value;
  }
  
  // Log what we're analyzing
  console.log("[API] Analyzing email:");
  console.log("  From:", headers.from || "MISSING");
  console.log("  Subject:", headers.subject || "MISSING");
  console.log("  Has Auth-Results:", !!headers['authentication-results']);
  
  return headers;
}

async function sendToPythonAPI(headers, context, contentAnalysis = null) {
  console.log("[Python] Sending to local API at http://localhost:5000/analyze");
  
  const payload = {
    headers: headers,
    context: context  // Pass context for debugging
  };

  if (contentAnalysis) {
    payload.content_analysis = contentAnalysis;
  }
  
  console.log("[Python] Email being analyzed:", {
    from: headers.from || "unknown",
    subject: headers.subject || "unknown",
    folder: context?.folder || "unknown"
  });

  const response = await fetch("http://localhost:5000/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  console.log("[Python] Response status:", response.status);

  if (!response.ok) {
    const errorBody = await response.text();
    console.error("[Python] API error:", errorBody);
    return { error: `API error: ${response.status}`, details: errorBody };
  }

  const result = await response.json();
  console.log("[Python] Analysis complete:", result);
  return result;
}

async function analyzeCurrentEmail() {
  console.log("========== [Analysis] START ==========");

  sendProgress("Step 1/5 — Authenticating with Google...");
  const token = await getToken();

  sendProgress("Step 2/5 — Reading email from Gmail...");
  const tab = await getGmailTab();
  const { messageId, context } = await getMessageId(tab.id);

  if (!messageId) {
    throw new Error(
      `No email selected. ${context?.folder ? `You are in ${context.folder} folder. ` : ''}` +
      "Please click on an email to open/select it first."
    );
  }

  console.log(`[Analysis] Analyzing email in folder: ${context?.folder || 'unknown'}`);

  sendProgress("Step 3/5 — Fetching headers from Gmail API...");
  const headers = await fetchRawHeaders(messageId, token);

  sendProgress("Step 4/5 — Analyzing email content...");
  const contentResponse = await getEmailContent(tab.id);
  const emailContentAnalysis = contentResponse.analysis;

  if (!emailContentAnalysis) {
    console.warn("[Content Analysis] No content analysis available:", contentResponse.error);
  }

  sendProgress("Step 5/5 — Analyzing with Python API...");
  const result = await sendToPythonAPI(headers, context, emailContentAnalysis);
  if (result?.error) {
    throw new Error(result.error);
  }

  // Add context to result for debugging
  result.analyzed_context = context;
  result.message_id = messageId;
  result.content_analysis = emailContentAnalysis;
  if (contentResponse.error) {
    result.content_analysis_error = contentResponse.error;
  }

  console.log("[Analysis] Complete. Sending result to popup.");
  console.log(result);
  chrome.runtime.sendMessage({ type: "ANALYSIS_RESULT", data: result });

  console.log("========== [Analysis] END ==========");
}

chrome.runtime.onMessage.addListener((request) => {
  console.log("[Listener] Message received:", request.type);
  if (request.type === "START_ANALYSIS") {
    analyzeCurrentEmail().catch((error) => {
      console.error("[Analysis] FAILED:", error.message);
      chrome.runtime.sendMessage({ type: "ANALYSIS_ERROR", error: error.message });
    });
  }
});
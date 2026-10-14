// popup.js

const analyzeBtn = document.getElementById("analyzeBtn");
const status = document.getElementById("status");
const raw = document.getElementById("raw");

const headerDetails = document.getElementById("headerDetails");
const contentDetails = document.getElementById("contentDetails");
const headerTabButton = document.getElementById("headerTabButton")
const contentTabButton = document.getElementById("contentTabButton")

const emailClientStatus = document.getElementById("emailClientStatus");
const emailClientIcon = document.getElementById("emailClientIcon");
const emailClientText = document.getElementById("emailClientText");
const statusIcon = document.getElementById("statusIcon");

function escapeHtml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}


// Toggle between showing the header and content tabs
headerTabButton.addEventListener("click", () => {
  headerTabButton.classList.add("active");
  contentTabButton.classList.remove("active");

  document.getElementById("headerTab").classList.add("active");
  document.getElementById("contentTab").classList.remove("active");
})

contentTabButton.addEventListener("click", () => {
  contentTabButton.classList.add("active");
  headerTabButton.classList.remove("active");

  document.getElementById("contentTab").classList.add("active");
  document.getElementById("headerTab").classList.remove("active");
})



function showEmailClientStatus(isDetected, hostname = "") {
  emailClientStatus.classList.remove("detected", "not-detected");

  const supportedDomains = {"mail.google.com": "UI/clients_icons/gmail.svg"};

  if (isDetected) {
    const iconPath = supportedDomains[hostname]
    if (iconPath) {
      emailClientIcon.src = chrome.runtime.getURL(iconPath)
      emailClientIcon.style.display = "inline"
      statusIcon.innerHTML = `<i class="fa-solid fa-circle-check"></i>`
    } else {
      emailClientIcon.style.display = "none"
    }

    emailClientStatus.classList.add("detected")
    emailClientText.textContent = `Email client detected in this tab (${hostname})`
  } else {
    analyzeBtn.style.display = "none"
    emailClientIcon.style.display = "none"
    emailClientStatus.classList.add("not-detected")
    emailClientText.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> No supported email client detected in this tab.`
  }
}

// Check for the email client type from the URl on DOM load
document.addEventListener("DOMContentLoaded", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs[0];

    if (!tab || !tab.url) {
      showEmailClientStatus(false);
      return;
    }

    const hostname = new URL(tab.url).hostname;
    const supportedDomains = [
      "mail.google.com",
      "outlook.live.com",
      "outlook.office.com",
      "mail.yahoo.com",
      "mail.proton.me",
    ];

    const isSupported = supportedDomains.includes(hostname);
    showEmailClientStatus(isSupported, hostname);
  });
});

function showStatus(msg, type) {
  status.textContent = msg;
  status.className = type;
  status.style.display = "block";
}

function showRaw(data) {
  raw.textContent = JSON.stringify(data, null, 2);
  raw.style.display = "block";
}

function showHeaderDetails(data) {
  if (!headerDetails) return;
  
  const ctx = data.analyzed_context || {};
  const spf = data.spf || {};
  const dkim = data.dkim || {};
  const dmarc = data.dmarc || {};
  
  headerDetails.innerHTML = `
    <div style="margin-top: 15px; padding: 10px; border-radius: 5px;">
      <h3>
        <i class="fa-solid fa-envelope"></i>
        Analyzed Email Info
      </h3>
      <p><strong>Folder:</strong> ${ctx.folder || 'unknown'}</p>
      <p><strong>Message ID:</strong> ${data.message_id || 'unknown'}</p>
      
      <h3>
        <i class="fa-solid fa-magnifying-glass"></i>
        Email Header Analysis Breakdown
      </h3>
      <table style="width: 100%; text-align: left;">
        <tr><th>Check</th><th>Status</th><th>Score</th></tr>
        <tr><td>SPF</td><td>${spf.status || 'N/A'}</td><td>${spf.score || 0}</td></tr>
        <tr><td>DKIM</td><td>${dkim.status || 'N/A'}</td><td>${dkim.score || 0}</td></tr>
        <tr><td>DMARC</td><td>${dmarc.status || 'N/A'}</td><td>${dmarc.score || 0}</td></tr>
        <tr><td>Total</td><td></td><td><strong>${data.header_score || 0}</strong></td></tr>
      </table>
      
      ${data.all_flags && data.all_flags.length > 0 ? `
        <div style="
        background-color: rgb(255 213 124 / 0.7);
        padding: 2px;
        border-radius: 10px;
        ">
          <h3><i class="fa-solid fa-triangle-exclamation"></i>️ Warnings</h3>
          <ul>
            ${data.all_flags.map(flag => `<li>${flag}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    </div>
  `;
  headerDetails.style.display = "block";
}

function showContentDetails(data) {
  if (!contentDetails) return;

  const content = data.content_analysis;

  if (!content) {
    contentDetails.innerHTML = `
      <div style="margin-top: 15px; padding: 10px; border-radius: 5px; background: #fff3e0; color: #ef6c00;">
        <strong>No content analysis available.</strong>
        <div>${escapeHtml(data.content_analysis_error || "The body could not be extracted from this email.")}</div>
      </div>
    `;
    contentDetails.style.display = "block";
    return;
  }

  const highRiskFactors = content.highRiskFactors || [];
  const warnings = content.warnings || [];
  const links = content.links || [];

  contentDetails.innerHTML = `
    <div style="margin-top: 15px; padding: 10px; border-radius: 5px;">
      <h3>
        <i class="fa-solid fa-file-lines"></i>
        Extracted Email Content
      </h3>
      <p><strong>Subject:</strong> ${escapeHtml(content.subject || "N/A")}</p>
      <p><strong>Sender:</strong> ${escapeHtml(content.sender || "N/A")}</p>
      <p><strong>Body length:</strong> ${content.bodyLength ?? (content.body || "").length ?? 0} characters</p>
      <p><strong>Links found:</strong> ${content.linkCount ?? links.length}</p>

      <h3>
        <i class="fa-solid fa-align-left"></i>
        Body Preview
      </h3>
      <pre style="white-space: pre-wrap; background: #f5f5f5; padding: 10px; border-radius: 5px; max-height: 180px; overflow: auto;">${escapeHtml(content.bodyPreview || content.body || "No body text extracted.")}</pre>

      ${links.length > 0 ? `
        <h3><i class="fa-solid fa-link"></i> Links</h3>
        <ul>
          ${links.map(link => `<li style="color:#333"><strong>${escapeHtml(link.text || link.url)}</strong><br /><span style="word-break:break-all;">${escapeHtml(link.url)}</span></li>`).join('')}
        </ul>
      ` : ''}

      ${highRiskFactors.length > 0 ? `
        <div style="background-color: rgb(255 213 124 / 0.7); padding: 2px; border-radius: 10px;">
          <h3><i class="fa-solid fa-triangle-exclamation"></i> High-Risk Findings</h3>
          <ul>
            ${highRiskFactors.map(flag => `<li>${escapeHtml(flag.detail || flag.text || flag.type || "Risk detected")}</li>`).join('')}
          </ul>
        </div>
      ` : ''}

      ${warnings.length > 0 ? `
        <div style="background-color: #fff8e1; padding: 2px; border-radius: 10px; margin-top: 10px;">
          <h3><i class="fa-solid fa-circle-info"></i> Warnings</h3>
          <ul>
            ${warnings.map(flag => `<li style="color:#8a4f00">${escapeHtml(flag.detail || flag.text || flag.type || "Warning detected")}</li>`).join('')}
          </ul>
        </div>
      ` : ''}
    </div>
  `;

  contentDetails.style.display = "block";
}

analyzeBtn.addEventListener("click", () => {
  analyzeBtn.disabled = true;
  showStatus("Connecting to Google...", "info");
  raw.style.display = "none";
  if (headerDetails) headerDetails.style.display = "none";
  if (contentDetails) contentDetails.style.display = "none";

  chrome.runtime.sendMessage({ type: "START_ANALYSIS" });
});

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "ANALYSIS_RESULT") {
    const d = message.data;
    const verdict = d.verdict?.toUpperCase() || "UNKNOWN";
    const score = d.final_score ?? d.header_score ?? "?";
    
    showStatus(`Verdict: ${verdict} — Score: ${score}/100`, 
               verdict === "SAFE" ? "success" : "error");

    document.querySelector(".tabs").classList.add("visible");
    showHeaderDetails(d);
    showContentDetails(d);
    showRaw(d);
    analyzeBtn.disabled = false;
  }

  if (message.type === "ANALYSIS_ERROR") {
    showStatus("Error: " + message.error, "error");
    analyzeBtn.disabled = false;
  }

  if (message.type === "PROGRESS") {
    showStatus(message.text, "info");
  }
});
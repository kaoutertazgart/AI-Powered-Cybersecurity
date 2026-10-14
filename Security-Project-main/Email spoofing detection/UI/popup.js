document.addEventListener('DOMContentLoaded', () => {
    // Cache DOM elements
    const scanBtn = document.getElementById('scanBtn');
    const results = document.getElementById('results');
    const loading = document.getElementById('loading');
    const riskLevel = document.getElementById('riskLevel');
    const details = document.getElementById('details');
    const errorMessage = document.getElementById('errorMessage');
    const warningBadges = document.getElementById('warningBadges');
    const recommendationsList = document.getElementById('recommendationsList');
    const clientStatus = document.getElementById('clientStatus');
    const clientIcon = document.getElementById('clientIcon');
    const clientText = document.getElementById('clientText');
    const statusIcon = document.getElementById('statusIcon');

    const supportedDomains = {
        "mail.google.com": "clients_icons/gmail.svg",
        "outlook.live.com": "clients_icons/outlook.svg",
        "outlook.office.com": "clients_icons/outlook.svg",
        "mail.yahoo.com": "clients_icons/yahoo-mail.svg",
        "mail.proton.me": "clients_icons/proton-mail.svg",
    };

    updateClientDetectionStatus().then(r => console.log(r));

    scanBtn.addEventListener("click", async () => {
        resetUI();
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            const url = new URL(tab.url);
            setClientStatus(url.hostname in supportedDomains, url.hostname);

            if (!url.hostname in supportedDomains) {
                throw new Error("Please open an email in Gmail, Outlook, or Yahoo Mail to scan.");
            }

            const response = await sendMessageToTab(tab.id, { action: "getEmailContent" });
            displayResults(response);
        } catch (error) {
            showError(error.message || "Error analyzing email. Please try again.");
        } finally {
            loading.style.display = "none";
            scanBtn.disabled = false;
        }
    });

    async function updateClientDetectionStatus() {
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab?.url) {
                setClientStatus(false);
                return;
            }

            const url = new URL(tab.url);
            setClientStatus(url.hostname in supportedDomains, url.hostname);
        } catch (error) {
            setClientStatus(false);
        }
    }

    function setClientStatus(isDetected, hostname = "") {
        clientStatus.classList.remove("detected", "not-detected");

        if (isDetected) {
            const iconPath = supportedDomains[hostname];

            if (iconPath) {
                clientIcon.src = chrome.runtime.getURL(iconPath);
                clientIcon.style.display = "inline";
                statusIcon.innerHTML = `<i class="fa-solid fa-circle-check"></i>`
            } else {
                clientIcon.style.display = "none";
            }

            clientStatus.classList.add("detected");
            clientText.textContent = `Email client detected in this tab (${hostname}).`;

        } else {
            clientStatus.classList.add("not-detected");
            scanBtn.style.display = "none";

            clientIcon.style.display = "none";
            clientText.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> No supported email client detected in this tab.`;
        }
    }
    function resetUI() {
        loading.style.display = 'block';
        results.style.display = 'none';
        errorMessage.style.display = 'none';
        scanBtn.disabled = true;
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorMessage.style.display = 'block';
        results.style.display = 'none';
    }

    function sendMessageToTab(tabId, message) {
        return new Promise((resolve, reject) => {
            chrome.tabs.sendMessage(tabId, message, (response) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else if (!response) {
                    reject(new Error('Empty response from content script'));
                } else {
                    resolve(response);
                }
            });
        });
    }

    async function highlightIssue(text, location) {
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            await chrome.tabs.sendMessage(tab.id, {
                action: "highlightText",
                text,
                location
            });
        } catch (error) {
            console.error('Error highlighting text:', error);
        }
    }

    function createClickableListItem(issue) {
        const li = document.createElement('li');
        li.textContent = issue.detail;
        li.className = 'clickable-issue';
        if (issue.text && issue.location) {
            li.addEventListener('click', () => highlightIssue(issue.text, issue.location));
            const indicator = document.createElement('span');
            indicator.className = 'click-indicator';
            indicator.textContent = ' (click to highlight)';
            li.appendChild(indicator);
        }
        return li;
    }

    function displayResults(analysis) {
        results.style.display = 'block';

        // Hide all badges
        warningBadges.querySelectorAll('.badge').forEach(badge => {
            badge.style.display = 'none';
            badge.classList.remove('active');
        });

        // Collect active badge types
        const activeBadges = new Set([
            ...(analysis.highRiskFactors?.map(f => f.type) || []),
            ...(analysis.warnings?.map(w => w.type) || [])
        ]);

        // Show only relevant badges
        activeBadges.forEach(type => {
            const badge = warningBadges.querySelector(`[data-type="${type}"]`);
            if (badge) {
                badge.style.display = 'flex';
                badge.classList.add('active');
            }
        });

        // Determine risk level and recommendations
        let riskClass, riskText, recommendations;
        if (analysis.highRiskFactors?.length) {
            riskClass = 'high-risk';
            riskText = '🔴 High Risk - Likely Phishing Attempt';
            recommendations = [
                'Do not click any links in this email',
                'Do not download any attachments',
                'Do not reply to this email',
                'Report this email as phishing'
            ];
        } else if (analysis.warnings?.length) {
            riskClass = 'suspicious';
            riskText = '<i class="fa-solid fa-triangle-exclamation"></i> Suspicious - Exercise Caution';
            recommendations = [
                'Verify the sender through other means',
                'Do not provide sensitive information',
                'When in doubt, contact the company directly'
            ];
        } else {
            riskClass = 'low-risk';
            riskText = '<i class="fa-solid fa-circle-check"></i> Low Risk - No Obvious Red Flags';
            recommendations = [
                'Always remain vigilant with email communications',
                'Keep your security software up to date'
            ];
        }

        riskLevel.className = `risk-level ${riskClass}`;
        riskLevel.innerHTML = riskText;

        // Build details list
        if ((analysis.highRiskFactors?.length || 0) > 0 || (analysis.warnings?.length || 0) > 0) {
            const detailsList = document.createElement('ul');
            detailsList.className = 'issues-list';
            (analysis.highRiskFactors || []).forEach(factor => {
                detailsList.appendChild(createClickableListItem(factor));
            });
            (analysis.warnings || []).forEach(warning => {
                detailsList.appendChild(createClickableListItem(warning));
            });
            details.innerHTML = '<h3>Detected Issues:</h3>';
            details.appendChild(detailsList);
        } else {
            details.innerHTML = '<p>No suspicious elements detected.</p>';
        }

        // Recommendations
        recommendationsList.innerHTML = recommendations.map(rec => `<li>${rec}</li>`).join('');

        // Show/hide warning badges section
        warningBadges.style.display = activeBadges.size > 0 ? 'flex' : 'none';
    }
});

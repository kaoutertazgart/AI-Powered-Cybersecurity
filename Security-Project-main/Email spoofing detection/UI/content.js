// Function to extract email content based on the email provider
function extractEmailContent() {
    const emailContent = {
        subject: '',
        body: '',
        sender: '',
        links: [],
        bodyElement: null // Store reference to body element
    };

    // Gmail extraction
    if (window.location.hostname.includes('mail.google.com')) {
        // Subject
        const subjectElement = document.querySelector('h2.hP');
        if (subjectElement) {
            emailContent.subject = subjectElement.textContent.trim();
        }

        // Body
        const bodySelectors = ['.a3s.aiL', '.a3s.aiL .ii.gt', '.ii.gt'];
        for (const selector of bodySelectors) {
            const el = document.querySelector(selector);
            if (el) {
                emailContent.bodyElement = el;
                break;
            }
        }
        if (emailContent.bodyElement) {
            emailContent.body = emailContent.bodyElement.innerText.trim();
        }

        // Sender
        const senderSelectors = ['.gD', '.go', '[email]', '.from'];
        for (const selector of senderSelectors) {
            const el = document.querySelector(selector);
            if (el) {
                emailContent.sender = el.getAttribute('email') || el.textContent.trim();
                break;
            }
        }

        // Links
        if (emailContent.bodyElement) {
            const links = emailContent.bodyElement.querySelectorAll('a');
            links.forEach(link => {
                if (link.href && !link.href.startsWith('mailto:')) {
                    emailContent.links.push({
                        url: link.href,
                        element: link
                    });
                }
            });
        }
    }

    return emailContent;
}

// Find and highlight text in an element
function findAndHighlightText(text, element) {
    if (!element || !text) return null;
    const range = document.createRange();
    const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );
    let node;
    while ((node = walker.nextNode())) {
        const pos = node.textContent.toLowerCase().indexOf(text.toLowerCase());
        if (pos !== -1) {
            range.setStart(node, pos);
            range.setEnd(node, pos + text.length);
            return range;
        }
    }
    return null;
}

// Highlight a given range
function highlightRange(range) {
    // Remove existing highlights
    document.querySelectorAll('.phishing-highlight').forEach(el => {
        const parent = el.parentNode;
        parent.replaceChild(document.createTextNode(el.textContent), el);
        parent.normalize();
    });

    if (range) {
        const highlight = document.createElement('span');
        highlight.className = 'phishing-highlight';
        highlight.style.backgroundColor = '#ffd700';
        highlight.style.padding = '2px';
        highlight.style.borderRadius = '3px';
        range.surroundContents(highlight);
        highlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

// Analyze email for phishing risks
function analyzeEmail(emailContent) {
    const highRiskFactors = [];
    const warnings = [];

    // Subject patterns
    if (emailContent.subject) {
        const subjectLower = emailContent.subject.toLowerCase();
        const highRiskSubjectPatterns = [
            /account.*suspended/i,
            /security.*breach/i,
            /unauthorized.*access/i,
            /immediate.*action.*required/i,
            /verify.*account.*now/i
        ];
        highRiskSubjectPatterns.forEach(regex => {
            const match = subjectLower.match(regex);
            if (match) {
                highRiskFactors.push({
                    type: 'urgency',
                    detail: `Urgent action demanded in subject: "${emailContent.subject}"`,
                    text: match[0],
                    location: 'subject'
                });
            }
        });
    }

    // Suspicious sender
    if (emailContent.sender) {
        const senderLower = emailContent.sender.toLowerCase();
        const suspiciousSenderPatterns = [
            /@.*\.temp\./i,
            /@.*\.fake\./i,
            /@.*\.free\./i,
            /noreply@/i,
            /account@/i,
            /security@/i,
            /support@/i
        ];
        if (suspiciousSenderPatterns.some(regex => regex.test(senderLower))) {
            warnings.push({
                type: 'spoofing',
                detail: 'Potentially spoofed sender address'
            });
        }
    }

    // Body content
    if (emailContent.body) {
        const bodyLower = emailContent.body.toLowerCase();

        // Sensitive info requests
        const sensitiveInfoPatterns = [
            /password/i,
            /credit card/i,
            /social security/i,
            /bank account/i,
            /verify.*identity/i,
            /confirm.*account/i
        ];
        sensitiveInfoPatterns.forEach(regex => {
            const match = emailContent.body.match(regex);
            if (match) {
                highRiskFactors.push({
                    type: 'sensitive',
                    detail: `Requests for sensitive information: "${match[0]}"`,
                    text: match[0],
                    location: 'body'
                });
            }
        });

        // Pressure tactics
        const pressurePatterns = [
            /within.*24 hours/i,
            /account.*suspended/i,
            /limited time/i,
            /immediate action/i,
            /urgent/i,
            /expires soon/i
        ];
        pressurePatterns.forEach(regex => {
            const match = emailContent.body.match(regex);
            if (match) {
                warnings.push({
                    type: 'pressure',
                    detail: `Time pressure tactic: "${match[0]}"`,
                    text: match[0],
                    location: 'body'
                });
            }
        });

        // Generic greetings
        const genericGreetings = [
            'dear user',
            'dear customer',
            'dear account holder',
            'dear sir/madam'
        ];
        genericGreetings.forEach(greeting => {
            if (bodyLower.includes(greeting)) {
                warnings.push({
                    type: 'generic',
                    detail: `Generic greeting: "${greeting}"`,
                    text: greeting,
                    location: 'body'
                });
            }
        });
    }

    // Suspicious links
    if (emailContent.links.length > 0) {
        const suspiciousUrlPatterns = [
            /bit\.ly/i,
            /tinyurl/i,
            /goo\.gl/i,
            /tiny\.cc/i,
            /click\.here/i,
            /verify.*account/i,
            /login.*secure/i
        ];
        emailContent.links.forEach(link => {
            const linkLower = link.url.toLowerCase();
            if (suspiciousUrlPatterns.some(regex => regex.test(linkLower))) {
                highRiskFactors.push({
                    type: 'links',
                    detail: `Suspicious URL: ${link.url}`,
                    element: link.element,
                    location: 'link'
                });
            }
        });
    }

    // Store the body element reference for highlighting
    const bodyElement = emailContent.bodyElement;
    delete emailContent.bodyElement;

    return {
        highRiskFactors,
        warnings,
        bodyElement
    };
}

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.action === "getEmailContent") {
        try {
            const emailContent = extractEmailContent();
            const analysis = analyzeEmail(emailContent);
            sendResponse(analysis);
        } catch (error) {
            sendResponse({ error: error.message });
        }
    } else if (request.action === "highlightText") {
        try {
            const { text, location } = request;
            let range = null;
            if (location === 'subject') {
                const subjectElement = document.querySelector('h2.hP');
                range = findAndHighlightText(text, subjectElement);
            } else if (location === 'body') {
                const bodyElement = document.querySelector('.a3s.aiL');
                range = findAndHighlightText(text, bodyElement);
            }
            if (range) {
                highlightRange(range);
                sendResponse({ success: true });
            } else {
                sendResponse({ success: false, error: 'Text not found' });
            }
        } catch (error) {
            sendResponse({ success: false, error: error.message });
        }
    }
    return true;
});

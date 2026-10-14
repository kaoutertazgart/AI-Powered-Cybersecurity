export function extractEmailContent() {
    let emailContent = {
        subject: '',
        body: '',
        sender: '',
        links: []
    };

    console.log('Starting email content extraction...');
    console.log('Current hostname:', window.location.hostname);

    // Detect if the current hostname of the page is a Gmail email client
    if (window.location.hostname.includes('mail.google.com')) {
        // Get the email subject
        const subjectElement = document.querySelector('h2.hP');
        console.log('Subject element found:', subjectElement);
        if (subjectElement) {
            emailContent.subject = subjectElement.textContent.trim();
            console.log('Extracted subject:', emailContent.subject);
        }

        // Get the email body - try multiple selectors
        const bodySelectors = ['.a3s.aiL', '.a3s.aiL .ii.gt', '.ii.gt'];
        let bodyElement = null;

        for (const selector of bodySelectors) {
            bodyElement = document.querySelector(selector);
            if (bodyElement) {
                console.log('Found body element with selector:', selector);
                break;
            }
        }

        if (bodyElement) {
            emailContent.body = bodyElement.innerText.trim();
            console.log('Extracted body:', emailContent.body);
        } else {
            console.log('No body element found with any selector');
        }

        // Get sender - try multiple selectors
        const senderSelectors = ['.gD', '.go', '[email]', '.from'];
        let senderElement = null;

        for (const selector of senderSelectors) {
            senderElement = document.querySelector(selector);
            if (senderElement) {
                console.log('Found sender element with selector:', selector);
                break;
            }
        }

        if (senderElement) {
            emailContent.sender = senderElement.getAttribute('email') || senderElement.textContent.trim();
            console.log('Extracted sender:', emailContent.sender);
        }

        // Get all links
        if (bodyElement) {
            const links = bodyElement.querySelectorAll('a');
            console.log('Found links:', links.length);
            links.forEach(link => {
                if (link.href && !link.href.startsWith('mailto:')) {
                    emailContent.links.push({
                        url: link.href,
                        text: link.textContent.trim() || link.href
                    });
                    console.log('Added link:', link.href);
                }
            });
        }
    }

    return emailContent;
}

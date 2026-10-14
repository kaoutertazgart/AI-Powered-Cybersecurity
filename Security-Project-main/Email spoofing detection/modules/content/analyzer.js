// Analyze email for phishing risks
export function analyzeEmailContent(emailContent) {
    let highRiskFactors = [];
    let warnings = [];
    const bodyText = emailContent.body || '';
    const safeLinks = (emailContent.links || []).map(link => ({
        url: link.url,
        text: link.text || link.url
    }));

    // Check for high-risk factors
    if (emailContent.subject) {
        const subjectLower = emailContent.subject.toLowerCase();
        const highRiskSubjectPatterns = [
            'account.*suspended',
            'security.*breach',
            'unauthorized.*access',
            'immediate.*action.*required',
            'verify.*account.*now'
        ];

        highRiskSubjectPatterns.forEach(pattern => {
            const regex = new RegExp(pattern);
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

    // Check for suspicious sender
    if (emailContent.sender) {
        const senderLower = emailContent.sender.toLowerCase();
        const suspiciousSenderPatterns = [
            '@.*\\.temp\\.',
            '@.*\\.fake\\.',
            '@.*\\.free\\.',
            'noreply@',
            'account@',
            'security@',
            'support@'
        ];

        suspiciousSenderPatterns.forEach(pattern => {
            if (senderLower.match(new RegExp(pattern))) {
                warnings.push({
                    type: 'spoofing',
                    detail: 'Potentially spoofed sender address'
                });
            }
        });
    }

    // Check body content
    if (bodyText) {
        const bodyLower = bodyText.toLowerCase();

        // Check for sensitive information requests
        const sensitiveInfoPatterns = [
            'password',
            'credit card',
            'social security',
            'bank account',
            'verify.*identity',
            'confirm.*account'
        ];

        sensitiveInfoPatterns.forEach(pattern => {
            const regex = new RegExp(pattern, 'i');
            const match = bodyText.match(regex);
            if (match) {
                highRiskFactors.push({
                    type: 'sensitive',
                    detail: `Requests for sensitive information: "${match[0]}"`,
                    text: match[0],
                    location: 'body'
                });
            }
        });

        // Check for urgency/pressure tactics
        const pressurePatterns = [
            'within.*24 hours',
            'account.*suspended',
            'limited time',
            'immediate action',
            'urgent',
            'expires soon'
        ];

        pressurePatterns.forEach(pattern => {
            const regex = new RegExp(pattern, 'i');
            const match = bodyText.match(regex);
            if (match) {
                warnings.push({
                    type: 'pressure',
                    detail: `Time pressure tactic: "${match[0]}"`,
                    text: match[0],
                    location: 'body'
                });
            }
        });

        // Check for generic greetings
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

    // Check links
    if (safeLinks.length > 0) {
        const suspiciousUrlPatterns = [
            'bit\\.ly',
            'tinyurl',
            'goo\\.gl',
            'tiny\\.cc',
            'click\\.here',
            'verify.*account',
            'login.*secure'
        ];

        safeLinks.forEach(link => {
            const linkLower = link.url.toLowerCase();
            suspiciousUrlPatterns.forEach(pattern => {
                if (linkLower.match(new RegExp(pattern))) {
                    highRiskFactors.push({
                        type: 'links',
                        detail: `Suspicious URL: ${link.url}`,
                        text: link.text,
                        location: 'link'
                    });
                }
            });
        });
    }

    return {
        subject: emailContent.subject || '',
        sender: emailContent.sender || '',
        body: bodyText,
        bodyPreview: bodyText ? bodyText.slice(0, 1000) : '',
        bodyLength: bodyText.length,
        linkCount: safeLinks.length,
        links: safeLinks,
        highRiskFactors,
        warnings
    };
}

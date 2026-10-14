import {analyzeEmailContent} from "../modules/content/analyzer";
import {extractEmailContent} from "../modules/content/extractor";
import {findAndHighlightText, highlightRange} from "../modules/content/highlighter";

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request.action === "getEmailContent") {
        try {
            const emailContent = extractEmailContent();
            const analysis = analyzeEmailContent(emailContent);
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

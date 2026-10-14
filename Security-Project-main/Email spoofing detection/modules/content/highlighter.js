// Find and highlight text in an element
export function findAndHighlightText(text, element) {
    if (!element || !text) return null;

    const range = document.createRange();
    const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT,
        null
        //false
    );

    let node;
    while (node = walker.nextNode()) {
        const position = node.textContent.toLowerCase().indexOf(text.toLowerCase());
        if (position !== -1) {
            range.setStart(node, position);
            range.setEnd(node, position + text.length);
            return range;
        }
    }
    return null;
}

// Highlight a given range
export function highlightRange(range) {
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


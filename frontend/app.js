const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const questionInput = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const loadingIndicator = document.getElementById("loadingIndicator");

const WELCOME_HTML = `
    <div class="message-row assistant-row">
        <div class="message-bubble assistant-bubble">
            <div class="sender-label">Assistant</div>
            <div class="message-text">
                Welcome to <strong>Samsung Phone Assistant</strong>! You can ask me questions about Samsung smartphones, check specifications or prices, and compare models (for example: <em>"What is the price of Galaxy S26 FE?"</em> or <em>"Compare Galaxy F70 and Galaxy F70 Pro"</em>).
            </div>
        </div>
    </div>
`;

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function formatMarkdownText(rawText) {
    const escaped = escapeHtml(rawText || "");
    const lines = escaped.split(/\r?\n/);
    const htmlParts = [];
    let inList = false;

    for (const rawLine of lines) {
        const line = rawLine.trim();

        if (!line) {
            if (inList) {
                htmlParts.push("</ul>");
                inList = false;
            }
            continue;
        }

        const headingMatch = line.match(/^(#{1,4})\s+(.*)$/);
        if (headingMatch) {
            if (inList) {
                htmlParts.push("</ul>");
                inList = false;
            }
            const content = formatInlineMarkdown(headingMatch[2]);
            htmlParts.push(`<h4>${content}</h4>`);
            continue;
        }

        const bulletMatch = line.match(/^[-*]\s+(.*)$/) || line.match(/^\d+\.\s+(.*)$/);
        if (bulletMatch) {
            if (!inList) {
                htmlParts.push("<ul>");
                inList = true;
            }
            htmlParts.push(`<li>${formatInlineMarkdown(bulletMatch[1])}</li>`);
            continue;
        }

        if (inList) {
            htmlParts.push("</ul>");
            inList = false;
        }

        htmlParts.push(`<p class="mb-2">${formatInlineMarkdown(line)}</p>`);
    }

    if (inList) {
        htmlParts.push("</ul>");
    }

    return htmlParts.join("");
}

function formatInlineMarkdown(text) {
    return text
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendMessage(role, text, isError = false) {
    const row = document.createElement("div");
    row.className = `message-row ${role === "user" ? "user-row" : "assistant-row"}`;

    const bubble = document.createElement("div");
    if (role === "user") {
        bubble.className = "message-bubble user-bubble";
    } else if (isError) {
        bubble.className = "message-bubble error-bubble";
    } else {
        bubble.className = "message-bubble assistant-bubble";
    }

    const label = document.createElement("div");
    label.className = "sender-label";
    label.textContent = role === "user" ? "You" : "Assistant";

    const content = document.createElement("div");
    content.className = "message-text";

    if (role === "user" || isError) {
        content.textContent = text;
    } else {
        content.innerHTML = formatMarkdownText(text);
    }

    bubble.appendChild(label);
    bubble.appendChild(content);
    row.appendChild(bubble);
    chatMessages.appendChild(row);
    scrollToBottom();
}

function setLoadingState(isLoading) {
    questionInput.disabled = isLoading;
    sendBtn.disabled = isLoading;
    loadingIndicator.classList.toggle("d-none", !isLoading);
    if (isLoading) {
        scrollToBottom();
    } else {
        questionInput.focus();
    }
}

async function handleSendQuestion(event) {
    event.preventDefault();

    const question = questionInput.value.trim();
    if (!question) {
        return;
    }

    appendMessage("user", question);
    questionInput.value = "";
    setLoadingState(true);

    try {
        const response = await fetch("/review", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ question })
        });

        let data = null;
        try {
            data = await response.json();
        } catch (_) {
            data = null;
        }

        if (!response.ok) {
            const detail = data && data.detail
                ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail))
                : `Server returned status ${response.status}.`;
            appendMessage(
                "assistant",
                `Unable to process your request: ${detail}`,
                true
            );
            return;
        }

        const reviewText = data && data.review
            ? data.review
            : "No review response was returned by the server.";

        appendMessage("assistant", reviewText);
    } catch (error) {
        appendMessage(
            "assistant",
            "Could not connect to the server. Please make sure the FastAPI backend is running and try again.",
            true
        );
    } finally {
        setLoadingState(false);
    }
}

function handleClearChat() {
    chatMessages.innerHTML = WELCOME_HTML;
    questionInput.value = "";
    questionInput.focus();
}

chatForm.addEventListener("submit", handleSendQuestion);
clearBtn.addEventListener("click", handleClearChat);

questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});

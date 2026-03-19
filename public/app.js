const form = document.getElementById("mailForm");
const csvInput = document.getElementById("csvFile");
const resumeInput = document.getElementById("resumeFile");
const sendButton = document.getElementById("sendButton");
const previewButton = document.getElementById("previewButton");
const formStatus = document.getElementById("formStatus");
const terminal = document.getElementById("terminal");
const terminalState = document.getElementById("terminalState");
const testModeInput = document.getElementById("testMode");
const testLimitWrap = document.getElementById("testLimitWrap");
const previewList = document.getElementById("previewList");
const previewMeta = document.getElementById("previewMeta");
const previewAttachment = document.getElementById("previewAttachment");
const issuesBox = document.getElementById("issuesBox");

const statEls = {
    totalRows: document.getElementById("statTotalRows"),
    queuedRecipients: document.getElementById("statQueuedRecipients"),
    sent: document.getElementById("statSent"),
    failed: document.getElementById("statFailed"),
    invalidEmails: document.getElementById("statInvalidEmails"),
    duplicates: document.getElementById("statDuplicates"),
};

let currentStream = null;
let completedNormally = false;

function setTerminalState(label, stateClass) {
    terminalState.textContent = label;
    terminalState.className = `panel-badge ${stateClass}`;
}

function appendLine(text, type = "") {
    const line = document.createElement("div");
    line.className = `terminal-line ${type}`.trim();
    line.textContent = text;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function resetTerminal() {
    terminal.innerHTML = "";
}

function stopStream() {
    if (currentStream) {
        currentStream.close();
        currentStream = null;
    }
}

function setFormBusy(isBusy) {
    sendButton.disabled = isBusy;
    previewButton.disabled = isBusy;
}

function getFormData() {
    const payload = new FormData(form);
    payload.set("testMode", testModeInput.checked ? "true" : "false");
    if (!resumeInput.files[0]) {
        payload.delete("resumeFile");
    }
    return payload;
}

function updateStats(stats = {}) {
    statEls.totalRows.textContent = stats.totalRows ?? 0;
    statEls.queuedRecipients.textContent = stats.queuedRecipients ?? stats.validRecipients ?? 0;
    statEls.sent.textContent = stats.sent ?? 0;
    statEls.failed.textContent = stats.failed ?? 0;
    statEls.invalidEmails.textContent = stats.invalidEmails ?? 0;
    statEls.duplicates.textContent = stats.duplicates ?? 0;
}

function renderIssues(issues) {
    const parts = [];
    if (issues.invalidRows?.length) {
        parts.push(`Invalid rows: ${issues.invalidRows.map((item) => `#${item.row_number} ${item.email}`).join(", ")}`);
    }
    if (issues.duplicateRows?.length) {
        parts.push(`Duplicate rows: ${issues.duplicateRows.map((item) => `#${item.row_number} ${item.email}`).join(", ")}`);
    }

    if (!parts.length) {
        issuesBox.classList.add("hidden");
        issuesBox.textContent = "";
        return;
    }

    issuesBox.classList.remove("hidden");
    issuesBox.textContent = parts.join(" | ");
}

function renderPreview(preview = []) {
    previewList.innerHTML = "";
    if (!preview.length) {
        previewList.innerHTML = '<article class="preview-card muted-card">No valid recipients available for preview.</article>';
        return;
    }

    preview.forEach((item) => {
        const card = document.createElement("article");
        card.className = "preview-card";
        card.innerHTML = `
            <div class="preview-card-header">
                <strong>Row ${item.rowNumber}</strong>
                <span>${item.email}</span>
            </div>
            <div class="preview-subject">${item.subject}</div>
            <pre class="preview-body"></pre>
        `;
        card.querySelector(".preview-body").textContent = item.body;
        previewList.appendChild(card);
    });
}

function syncTestMode() {
    testLimitWrap.classList.toggle("hidden-field", !testModeInput.checked);
}

async function runPreview() {
    const file = csvInput.files[0];
    if (!file) {
        formStatus.textContent = "Choose email.csv first.";
        return;
    }

    if (file.name.toLowerCase() !== "email.csv") {
        formStatus.textContent = "Only a CSV named email.csv is accepted.";
        return;
    }

    setFormBusy(true);
    formStatus.textContent = "";
    previewMeta.textContent = "Generating preview...";

    try {
        const response = await fetch("/api/preview", {
            method: "POST",
            body: getFormData(),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || "Preview failed.");
        }

        updateStats(result.stats);
        renderPreview(result.preview);
        renderIssues(result.issues);
        previewAttachment.textContent = result.attachment || "No attachment";
        previewAttachment.className = `panel-badge ${result.attachment ? "success" : "idle"}`;
        previewMeta.textContent = `Headers: ${result.headers.join(", ")} | Previewing up to 3 emails.`;
        formStatus.textContent = "Preview ready.";
    } catch (error) {
        previewMeta.textContent = "Preview failed.";
        formStatus.textContent = error.message;
    } finally {
        setFormBusy(false);
    }
}

previewButton.addEventListener("click", runPreview);
testModeInput.addEventListener("change", syncTestMode);
syncTestMode();

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    stopStream();
    resetTerminal();
    completedNormally = false;

    const file = csvInput.files[0];
    if (!file) {
        formStatus.textContent = "Choose email.csv first.";
        return;
    }

    if (file.name.toLowerCase() !== "email.csv") {
        formStatus.textContent = "Only a CSV named email.csv is accepted.";
        return;
    }

    setFormBusy(true);
    formStatus.textContent = "";
    setTerminalState("Starting", "starting");
    appendLine("$ Starting mail sender...", "info");

    try {
        const response = await fetch("/api/send", {
            method: "POST",
            body: getFormData(),
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || "Unable to start the job.");
        }

        setTerminalState("Running", "running");
        appendLine("$ Connected to live stream.", "info");

        currentStream = new EventSource(`/api/stream/${result.jobId}`);
        currentStream.addEventListener("log", (streamEvent) => {
            const payload = JSON.parse(streamEvent.data);
            appendLine(payload.message, payload.level);
        });
        currentStream.addEventListener("summary", (streamEvent) => {
            const payload = JSON.parse(streamEvent.data);
            updateStats(payload.stats);
        });
        currentStream.addEventListener("done", () => {
            completedNormally = true;
            appendLine("$ Job finished.", "success");
            formStatus.textContent = "Mail sending completed.";
            setTerminalState("Completed", "success");
            setFormBusy(false);
            stopStream();
        });
        currentStream.onerror = () => {
            if (completedNormally) {
                return;
            }
            appendLine("$ Stream disconnected.", "error");
            formStatus.textContent = "The log stream closed unexpectedly.";
            setTerminalState("Disconnected", "error");
            setFormBusy(false);
            stopStream();
        };
    } catch (error) {
        appendLine(`$ ${error.message}`, "error");
        formStatus.textContent = error.message;
        setTerminalState("Error", "error");
        setFormBusy(false);
    }
});

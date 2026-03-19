const form = document.getElementById("mailForm");
const csvInput = document.getElementById("csvFile");
const sendButton = document.getElementById("sendButton");
const formStatus = document.getElementById("formStatus");
const terminal = document.getElementById("terminal");
const terminalState = document.getElementById("terminalState");

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

    const payload = new FormData(form);
    sendButton.disabled = true;
    formStatus.textContent = "";
    setTerminalState("Starting", "starting");
    appendLine("$ Starting mail sender...", "info");

    try {
        const response = await fetch("/api/send", {
            method: "POST",
            body: payload,
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || "Unable to start the job.");
        }

        setTerminalState("Running", "running");
        appendLine("$ Connected to live stream.", "info");

        currentStream = new EventSource(`/api/stream/${result.jobId}`);
        currentStream.onmessage = (streamEvent) => appendLine(streamEvent.data);
        currentStream.addEventListener("done", () => {
            completedNormally = true;
            appendLine("$ Job finished.", "success");
            formStatus.textContent = "Mail sending completed.";
            setTerminalState("Completed", "success");
            sendButton.disabled = false;
            stopStream();
        });
        currentStream.onerror = () => {
            if (completedNormally) {
                return;
            }
            appendLine("$ Stream disconnected.", "error");
            formStatus.textContent = "The log stream closed unexpectedly.";
            setTerminalState("Disconnected", "error");
            sendButton.disabled = false;
            stopStream();
        };
    } catch (error) {
        appendLine(`$ ${error.message}`, "error");
        formStatus.textContent = error.message;
        setTerminalState("Error", "error");
        sendButton.disabled = false;
    }
});

const API_BASE_URL = "";

let currentSessionId = null;
let isWaitingForResponse = false;

const messagesArea = document.getElementById("messagesArea");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const newSessionBtn = document.getElementById("newSessionBtn");
const typingIndicator = document.getElementById("typingIndicator");
const sessionStatus = document.getElementById("sessionStatus");

document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await initializeSession();
});

function setupEventListeners() {
  sendBtn.addEventListener("click", sendMessage);
  newSessionBtn.addEventListener("click", startNewSession);
  messageInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  messageInput.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 120) + "px";
  });
}

async function initializeSession() {
  updateSessionStatus("initializing", "#f59e0b");
  try {
    const res = await fetch(`${API_BASE_URL}/session`, { method: "POST" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    currentSessionId = data.session_id;
    messagesArea.innerHTML = "";
    addBotMessage(
      "Welcome! Describe your car problem and I'll help diagnose it.",
    );
    updateSessionStatus("active", "#10b981");
    messageInput.disabled = false;
    sendBtn.disabled = false;
    messageInput.focus();
  } catch (err) {
    console.error(err);
    addBotMessage("❌ Cannot reach server. Make sure the backend is running.");
    updateSessionStatus("offline", "#ef4444");
    messageInput.disabled = true;
    sendBtn.disabled = true;
  }
}

async function startNewSession() {
  if (isWaitingForResponse) return;
  updateSessionStatus("creating", "#f59e0b");
  try {
    const res = await fetch(`${API_BASE_URL}/session`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to create session");
    const data = await res.json();
    currentSessionId = data.session_id;
    messagesArea.innerHTML = "";
    addBotMessage("New session started. Describe your car problem.");
    updateSessionStatus("active", "#10b981");
    messageInput.disabled = false;
    sendBtn.disabled = false;
    messageInput.focus();
  } catch (err) {
    console.error(err);
    addBotMessage("❌ Error creating session. Refresh the page.");
    updateSessionStatus("offline", "#ef4444");
  }
}

async function sendMessage() {
  const message = messageInput.value.trim();
  if (!message || isWaitingForResponse || !currentSessionId) return;

  addUserMessage(message);
  messageInput.value = "";
  messageInput.style.height = "auto";

  isWaitingForResponse = true;
  sendBtn.disabled = true;
  showTypingIndicator();

  // Create the bot message bubble that we'll stream into
  const botDiv = createStreamingBubble();

  try {
    const res = await fetch(
      `${API_BASE_URL}/session/${currentSessionId}/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      },
    );

    if (res.status === 404) {
      // Session expired — recreate and retry
      await startNewSession();
      botDiv.remove();
      if (currentSessionId) await sendMessageTo(message);
      return;
    }

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    // Read the SSE stream
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullText = "";

    hideTypingIndicator();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const chunk = line.slice(6); // strip "data: "
        if (!chunk) continue;
        fullText += chunk;
        updateStreamingBubble(botDiv, fullText);
        scrollToBottom();
      }
    }

    // Handle any remaining buffer
    if (buffer.startsWith("data: ")) {
      const chunk = buffer.slice(6);
      if (chunk) {
        fullText += chunk;
        updateStreamingBubble(botDiv, fullText);
      }
    }

    updateSessionStatus("active", "#10b981");
  } catch (err) {
    console.error(err);
    updateStreamingBubble(
      botDiv,
      "❌ Error getting response. Check your connection.",
    );
    updateSessionStatus("error", "#ef4444");
  } finally {
    isWaitingForResponse = false;
    sendBtn.disabled = false;
    hideTypingIndicator();
    messageInput.focus();
    scrollToBottom();
  }
}

// Retry helper used after session recreation
async function sendMessageTo(message) {
  const botDiv = createStreamingBubble();
  try {
    const res = await fetch(
      `${API_BASE_URL}/session/${currentSessionId}/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let fullText = "";
    hideTypingIndicator();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const chunk = line.slice(6);
        if (!chunk) continue;
        fullText += chunk;
        updateStreamingBubble(botDiv, fullText);
        scrollToBottom();
      }
    }
  } catch (err) {
    updateStreamingBubble(botDiv, "❌ Error. Please try again.");
  } finally {
    isWaitingForResponse = false;
    sendBtn.disabled = false;
    hideTypingIndicator();
  }
}

// ── DOM helpers ───────────────────────────────────────────────────────────────

function createStreamingBubble() {
  const div = document.createElement("div");
  div.className = "message bot-message";
  div.innerHTML = `
    <div class="message-avatar"><i class="fas fa-robot"></i></div>
    <div class="message-bubble">
      <div class="message-content"><p class="stream-text"></p></div>
      <div class="message-time">${getTimestamp()}</div>
    </div>`;
  messagesArea.appendChild(div);
  scrollToBottom();
  return div;
}

function updateStreamingBubble(div, text) {
  const p = div.querySelector(".stream-text");
  if (p) p.innerHTML = formatBotMessage(escapeHtml(text));
}

function addUserMessage(text) {
  const div = document.createElement("div");
  div.className = "message user-message";
  div.innerHTML = `
    <div class="message-bubble">
      <div class="message-content"><p>${escapeHtml(text)}</p></div>
      <div class="message-time">${getTimestamp()}</div>
    </div>
    <div class="message-avatar"><i class="fas fa-user"></i></div>`;
  messagesArea.appendChild(div);
  scrollToBottom();
}

function addBotMessage(text) {
  const div = document.createElement("div");
  div.className = "message bot-message";
  div.innerHTML = `
    <div class="message-avatar"><i class="fas fa-robot"></i></div>
    <div class="message-bubble">
      <div class="message-content"><p>${formatBotMessage(escapeHtml(text))}</p></div>
      <div class="message-time">${getTimestamp()}</div>
    </div>`;
  messagesArea.appendChild(div);
  scrollToBottom();
}

function formatBotMessage(text) {
  return text
    .replace(/\n/g, "<br>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

function getTimestamp() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function scrollToBottom() {
  const c = document.getElementById("chatContainer");
  if (c) c.scrollTop = c.scrollHeight;
}

function showTypingIndicator() {
  if (typingIndicator) typingIndicator.style.display = "block";
  scrollToBottom();
}

function hideTypingIndicator() {
  if (typingIndicator) typingIndicator.style.display = "none";
}

function updateSessionStatus(status, color) {
  const labels = {
    active: "Session active",
    creating: "Creating session...",
    initializing: "Initializing...",
    offline: "Server offline",
    error: "Connection error",
  };
  sessionStatus.innerHTML = `<i class="fas fa-circle" style="font-size:8px;color:${color}"></i> ${labels[status] || status}`;
}

// API Configuration - Using relative URL (same origin)
const API_BASE_URL = ""; // Empty means use same server

// Global state
let currentSessionId = null;
let isWaitingForResponse = false;

// DOM Elements
const messagesArea = document.getElementById("messagesArea");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const newSessionBtn = document.getElementById("newSessionBtn");
const typingIndicator = document.getElementById("typingIndicator");
const sessionStatus = document.getElementById("sessionStatus");

// Initialize - Auto create session when page loads
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

  // Auto-resize textarea
  messageInput.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 120) + "px";
  });
}

// Initialize session on page load
async function initializeSession() {
  updateSessionStatus("initializing", "#f59e0b");
  addSystemMessage("🔄 Creating new diagnostic session...");

  try {
    const response = await fetch(`${API_BASE_URL}/session`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    currentSessionId = data.session_id;

    // Clear system message and add welcome
    messagesArea.innerHTML = "";
    addBotMessage(
      data.welcome || "Welcome! Describe your car problem to begin diagnosis.",
    );

    updateSessionStatus("active", "#10b981");
    messageInput.disabled = false;
    sendBtn.disabled = false;
    messageInput.focus();
  } catch (error) {
    console.error("Session creation error:", error);
    addBotMessage(
      "❌ Error connecting to server. Please make sure the backend is running on port 8000.",
    );
    updateSessionStatus("offline", "#ef4444");
    messageInput.disabled = true;
    sendBtn.disabled = true;
  }
}

// Start a new session
async function startNewSession() {
  if (isWaitingForResponse) return;

  updateSessionStatus("creating", "#f59e0b");
  addSystemMessage("🔄 Starting new diagnostic session...");

  try {
    const response = await fetch(`${API_BASE_URL}/session`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) throw new Error("Failed to create session");

    const data = await response.json();
    currentSessionId = data.session_id;

    // Clear chat and add welcome
    messagesArea.innerHTML = "";
    addBotMessage("🔄 New session started!\n\n" + data.welcome);

    updateSessionStatus("active", "#10b981");
    messageInput.disabled = false;
    sendBtn.disabled = false;
    messageInput.focus();
  } catch (error) {
    console.error("New session error:", error);
    addBotMessage("❌ Error creating new session. Please refresh the page.");
    updateSessionStatus("offline", "#ef4444");
  }
}

// Send message
async function sendMessage() {
  const message = messageInput.value.trim();
  if (!message || isWaitingForResponse || !currentSessionId) return;

  // Add user message to UI
  addUserMessage(message);
  messageInput.value = "";
  messageInput.style.height = "auto";

  // Send to API
  isWaitingForResponse = true;
  showTypingIndicator();

  try {
    const response = await fetch(
      `${API_BASE_URL}/session/${currentSessionId}/chat`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: message }),
      },
    );

    if (!response.ok) {
      if (response.status === 404) {
        // Session expired, create new one
        addBotMessage("⚠️ Session expired. Creating a new one...");
        await startNewSession();
        // Resend the message after new session
        if (currentSessionId) {
          const retryResponse = await fetch(
            `${API_BASE_URL}/session/${currentSessionId}/chat`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message: message }),
            },
          );
          if (retryResponse.ok) {
            const data = await retryResponse.json();
            let botMessage = data.message;
            if (data.follow_up) botMessage += "\n\n" + data.follow_up;
            addBotMessage(botMessage);
          }
        }
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    // Add bot response
    let botMessage = data.message;
    if (data.follow_up) {
      botMessage += "\n\n" + data.follow_up;
    }
    if (data.done) {
      botMessage +=
        "\n\n✅ Diagnosis complete! Click 'New Session' to start another diagnosis.";
    }

    addBotMessage(botMessage);
    updateSessionStatus("active", "#10b981");
  } catch (error) {
    console.error("Chat error:", error);
    addBotMessage("❌ Error getting diagnosis. Please check your connection.");
    updateSessionStatus("error", "#ef4444");
  } finally {
    isWaitingForResponse = false;
    hideTypingIndicator();
    messageInput.focus();
  }
}

// UI Helpers
function addUserMessage(text) {
  const messageDiv = document.createElement("div");
  messageDiv.className = "message user-message";
  messageDiv.innerHTML = `
        <div class="message-bubble">
            <div class="message-content">
                <p>${escapeHtml(text)}</p>
            </div>
            <div class="message-time">${getTimestamp()}</div>
        </div>
        <div class="message-avatar">
            <i class="fas fa-user"></i>
        </div>
    `;
  messagesArea.appendChild(messageDiv);
  scrollToBottom();
}

function addBotMessage(text) {
  const messageDiv = document.createElement("div");
  messageDiv.className = "message bot-message";
  messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-bubble">
            <div class="message-content">
                <p>${formatBotMessage(escapeHtml(text))}</p>
            </div>
            <div class="message-time">${getTimestamp()}</div>
        </div>
    `;
  messagesArea.appendChild(messageDiv);
  scrollToBottom();
}

function addSystemMessage(text) {
  const messageDiv = document.createElement("div");
  messageDiv.className = "message bot-message";
  messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-info-circle"></i>
        </div>
        <div class="message-bubble">
            <div class="message-content">
                <p><em>${escapeHtml(text)}</em></p>
            </div>
        </div>
    `;
  messagesArea.appendChild(messageDiv);
  scrollToBottom();
}

function formatBotMessage(text) {
  return text.replace(/\n/g, "<br>");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function scrollToBottom() {
  const chatContainer = document.getElementById("chatContainer");
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showTypingIndicator() {
  typingIndicator.style.display = "block";
  scrollToBottom();
}

function hideTypingIndicator() {
  typingIndicator.style.display = "none";
}

function updateSessionStatus(status, color) {
  const statusText = {
    active: "Session active",
    creating: "Creating session...",
    initializing: "Initializing...",
    offline: "Server offline",
    error: "Connection error",
  };
  sessionStatus.innerHTML = `<i class="fas fa-circle" style="font-size: 8px; color: ${color}"></i> ${statusText[status] || status}`;
}

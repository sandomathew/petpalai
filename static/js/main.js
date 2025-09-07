function appendMessage(role, text) {
    const chat = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = `chat-message ${role}`;

    if (role === 'agent') {
        msg.innerHTML = `
            <span class="agent-avatar">
                <img src="/static/images/paai_trim1.jpg" alt="PAAI avatar">
            </span>
            <span>${text}</span>
        `;
    } else {
        msg.innerHTML = `<span>${text}</span>`;
    }

    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
}

function toggleChat() {
    const chat = document.querySelector('.chat-widget');
    const chat_msg = document.getElementById('chat-messages');
    chat.style.display = (chat.style.display === 'flex') ? 'none' : 'flex';
    if(chat.style.display == 'flex' & chat_msg.childElementCount == 1){
        appendMessage('agent', "👋 Hi! I'm PAAI – your PetPalAI Agent. <br> Please note: your interactions may be reviewed for quality and improvement purposes.");
    }
}

// Show typing animation
function showTyping() {
    const chat = document.getElementById('chat-messages');
    const typingMsg = document.createElement('div');
    typingMsg.className = "chat-message agent typing";
    typingMsg.innerHTML = `
        <span class="agent-avatar">
            <img src="/static/images/paai_trim1.jpg" alt="PAAI avatar">
        </span>
        <div class="typing-animation">
            <span></span><span></span><span></span>
        </div>
    `;
    typingMsg.id = "typing-indicator";
    chat.appendChild(typingMsg);
    chat.scrollTop = chat.scrollHeight;
}

// Hide typing animation
function hideTyping() {
    const typingMsg = document.getElementById("typing-indicator");
    if (typingMsg) typingMsg.remove();
}

function sendAgentMessage() {
    const input = document.getElementById('agent-input');
    const message = input.value.trim();
    if (!message) return;

    appendMessage('user', message);
    input.value = '';

    showTyping();

    fetch('/agent/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        hideTyping();
        const reply = data.reply || "Sorry, I didn’t get that.";
        appendMessage('agent', reply);
    })
    .catch(error => {
        appendMessage('agent', "❌ Sorry, I couldn’t understand.");
    });
}

// Resume the pending intents by the agent
function resumeAgentTasks() {
    fetch('/agent/resume/', {
        method: 'GET',
        credentials: 'include',
    })
    .then(response => response.json())
    .then(data => {
        // ✅ replay old history if available
        if (data.history && data.history.length > 0) {
            data.history.forEach(turn => {
                appendMessage(turn.role, turn.message);
            });
        }
        const reply = data.reply || "No pending tasks found.";
        appendMessage('agent', reply);
    })
    .catch(error => {
        console.error("Resume error:", error);
    });
}

// CSRF helper
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Resume tasks after page loads
window.addEventListener('DOMContentLoaded', function () {
    resumeAgentTasks();
});

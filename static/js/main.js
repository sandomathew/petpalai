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
       <div class="status-and-animation">
            <div id="status-text"></div>
            <div class="typing-animation">
                <span></span><span></span><span></span>
            </div>
        </div>

    `;
    typingMsg.id = "typing-indicator";
    chat.appendChild(typingMsg);
    chat.scrollTop = chat.scrollHeight;
}

// Function to update the status text in the typing animation
function updateTypingStatus(message) {
    const statusDiv = document.getElementById('status-text');
    if (statusDiv) {
        statusDiv.textContent = message;
    }
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
    updateTypingStatus("Thinking...");

    fetch('/agent/stream/start/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        const taskId = data.task_id;
        const source = new EventSource(`/agent/stream/${taskId}/`);

        source.onmessage = function(event) {
            const streamedData = JSON.parse(event.data);
            console.log(streamedData);
            // Check if the message is a final reply
            if (streamedData.type === 'status') {
                // Handle a regular status update
                updateTypingStatus(streamedData.message);
            } else {
                hideTyping();
                appendMessage('agent', streamedData.message);
                 showTyping();
                if (streamedData.type === 'final'){hideTyping();source.close();}

            }
        };

        source.onerror = function(error) {
            hideTyping();
            appendMessage('agent', "❌ Sorry, I'm unable to fulfill the request now, please try again.");
            source.close();
        };
    })
    .catch(error => {
        hideTyping();
        appendMessage('agent', "❌ Sorry, I'm unable to fulfill the request now, please try again.");
    });
}

// Resume the pending intents by the agent
function resumeAgentTasks() {
    fetch('/agent/stream/resume/', {
        method: 'GET',
        credentials: 'include',
    })
    .then(response => response.json())
    .then(data => {
        const taskId = data.task_id;
        // Connect to the same streaming endpoint as the main chat
        const source = new EventSource(`/agent/stream/${taskId}/`);

        source.onmessage = function(event) {
            const streamedData = JSON.parse(event.data);
            console.log(streamedData);
            // Handle the preloaded history first
            if (streamedData.type === 'history_preload') {
                toggleChat(); // Open the chat if it's not already open
                streamedData.message.forEach(turn => {
                    appendMessage(turn.role, turn.message);
                });
            }
            // Handle the final message and close the stream
            else if (streamedData.type === 'final') {
                appendMessage('agent', streamedData.message);
                source.close();
            } else if (streamedData.type === 'status' || streamedData.type === 'partial') {
                // Handle all other status/partial messages
                updateTypingStatus(streamedData.message);
            }
        };

        source.onerror = function(error) {
            console.error("Stream resume error:", error);
            appendMessage('agent', "❌ Failed to resume pending tasks.");
            source.close();
        };
    })
    .catch(error => {
        console.error("Resume start error:", error);
        appendMessage('agent', "❌ Failed to start resume process.");
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
    if (window.isAuthenticated) {
        resumeAgentTasks();
    }
});

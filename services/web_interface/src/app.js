// TTRPG LLM System Web Interface
// Version: 1.0.0

// Constants
const AUTH_URL = 'http://localhost:8000';
const GAME_SESSION_URL = 'http://localhost:8001';
const RULES_ENGINE_URL = 'http://localhost:8002';
const BEING_REGISTRY_URL = 'http://localhost:8007';
const BEING_URL = 'http://localhost:8006';
const GM_URL = 'http://localhost:8005';
const WORLDS_URL = 'http://localhost:8004';
const TIME_MANAGEMENT_URL = 'http://localhost:8003';

// Utility function to escape HTML
function escapeHTML(str) {
    if (typeof str !== 'string') return str;
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Custom Modal Dialogs - Non-blocking replacements for prompt() and confirm()
function showCustomModal(options) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('custom-modal-overlay');
        const title = document.getElementById('custom-modal-title');
        const message = document.getElementById('custom-modal-message');
        const inputContainer = document.getElementById('custom-modal-input-container');
        const input = document.getElementById('custom-modal-input');
        const cancelBtn = document.getElementById('custom-modal-cancel');
        const confirmBtn = document.getElementById('custom-modal-confirm');
        
        // Set content
        title.textContent = options.title || (options.type === 'prompt' ? 'Input Required' : 'Confirm');
        message.textContent = options.message || '';
        
        // Show/hide input for prompt
        if (options.type === 'prompt') {
            inputContainer.style.display = 'block';
            input.value = options.defaultValue || '';
            input.placeholder = options.placeholder || '';
            input.focus();
            input.select();
        } else {
            inputContainer.style.display = 'none';
        }
        
        // Set button labels
        cancelBtn.textContent = options.cancelLabel || 'Cancel';
        confirmBtn.textContent = options.confirmLabel || 'OK';
        
        // Clean up previous listeners
        const newCancelBtn = cancelBtn.cloneNode(true);
        const newConfirmBtn = confirmBtn.cloneNode(true);
        cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        
        // Show modal
        overlay.style.display = 'flex';
        
        // Handle cancel
        newCancelBtn.addEventListener('click', () => {
            overlay.style.display = 'none';
            if (options.type === 'prompt') {
                resolve(null);
            } else {
                resolve(false);
            }
        });
        
        // Handle confirm
        const handleConfirm = () => {
            overlay.style.display = 'none';
            if (options.type === 'prompt') {
                resolve(input.value || null);
            } else {
                resolve(true);
            }
        };
        
        newConfirmBtn.addEventListener('click', handleConfirm);
        
        // Handle Enter key for prompt
        if (options.type === 'prompt') {
            const handleEnter = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleConfirm();
                }
            };
            input.addEventListener('keydown', handleEnter);
        }
        
        // Handle Escape key
        let escapeHandler = null;
        let resolved = false;
        const cleanup = () => {
            if (escapeHandler) {
                document.removeEventListener('keydown', escapeHandler);
                escapeHandler = null;
            }
        };
        
        escapeHandler = (e) => {
            if (e.key === 'Escape' && !resolved) {
                resolved = true;
                overlay.style.display = 'none';
                cleanup();
                resolve(options.type === 'prompt' ? null : false);
            }
        };
        document.addEventListener('keydown', escapeHandler);
        
        // Wrap resolve to clean up escape listener
        const originalResolve = resolve;
        resolve = (value) => {
            if (!resolved) {
                resolved = true;
                cleanup();
                originalResolve(value);
            }
        };
    });
}

// Non-blocking prompt replacement
async function customPrompt(message, defaultValue = '', placeholder = '') {
    return await showCustomModal({
        type: 'prompt',
        title: 'Input Required',
        message: message,
        defaultValue: defaultValue,
        placeholder: placeholder
    });
}

// Non-blocking confirm replacement
async function customConfirm(message, title = 'Confirm') {
    return await showCustomModal({
        type: 'confirm',
        title: title,
        message: message
    });
}

// Get version from build-time generated file, or fallback to default
const SYSTEM_VERSION = (typeof window !== 'undefined' && window.BUILD_VERSION) || 'dev';

let authToken = null;
let worldsWS = null;
let gmWS = null;

// Authentication - login function
async function performLogin() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        alert('Please enter both username and password');
        return;
    }
    
    try {
        const response = await fetch(`${AUTH_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            // Persist token to localStorage
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('username', username);
            
            document.getElementById('username-display').textContent = username;
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('user-info').style.display = 'block';
            document.getElementById('game-section').style.display = 'block';
            
            // Load user info to show role and enable GM features
            await loadUserInfo();
            
            // Connect WebSockets
            connectWebSockets();
            
            // Load initial game state
            await loadGameState();
        } else {
            alert('Login failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Login error: ' + error.message);
    }
}

// Login button click
document.getElementById('login-btn').addEventListener('click', performLogin);

// Enter key support for login form
document.getElementById('username').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        performLogin();
    }
});

document.getElementById('password').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        performLogin();
    }
});

document.getElementById('register-btn').addEventListener('click', async () => {
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const username = usernameInput ? usernameInput.value.trim() : '';
    const password = passwordInput ? passwordInput.value : '';
    
    if (!username || !password) {
        alert('Please enter both username and password');
        return;
    }
    
    // Generate email from username if it doesn't look like an email
    let email = username;
    if (!email.includes('@')) {
        email = `${username}@example.com`;
    }
    
    // Note: First user automatically becomes GM, others default to player
    // Role can be changed later by a GM
    
    try {
        const response = await fetch(`${AUTH_URL}/register`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ 
                username: username, 
                email: email, 
                password: password
                // Role not specified - backend will auto-assign GM to first user
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            alert('Registration successful! Please login.');
            console.log('Registered user:', data);
        } else {
            let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorText = await response.text();
                if (errorText) {
                    try {
                        const errorJson = JSON.parse(errorText);
                        // Handle FastAPI validation errors (array format)
                        if (Array.isArray(errorJson.detail)) {
                            errorDetail = errorJson.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
                        } else if (typeof errorJson.detail === 'string') {
                            errorDetail = errorJson.detail;
                        } else if (errorJson.message) {
                            errorDetail = errorJson.message;
                        } else {
                            errorDetail = JSON.stringify(errorJson);
                        }
                    } catch {
                        errorDetail = errorText || `HTTP ${response.status}`;
                    }
                }
            } catch (e) {
                errorDetail = `Failed to parse error: ${e.message}`;
            }
            alert('Registration failed: ' + errorDetail);
            console.error('Registration failed:', response.status, errorDetail);
        }
    } catch (error) {
        console.error('Registration error:', error);
        // Handle network errors and other exceptions
        let errorMessage = 'Unknown error occurred';
        if (error instanceof TypeError && error.message.includes('fetch')) {
            errorMessage = 'Network error: Could not connect to server. Make sure the auth service is running on port 8000.';
        } else if (error.message) {
            errorMessage = error.message;
        } else if (typeof error === 'string') {
            errorMessage = error;
        } else {
            // Convert error object to string safely
            try {
                errorMessage = JSON.stringify(error);
            } catch {
                errorMessage = String(error);
            }
        }
        alert('Registration error: ' + errorMessage);
    }
});

document.getElementById('logout-btn').addEventListener('click', () => {
    authToken = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    disconnectWebSockets();
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('user-info').style.display = 'none';
    document.getElementById('game-section').style.display = 'none';
});

// WebSocket connections
function connectWebSockets() {
    // Connect to Worlds service
    worldsWS = new WebSocket(`ws://localhost:8004/ws`);
    worldsWS.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'world_event') {
            addEvent(data.event);
        }
    };
    
    // Connect to Game Master service
    gmWS = new WebSocket(`ws://localhost:8005/ws`);
    gmWS.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'narrative') {
            addNarrative(data.narrative);
        }
    };
}

function disconnectWebSockets() {
    if (worldsWS) {
        worldsWS.close();
        worldsWS = null;
    }
    if (gmWS) {
        gmWS.close();
        gmWS = null;
    }
}

// UI updates
function addSystemMessage(message, type = 'info') {
    const log = document.getElementById('system-messages-log');
    if (!log) return;
    const div = document.createElement('div');
    div.className = 'system-message';
    
    // Set color based on type
    let borderColor = '#888'; // default/info
    let textColor = '#bbb';
    if (type === 'error') {
        borderColor = '#ef4444';
        textColor = '#ff9999';
    } else if (type === 'success') {
        borderColor = '#10b981';
        textColor = '#99ffcc';
    } else if (type === 'warning') {
        borderColor = '#f59e0b';
        textColor = '#ffcc99';
    }
    
    div.style.cssText = `padding: 6px 8px; margin-bottom: 6px; background: #333; border-radius: 3px; border-left: 2px solid ${borderColor}; font-size: 0.9em; color: ${textColor};`;
    div.textContent = message;
    log.appendChild(div);
    
    // Auto-scroll to bottom
    log.scrollTop = log.scrollHeight;
}

function addEvent(event) {
    const log = document.getElementById('events-log');
    if (!log) return;
    const div = document.createElement('div');
    div.className = 'event';
    div.innerHTML = `<strong>${event.event_type}</strong>: ${event.description}`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function addNarrative(narrative) {
    const log = document.getElementById('narrative-log');
    if (!log) return;
    const div = document.createElement('div');
    div.className = 'narrative';
    div.textContent = narrative.text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

// System messages panel minimize/maximize
function setupSystemMessagesToggle() {
    const toggleBtn = document.getElementById('toggle-system-messages');
    const messagesLog = document.getElementById('system-messages-log');
    const panel = messagesLog?.closest('.panel');
    
    if (!toggleBtn || !messagesLog || !panel) return;
    
    // Load saved state
    const savedState = localStorage.getItem('systemMessagesMinimized');
    const isMinimized = savedState === 'true';
    
    function setMinimized(minimized) {
        if (minimized) {
            messagesLog.style.display = 'none';
            toggleBtn.textContent = '+';
            toggleBtn.title = 'Expand System Messages';
        } else {
            messagesLog.style.display = 'block';
            toggleBtn.textContent = '−';
            toggleBtn.title = 'Minimize System Messages';
        }
        localStorage.setItem('systemMessagesMinimized', String(minimized));
    }
    
    // Apply saved state
    setMinimized(isMinimized);
    
    // Toggle on click
    toggleBtn.addEventListener('click', () => {
        const currentlyMinimized = messagesLog.style.display === 'none';
        setMinimized(!currentlyMinimized);
    });
}

// Being chat functionality (now handles both beings and LLM services)
let currentBeingChatId = null;
let currentChatType = null; // 'being' or 'llm'
let beingChatHistory = {};

// Load being chat history from localStorage
function loadBeingChatHistory(beingId) {
    const key = `being_chat_${beingId}`;
    const history = localStorage.getItem(key);
    return history ? JSON.parse(history) : [];
}

// Save being chat history to localStorage
function saveBeingChatHistory(beingId, history) {
    const key = `being_chat_${beingId}`;
    localStorage.setItem(key, JSON.stringify(history));
}

// Add message to being chat history
function addBeingChatMessage(beingId, role, content, metadata = {}) {
    const history = loadBeingChatHistory(beingId);
    const currentUser = window.currentUser;
    const senderRole = currentUser ? currentUser.role : 'player';
    
    // GM messages are hidden from players by default, unless explicitly marked visible
    const visibleToPlayers = metadata.visible_to_players !== undefined 
        ? metadata.visible_to_players 
        : (senderRole !== 'gm'); // Non-GM messages are always visible
    
    history.push({
        role: role, // 'user' or 'assistant'
        content: content,
        timestamp: new Date().toISOString(),
        sender_role: senderRole, // Track who sent the message
        visible_to_players: visibleToPlayers, // Visibility flag
        metadata: metadata
    });
    // Keep only last 100 messages per being
    if (history.length > 100) {
        history.shift();
    }
    saveBeingChatHistory(beingId, history);
    return history;
}

// Render LLM service conversation in being chat interface
function renderLLMConversationForBeingChat(service) {
    const messagesDiv = document.getElementById('being-chat-messages');
    const history = loadLLMConversationHistory(service);
    const serviceConfig = LLM_SERVICES[service];
    
    if (history.length === 0) {
        messagesDiv.innerHTML = `
            <div style="text-align: center; color: #888; padding: 40px 20px; font-style: italic;">
                No messages yet. Start the conversation!
            </div>
        `;
        return;
    }
    
    messagesDiv.innerHTML = history.map(msg => {
        const isUser = msg.role === 'user';
        const timestamp = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return `
            <div style="display: flex; gap: 12px; ${isUser ? 'flex-direction: row-reverse;' : ''}">
                <div style="flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%; background: ${isUser ? '#4a9eff' : serviceConfig.color}; display: flex; align-items: center; justify-content: center; font-size: 1.2em;">
                    ${isUser ? '👤' : serviceConfig.icon}
                </div>
                <div style="flex: 1; ${isUser ? 'text-align: right;' : ''}">
                    <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px; ${isUser ? 'justify-content: flex-end;' : ''}">
                        <span style="font-weight: bold; color: ${isUser ? '#4a9eff' : serviceConfig.color}; font-size: 0.9em;">
                            ${isUser ? 'You' : serviceConfig.name.split(' ')[0]}
                        </span>
                        <span style="font-size: 0.75em; color: #888;">${timestamp}</span>
                    </div>
                    <div style="background: ${isUser ? '#2a4a6a' : '#2a2a2a'}; padding: 10px 12px; border-radius: 8px; color: #e0e0e0; white-space: pre-wrap; word-wrap: break-word;">
                        ${escapeHTML(msg.content)}
                    </div>
                    ${!isUser && msg.metadata && msg.metadata.rules_found !== undefined ? `
                        <div style="font-size: 0.75em; color: #888; margin-top: 4px;">
                            Rules found: ${msg.metadata.rules_found}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Render being chat conversation
function renderBeingChat(beingId, beingName) {
    const messagesDiv = document.getElementById('being-chat-messages');
    const history = loadBeingChatHistory(beingId);
    const currentUser = window.currentUser;
    const isGM = currentUser && currentUser.role === 'gm';
    
    // Filter messages based on visibility
    // Non-GMs can't see GM messages unless they're marked visible_to_players
    const visibleHistory = isGM 
        ? history // GMs see all messages
        : history.filter(msg => {
            // Show message if:
            // 1. Sender is not a GM, OR
            // 2. Sender is GM but message is marked visible_to_players
            return !msg.sender_role || msg.sender_role !== 'gm' || msg.visible_to_players === true;
        });
    
    if (visibleHistory.length === 0) {
        messagesDiv.innerHTML = `
            <div style="text-align: center; color: #888; padding: 40px 20px; font-style: italic;">
                ${history.length > 0 && !isGM 
                    ? 'No visible messages. Some messages may be hidden by the GM.' 
                    : 'No messages yet. Start the conversation!'}
            </div>
        `;
        return;
    }
    
    messagesDiv.innerHTML = visibleHistory.map((msg, index) => {
        const isUser = msg.role === 'user';
        const timestamp = new Date(msg.timestamp).toLocaleTimeString();
        const isGMMessage = msg.sender_role === 'gm' && msg.role === 'user';
        const isHidden = isGMMessage && !msg.visible_to_players;
        
        return `
            <div style="display: flex; gap: 12px; ${isUser ? 'flex-direction: row-reverse;' : ''}" data-message-index="${index}" data-message-timestamp="${msg.timestamp}">
                <div style="flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%; background: ${isUser ? (isGMMessage ? '#f59e0b' : '#4a9eff') : '#8b5cf6'}; display: flex; align-items: center; justify-content: center; font-size: 1.2em;">
                    ${isUser ? (isGMMessage ? '👑' : '👤') : '🧠'}
                </div>
                <div style="flex: 1; ${isUser ? 'text-align: right;' : ''}">
                    <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px; ${isUser ? 'justify-content: flex-end;' : ''}">
                        <span style="font-weight: bold; color: ${isUser ? (isGMMessage ? '#f59e0b' : '#4a9eff') : '#8b5cf6'}; font-size: 0.9em;">
                            ${isUser ? (isGMMessage ? 'GM' : 'You') : beingName}
                        </span>
                        ${isGMMessage && !msg.visible_to_players ? '<span style="color: #888; font-size: 0.7em;">(Hidden from players)</span>' : ''}
                        <span style="font-size: 0.75em; color: #888;">${timestamp}</span>
                    </div>
                    <div style="background: ${isUser ? (isGMMessage ? '#3a2a1a' : '#2a4a6a') : '#2a1a3a'}; padding: 10px 12px; border-radius: 8px; color: #e0e0e0; white-space: pre-wrap; word-wrap: break-word; position: relative;">
                        ${escapeHTML(msg.content)}
                        ${isGM && isGMMessage ? `
                            <button onclick="toggleMessageVisibility('${beingId}', '${msg.timestamp}', ${!msg.visible_to_players})" 
                                style="position: absolute; top: 4px; right: 4px; padding: 2px 6px; background: ${msg.visible_to_players ? '#10b981' : '#666'}; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.7em; opacity: 0.7; transition: opacity 0.2s;"
                                onmouseover="this.style.opacity='1'" 
                                onmouseout="this.style.opacity='0.7'"
                                title="${msg.visible_to_players ? 'Hide from players' : 'Show to players'}">
                                ${msg.visible_to_players ? '👁️' : '👁️‍🗨️'}
                            </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Switch being chat channel (handles both beings and LLM services)
function switchBeingChat(beingId, beingName, chatType = 'being') {
    currentBeingChatId = beingId;
    currentChatType = chatType;
    
    // Update header
    const iconEl = document.getElementById('being-chat-character-icon');
    const nameEl = document.getElementById('being-chat-character-name');
    const infoEl = document.getElementById('being-chat-info');
    
    if (chatType === 'llm') {
        const serviceConfig = LLM_SERVICES[beingId];
        iconEl.textContent = serviceConfig.icon;
        nameEl.textContent = serviceConfig.name;
        infoEl.innerHTML = '<span>Chat with LLM services</span>';
    } else {
        iconEl.textContent = '🧠';
        nameEl.textContent = beingName || `Character ${beingId.substring(0, 8)}`;
        infoEl.innerHTML = '<span>Chat with your characters or other beings in the session</span>';
    }
    
    // Enable input
    const input = document.getElementById('being-chat-input');
    const sendBtn = document.getElementById('being-chat-send-btn');
    input.disabled = false;
    sendBtn.disabled = false;
    
    if (chatType === 'llm') {
        const serviceConfig = LLM_SERVICES[beingId];
        input.placeholder = `Message ${serviceConfig.name.split(' ')[0]}...`;
        // Render LLM conversation
        renderLLMConversationForBeingChat(beingId);
    } else {
        input.placeholder = `Message ${beingName || 'character'}... (Use @name to mention others)`;
        // Render being conversation
        renderBeingChat(beingId, beingName);
    }
    
    // Update active state in sidebar
    document.querySelectorAll('.being-chat-item').forEach(el => {
        if (el.dataset.beingId === beingId || (el.dataset.service === beingId && el.dataset.type === chatType)) {
            el.style.background = '#3a2a4a';
        } else {
            el.style.background = '#2a2a2a';
        }
    });
}

// Submit message (handles both beings and LLM services)
async function submitBeingMessage() {
    const input = document.getElementById('being-chat-input');
    const message = input.value.trim();
    
    if (!message || !currentBeingChatId) {
        return;
    }
    
    const token = authToken || localStorage.getItem('authToken');
    if (!token) {
        alert('Please log in first');
        return;
    }
    
    // Clear input
    input.value = '';
    
    // Handle LLM service messages
    if (currentChatType === 'llm') {
        const requestService = currentBeingChatId;
        const serviceConfig = LLM_SERVICES[requestService];
        
        // Add user message to history
        addLLMMessage(requestService, 'user', message);
        renderLLMConversationForBeingChat(requestService);
        
        // Show typing indicator
        const messagesDiv = document.getElementById('being-chat-messages');
        const typingId = `llm-typing-${requestService}-${Date.now()}`;
        const typingIndicator = document.createElement('div');
        typingIndicator.id = typingId;
        typingIndicator.innerHTML = `
            <div style="display: flex; gap: 12px;">
                <div style="flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%; background: ${serviceConfig.color}; display: flex; align-items: center; justify-content: center; font-size: 1.2em;">
                    ${serviceConfig.icon}
                </div>
                <div style="flex: 1;">
                    <div style="background: #2a2a2a; padding: 10px 12px; border-radius: 8px; color: #888;">
                        <span style="animation: pulse 1.5s ease-in-out infinite;">●</span> Thinking...
                    </div>
                </div>
            </div>
        `;
        messagesDiv.appendChild(typingIndicator);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        try {
            const currentSession = window.currentSession;
            const sessionId = currentSession ? currentSession.session_id : null;
            
            const response = await fetch(serviceConfig.url, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: message,
                    session_id: sessionId,
                    game_system: currentSession ? currentSession.game_system_type : null
                })
            });
            
            const typingEl = document.getElementById(typingId);
            if (typingEl) typingEl.remove();
            
            if (response.ok) {
                const data = await response.json();
                const responseText = data.response || 'No response received';
                
                addLLMMessage(requestService, 'assistant', responseText, data.metadata || {});
                renderLLMConversationForBeingChat(requestService);
            } else {
                const errorText = await response.text();
                throw new Error(errorText || 'Failed to send message');
            }
        } catch (error) {
            const typingEl = document.getElementById(typingId);
            if (typingEl) typingEl.remove();
            
            console.error('Error sending message to LLM service:', error);
            alert('Error: ' + error.message);
        }
        return;
    }
    
    // Handle being messages (existing code)
    // Add user message to history
    // GM messages are hidden by default, but can be made visible
    const currentUser = window.currentUser;
    const isGM = currentUser && currentUser.role === 'gm';
    addBeingChatMessage(currentBeingChatId, 'user', message, {
        visible_to_players: false // GM messages hidden by default
    });
    renderBeingChat(currentBeingChatId, document.getElementById('being-chat-character-name').textContent);
    
    // Show typing indicator
    const messagesDiv = document.getElementById('being-chat-messages');
    const typingId = `being-typing-${Date.now()}`;
    const typingIndicator = document.createElement('div');
    typingIndicator.id = typingId;
    typingIndicator.innerHTML = `
        <div style="display: flex; gap: 12px;">
            <div style="flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%; background: #8b5cf6; display: flex; align-items: center; justify-content: center; font-size: 1.2em;">🧠</div>
            <div style="flex: 1;">
                <div style="background: #2a1a3a; padding: 10px 12px; border-radius: 8px; color: #888;">
                    <span style="animation: pulse 1.5s ease-in-out infinite;">●</span> Thinking...
                </div>
            </div>
        </div>
    `;
    messagesDiv.appendChild(typingIndicator);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    
    try {
        const currentSession = window.currentSession;
        const sessionId = currentSession ? currentSession.session_id : null;
        
        // Parse @mentions to find target_being_id
        const mentionMatch = message.match(/@(\w+)/);
        let targetBeingId = null;
        
        if (mentionMatch && sessionId) {
            // Try to resolve mention to being_id
            try {
                const vicinityResponse = await fetch(`${BEING_REGISTRY_URL}/beings/vicinity/${sessionId}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (vicinityResponse.ok) {
                    const vicinityData = await vicinityResponse.json();
                    const beings = vicinityData.beings || [];
                    const mentionName = mentionMatch[1].toLowerCase();
                    for (const being of beings) {
                        const beingName = (being.name || '').toLowerCase();
                        if (mentionName === beingName || beingName.startsWith(mentionName)) {
                            targetBeingId = being.being_id;
                            break;
                        }
                    }
                }
            } catch (e) {
                console.warn('Could not resolve @mention:', e);
            }
        }
        
        // Send message to being service
        const response = await fetch(`${BEING_URL}/query`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: message,
                being_id: currentBeingChatId,
                target_being_id: targetBeingId,
                session_id: sessionId,
                game_system: currentSession ? currentSession.game_system_type : null
            })
        });
        
        // Remove typing indicator
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        
        if (response.ok) {
            let data;
            try {
                const responseText = await response.text();
                if (!responseText || responseText.trim() === '') {
                    throw new Error('Empty response from being service');
                }
                data = JSON.parse(responseText);
            } catch (parseError) {
                console.error('Error parsing being service response:', parseError);
                console.error('Response status:', response.status);
                console.error('Response headers:', [...response.headers.entries()]);
                throw new Error(`Invalid response from being service: ${parseError.message}`);
            }
            
            const responseText = data.response || 'No response received';
            
            if (responseText === 'No response received' || !responseText || responseText.trim() === '') {
                console.error('Being service returned empty response:', data);
                addSystemMessage(`Warning: Character "${currentBeingChatId}" returned no response. Check being service logs.`, 'warning');
            }
            
            // Add response to history
            addBeingChatMessage(currentBeingChatId, 'assistant', responseText, {
                target_being_id: targetBeingId,
                mentions: data.mentions || []
            });
            
            // Re-render conversation
            renderBeingChat(currentBeingChatId, document.getElementById('being-chat-character-name').textContent);
        } else {
            const errorText = await response.text();
            let errorMessage = errorText || 'Failed to send message';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                // Not JSON, use as-is
            }
            throw new Error(errorMessage);
        }
    } catch (error) {
        // Remove typing indicator
        const typingEl = document.getElementById(typingId);
        if (typingEl) typingEl.remove();
        
        console.error('Error sending message to being:', error);
        alert('Error: ' + error.message);
    }
}

// Load user's characters for being chat
async function loadBeingChatCharacters() {
    const token = authToken || localStorage.getItem('authToken');
    if (!token) return;
    
    try {
        const response = await fetch(`${BEING_REGISTRY_URL}/beings/my-characters`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            const characters = data.characters || [];
            const characterList = document.getElementById('being-character-list');
            
            characterList.innerHTML = characters.map(char => `
                <div class="being-chat-item" data-being-id="${char.being_id}" style="padding: 8px 10px; border-radius: 4px; cursor: pointer; background: #2a2a2a; color: #e0e0e0; font-size: 0.9em; display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.1em;">🧠</span>
                    <span>${char.name || char.being_id.substring(0, 8)}</span>
                </div>
            `).join('');
            
            // Add click handlers for characters
            document.querySelectorAll('.being-chat-item:not(.llm-service-item)').forEach(item => {
                if (!item.dataset.type) { // Only handle non-LLM items
                    item.addEventListener('click', () => {
                        const beingId = item.dataset.beingId;
                        const beingName = item.textContent.trim().replace('🧠', '').trim();
                        switchBeingChat(beingId, beingName, 'being');
                    });
                }
            });
        }
    } catch (error) {
        console.error('Error loading characters:', error);
    }
}

// Load all beings for GM (with intelligent sorting)
let allBeingsCache = [];
async function loadAllBeings() {
    const token = authToken || localStorage.getItem('authToken');
    const currentUser = window.currentUser;
    
    // Only show for GMs
    if (!token || !currentUser || currentUser.role !== 'gm') {
        const allBeingsSection = document.getElementById('all-beings-section');
        if (allBeingsSection) {
            allBeingsSection.style.display = 'none';
        }
        return;
    }
    
    try {
        // Use auth service endpoint which has better ownership info
        const response = await fetch(`${AUTH_URL}/beings/list`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            const beings = data.characters || [];
            allBeingsCache = beings;
            
            // Sort intelligently
            const currentSession = window.currentSession;
            const sortedBeings = sortBeingsIntelligently(beings, currentSession);
            
            renderAllBeings(sortedBeings);
            
            // Show section
            const allBeingsSection = document.getElementById('all-beings-section');
            if (allBeingsSection) {
                allBeingsSection.style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Error loading all beings:', error);
    }
}

// Intelligent sorting for beings
function sortBeingsIntelligently(beings, currentSession) {
    const currentSessionId = currentSession ? currentSession.session_id : null;
    
    return [...beings].sort((a, b) => {
        // 1. Current session beings first
        const aInCurrentSession = a.session_id === currentSessionId;
        const bInCurrentSession = b.session_id === currentSessionId;
        if (aInCurrentSession && !bInCurrentSession) return -1;
        if (!aInCurrentSession && bInCurrentSession) return 1;
        
        // 2. Then by session (group by session)
        if (a.session_id && !b.session_id) return -1;
        if (!a.session_id && b.session_id) return 1;
        if (a.session_id && b.session_id && a.session_id !== b.session_id) {
            return a.session_id.localeCompare(b.session_id);
        }
        
        // 3. Then by name (alphabetical)
        const aName = (a.name || a.being_id || '').toLowerCase();
        const bName = (b.name || b.being_id || '').toLowerCase();
        return aName.localeCompare(bName);
    });
}

// Render all beings list
function renderAllBeings(beings, searchFilter = '') {
    const allBeingsList = document.getElementById('all-beings-list');
    if (!allBeingsList) return;
    
    // Filter by search if provided
    let filteredBeings = beings;
    if (searchFilter) {
        const searchLower = searchFilter.toLowerCase();
        filteredBeings = beings.filter(being => {
            const name = (being.name || being.being_id || '').toLowerCase();
            const owner = (being.owner_username || '').toLowerCase();
            const sessionId = (being.session_id || '').toLowerCase();
            return name.includes(searchLower) || owner.includes(searchLower) || sessionId.includes(searchLower);
        });
    }
    
    if (filteredBeings.length === 0) {
        allBeingsList.innerHTML = '<div style="color: #888; font-size: 0.85em; padding: 8px;">No beings found</div>';
        return;
    }
    
    const currentSession = window.currentSession;
    const currentSessionId = currentSession ? currentSession.session_id : null;
    
    // Group by session for better organization
    const grouped = {};
    filteredBeings.forEach(being => {
        const sessionKey = being.session_id || 'no-session';
        if (!grouped[sessionKey]) {
            grouped[sessionKey] = [];
        }
        grouped[sessionKey].push(being);
    });
    
    let html = '';
    const sessionKeys = Object.keys(grouped).sort((a, b) => {
        // Current session first
        if (a === currentSessionId) return -1;
        if (b === currentSessionId) return 1;
        return a.localeCompare(b);
    });
    
    sessionKeys.forEach(sessionKey => {
        const sessionBeings = grouped[sessionKey];
        const isCurrentSession = sessionKey === currentSessionId;
        const sessionLabel = isCurrentSession ? 'Current Session' : (sessionKey === 'no-session' ? 'No Session' : `Session ${sessionKey.substring(0, 8)}`);
        
        html += `<div style="font-size: 0.7em; color: #666; padding: 4px 8px; margin-top: 8px; ${sessionKeys.indexOf(sessionKey) > 0 ? 'border-top: 1px solid #333; padding-top: 8px;' : ''}">${sessionLabel}</div>`;
        
        sessionBeings.forEach(being => {
            const beingName = being.name || being.being_id.substring(0, 8);
            const ownerInfo = being.owner_username ? ` (${being.owner_username})` : '';
            html += `
                <div class="being-chat-item all-being-item" data-being-id="${being.being_id}" data-type="being" style="padding: 6px 8px; border-radius: 4px; cursor: pointer; background: #2a2a2a; color: #e0e0e0; font-size: 0.85em; display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 0.9em;">🧠</span>
                    <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHTML(beingName)}${ownerInfo}</span>
                </div>
            `;
        });
    });
    
    allBeingsList.innerHTML = html;
    
    // Add click handlers
    document.querySelectorAll('.all-being-item').forEach(item => {
        item.addEventListener('click', () => {
            const beingId = item.dataset.beingId;
            const beingName = item.textContent.trim().replace('🧠', '').trim().split(' (')[0];
            switchBeingChat(beingId, beingName, 'being');
            // Update active state
            document.querySelectorAll('.being-chat-item').forEach(el => el.style.background = '#2a2a2a');
            item.style.background = '#3a2a4a';
        });
    });
}

// Setup search for all beings
function setupAllBeingsSearch() {
    const searchInput = document.getElementById('all-beings-search');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', (e) => {
        const searchFilter = e.target.value.trim();
        const sortedBeings = sortBeingsIntelligently(allBeingsCache, window.currentSession);
        renderAllBeings(sortedBeings, searchFilter);
    });
}

// Load nearby beings for being chat
async function loadNearbyBeings() {
    const token = authToken || localStorage.getItem('authToken');
    const currentSession = window.currentSession;
    
    if (!token || !currentSession) {
        document.getElementById('being-vicinity-list').innerHTML = '<div style="color: #888; font-size: 0.85em; padding: 8px;">Join a session to see nearby beings</div>';
        return;
    }
    
    try {
        const response = await fetch(`${BEING_REGISTRY_URL}/beings/vicinity/${currentSession.session_id}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            const beings = data.beings || [];
            const vicinityList = document.getElementById('being-vicinity-list');
            
            if (beings.length === 0) {
                vicinityList.innerHTML = '<div style="color: #888; font-size: 0.85em; padding: 8px;">No other beings nearby</div>';
                return;
            }
            
            vicinityList.innerHTML = beings.map(being => `
                <div class="being-vicinity-item" data-being-id="${being.being_id}" style="padding: 6px 8px; border-radius: 4px; cursor: pointer; background: #2a2a2a; color: #e0e0e0; font-size: 0.85em; display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 0.9em;">👤</span>
                    <span>${being.name || being.being_id.substring(0, 8)}</span>
                </div>
            `).join('');
            
            // Add click handlers for nearby beings
            document.querySelectorAll('.being-vicinity-item').forEach(item => {
                item.addEventListener('click', () => {
                    const beingId = item.dataset.beingId;
                    const beingName = item.textContent.trim().replace('👤', '').trim();
                    switchBeingChat(beingId, beingName);
                    // Update active state
                    document.querySelectorAll('.being-vicinity-item').forEach(el => el.style.background = '#2a2a2a');
                    item.style.background = '#3a2a4a';
                });
            });
        }
    } catch (error) {
        console.error('Error loading nearby beings:', error);
        document.getElementById('being-vicinity-list').innerHTML = '<div style="color: #888; font-size: 0.85em; padding: 8px;">Error loading nearby beings</div>';
    }
}

// Game session management - defer prompt and all async work to prevent blocking
document.getElementById('create-session-btn').addEventListener('click', () => {
    // Return immediately from click handler, defer everything
    setTimeout(async () => {
        const sessionName = await customPrompt('Enter a name for your game session:', '', 'Session name');
        if (!sessionName) return;
        
        // Defer all async work using another setTimeout
        setTimeout(async () => {
        try {
            const token = authToken || localStorage.getItem('authToken');
            // Get current user to determine if they're GM
            const userResponse = await fetch(`${AUTH_URL}/me`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (!userResponse.ok) {
                alert('Could not get user info. Please log in again.');
                return;
            }
            
            const user = await userResponse.json();
            const isGM = user.role === 'gm';
            
            if (!isGM) {
                const fixFirst = await customConfirm('Only Game Masters can create sessions. Your role is: ' + user.role + '\n\nWould you like to check if you should be the first GM?', 'Game Master Required');
                if (fixFirst) {
                    try {
                        const fixResponse = await fetch(`${AUTH_URL}/users/fix-first-user`, {
                            method: 'POST',
                            headers: { 
                                'Authorization': `Bearer ${token}`,
                                'Content-Type': 'application/json'
                            }
                        });
                        
                        if (fixResponse.ok) {
                            const result = await fixResponse.json();
                            alert(result.message + '\n\nPlease refresh the page and try again.');
                            window.location.reload();
                            return;
                        } else {
                            let errorMsg = 'Could not auto-upgrade';
                            try {
                                const errorText = await fixResponse.text();
                                const errorJson = JSON.parse(errorText);
                                errorMsg = errorJson.detail || errorJson.message || errorText;
                            } catch {
                                errorMsg = await fixResponse.text() || 'Unknown error';
                            }
                            alert('Could not auto-upgrade: ' + errorMsg + '\n\nPlease ask an existing Game Master to upgrade your account.');
                        }
                    } catch (e) {
                        console.error('Fix first user error:', e);
                        const errorMsg = e.message || String(e);
                        if (errorMsg.includes('CORS') || errorMsg.includes('fetch')) {
                            alert('Network error: Could not connect to server. Please check that all services are running.');
                        } else {
                            alert('Error checking GM status: ' + errorMsg + '\n\nPlease ask an existing Game Master to upgrade your account.');
                        }
                    }
                }
                return;
            }
            
            const response = await fetch(`${GAME_SESSION_URL}/sessions?gm_user_id=${user.user_id}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    name: sessionName,
                    description: `Game session: ${sessionName}`,
                    game_system_type: 'custom',
                    time_mode_preference: 'real-time'
                })
            });
            
            if (response.ok) {
                const session = await response.json();
                addSystemMessage(`Created game session: ${session.name} (ID: ${session.session_id})`);
                // Refresh in background, don't await
                refreshSessions().catch(err => console.error('Error refreshing sessions:', err));
            } else {
                const error = await response.text();
                alert('Failed to create session: ' + error);
            }
        } catch (error) {
            console.error('Error creating session:', error);
            alert('Error creating session: ' + error.message);
        }
        }, 0);
    }, 0);
});

// Refresh button removed - sessions now auto-refresh
// Check if button exists before adding listener (for backwards compatibility)
const refreshBtn = document.getElementById('refresh-sessions-btn');
if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
        await refreshSessions();
    });
}

let sessionsAutoRefreshInterval = null;

function startSessionsAutoRefresh() {
    if (!sessionsAutoRefreshInterval) {
        sessionsAutoRefreshInterval = setInterval(refreshSessions, 5000); // Refresh every 5 seconds
        console.log("Started sessions auto-refresh.");
    }
}

function stopSessionsAutoRefresh() {
    if (sessionsAutoRefreshInterval) {
        clearInterval(sessionsAutoRefreshInterval);
        sessionsAutoRefreshInterval = null;
        console.log("Stopped sessions auto-refresh.");
    }
}

// Use event delegation for session buttons to avoid re-attaching listeners
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('join-session-btn')) {
        const sessionId = e.target.dataset.sessionId;
        if (sessionId) {
            e.preventDefault();
            // Defer to prevent blocking
            setTimeout(() => joinSession(sessionId), 0);
        }
    } else if (e.target.classList.contains('leave-session-btn')) {
        const sessionId = e.target.dataset.sessionId;
        if (sessionId) {
            e.preventDefault();
            // Defer to prevent blocking
            setTimeout(() => leaveSession(sessionId), 0);
        }
    } else if (e.target.classList.contains('delete-session-btn')) {
        const sessionId = e.target.dataset.sessionId;
        const sessionName = e.target.dataset.sessionName;
        if (sessionId && sessionName) {
            e.preventDefault();
            // Defer to prevent blocking
            setTimeout(() => deleteSession(sessionId, sessionName), 0);
        }
    }
});

async function refreshSessions() {
    try {
        const token = authToken || localStorage.getItem('authToken');
        const currentUser = window.currentUser;
        const sessionsList = document.getElementById('sessions-list');
        
        if (!sessionsList) return;
        
        // Show loading state immediately
        sessionsList.innerHTML = '<div style="color: #888; padding: 8px; font-size: 0.85em;">Loading sessions...</div>';
        
        // Add timeout to prevent hanging
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
        
        const response = await fetch(`${GAME_SESSION_URL}/sessions`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {},
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            sessionsList.innerHTML = '<div style="color: #ef4444; padding: 8px; font-size: 0.85em;">Could not load sessions.</div>';
            return;
        }
        
        const sessions = await response.json();
        const html = sessions.length === 0 
            ? '<div style="color: #888; padding: 8px; font-size: 0.85em;">No game sessions found. Create one to get started!</div>'
            : sessions.map(session => {
                const playerCount = session.player_user_ids?.length || 0;
                const statusColor = session.status === 'active' ? '#10b981' : session.status === 'paused' ? '#f59e0b' : session.status === 'ended' ? '#ef4444' : '#888';
                const statusIcon = session.status === 'active' ? '▶️' : session.status === 'paused' ? '⏸️' : session.status === 'ended' ? '⏹️' : '⏳';
                const isGM = currentUser && session.gm_user_id === currentUser.user_id;
                const canDelete = isGM && session.status !== 'active';
                const isCurrentSession = currentSession && session.session_id === currentSession.session_id;
                const isPlayer = currentUser && session.player_user_ids && session.player_user_ids.includes(currentUser.user_id);
                const canLeave = isCurrentSession && (isPlayer || isGM);
                // Escape quotes to prevent XSS and syntax errors
                const sessionId = String(session.session_id).replace(/'/g, "\\'").replace(/"/g, '&quot;');
                const sessionName = String(session.name).replace(/'/g, "\\'").replace(/"/g, '&quot;');
                
                return `<div style="padding: 6px 8px; margin-bottom: 4px; background: ${isCurrentSession ? '#2a3a2a' : '#2a2a2a'}; border-radius: 3px; border-left: 3px solid ${isCurrentSession ? '#10b981' : statusColor}; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 200px;">
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <strong style="color: ${isCurrentSession ? '#10b981' : '#4a9eff'}; font-size: 0.9em;">${statusIcon} ${sessionName}</strong>
                            ${isGM ? '<span style="color: #f59e0b; font-size: 0.75em;">(GM)</span>' : ''}
                            ${isCurrentSession ? '<span style="color: #10b981; font-size: 0.75em; font-weight: bold;">(ACTIVE)</span>' : ''}
                        </div>
                        <div style="color: #888; font-size: 0.8em; margin-top: 2px;">
                            ${session.status} • ${playerCount} player${playerCount !== 1 ? 's' : ''}${session.game_system_type ? ` • ${session.game_system_type}` : ''}
                        </div>
                    </div>
                    <div style="display: flex; gap: 4px; align-items: center;">
                        ${isCurrentSession 
                            ? `<button data-session-id="${sessionId}" class="leave-session-btn" style="padding: 4px 10px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Leave</button>`
                            : `<button data-session-id="${sessionId}" class="join-session-btn" style="padding: 4px 10px; background: #4a9eff; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Join</button>`
                        }
                        ${isGM ? `<button onclick="manageSession('${sessionId}')" style="padding: 4px 10px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;" title="Manage Session">⚙️</button>` : ''}
                        ${canDelete ? `<button data-session-id="${sessionId}" data-session-name="${sessionName}" class="delete-session-btn" style="padding: 4px 10px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">🗑️</button>` : ''}
                    </div>
                </div>`;
            }).join('');
        
        // Single DOM update
        sessionsList.innerHTML = html;
        
        // Update current session indicator
        updateCurrentSessionIndicator();
    } catch (error) {
        console.error('Error refreshing sessions:', error);
        const sessionsList = document.getElementById('sessions-list');
        if (sessionsList) {
            let errorMsg = 'Error loading sessions.';
            if (error.name === 'AbortError') {
                errorMsg = 'Request timed out. The server may be slow or unreachable.';
            } else if (error.message) {
                errorMsg = `Error: ${error.message}`;
            }
            sessionsList.innerHTML = `<div style="color: #ef4444; padding: 8px; font-size: 0.85em;">${errorMsg}</div>`;
        }
    }
}

// Manage session function (GM only)
window.manageSession = async function(sessionId) {
    const token = authToken || localStorage.getItem('authToken');
    const currentUser = window.currentUser;
    
    if (!token || !currentUser) {
        alert('Please log in first');
        return;
    }
    
    try {
        // Get session details
        const sessionResponse = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!sessionResponse.ok) {
            throw new Error('Could not load session details');
        }
        
        const session = await sessionResponse.json();
        
        // Verify user is GM of this session
        if (session.gm_user_id !== currentUser.user_id) {
            alert('Only the Game Master of this session can manage it.');
            return;
        }
        
        // Get all users for player selection
        const usersResponse = await fetch(`${AUTH_URL}/users`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!usersResponse.ok) {
            throw new Error('Could not load users');
        }
        
        const allUsers = await usersResponse.json();
        const players = allUsers.filter(u => u.user_id !== session.gm_user_id && u.role === 'player');
        const currentPlayerIds = session.player_user_ids || [];
        
        // Create modal
        const modal = document.createElement('div');
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.8); z-index: 2000; display: flex; align-items: center; justify-content: center;';
        modal.innerHTML = `
            <div style="background: #1a1a1a; border: 1px solid #444; border-radius: 8px; padding: 25px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto; position: relative; box-shadow: 0 5px 25px rgba(0, 0, 0, 0.7);">
                <button onclick="this.closest('div[style*=\"position: fixed\"]').remove()" style="position: absolute; top: 15px; right: 15px; background: #ef4444; color: white; border: none; border-radius: 4px; padding: 8px 15px; cursor: pointer; font-size: 0.9em;">✕ Close</button>
                <h3 style="margin-top: 0; margin-bottom: 20px; color: #e0e0e0; font-size: 1.4em;">Manage Session: ${escapeHTML(session.name)}</h3>
                
                <div style="display: flex; flex-direction: column; gap: 20px;">
                    <!-- Session Information -->
                    <div style="background: #2a2a2a; padding: 15px; border-radius: 4px;">
                        <h4 style="margin: 0 0 12px 0; color: #4a9eff; font-size: 1.1em;">Session Information</h4>
                        <div style="display: flex; flex-direction: column; gap: 10px;">
                            <div>
                                <label style="display: block; color: #888; font-size: 0.85em; margin-bottom: 4px;">Name:</label>
                                <input type="text" id="session-edit-name" value="${escapeHTML(session.name)}" style="width: 100%; padding: 6px 8px; background: #1a1a1a; border: 1px solid #444; border-radius: 3px; color: #e0e0e0; font-size: 0.9em;">
                            </div>
                            <div>
                                <label style="display: block; color: #888; font-size: 0.85em; margin-bottom: 4px;">Description:</label>
                                <textarea id="session-edit-description" rows="3" style="width: 100%; padding: 6px 8px; background: #1a1a1a; border: 1px solid #444; border-radius: 3px; color: #e0e0e0; font-size: 0.9em; resize: vertical;">${escapeHTML(session.description || '')}</textarea>
                            </div>
                            <div>
                                <label style="display: block; color: #888; font-size: 0.85em; margin-bottom: 4px;">Game System:</label>
                                <input type="text" id="session-edit-game-system" value="${escapeHTML(session.game_system_type || '')}" placeholder="D&D 5e, Pathfinder, custom, etc." style="width: 100%; padding: 6px 8px; background: #1a1a1a; border: 1px solid #444; border-radius: 3px; color: #e0e0e0; font-size: 0.9em;">
                            </div>
                            <div>
                                <label style="display: block; color: #888; font-size: 0.85em; margin-bottom: 4px;">Status:</label>
                                <select id="session-edit-status" style="width: 100%; padding: 6px 8px; background: #1a1a1a; border: 1px solid #444; border-radius: 3px; color: #e0e0e0; font-size: 0.9em;">
                                    <option value="created" ${session.status === 'created' ? 'selected' : ''}>Created</option>
                                    <option value="active" ${session.status === 'active' ? 'selected' : ''}>Active</option>
                                    <option value="paused" ${session.status === 'paused' ? 'selected' : ''}>Paused</option>
                                    <option value="ended" ${session.status === 'ended' ? 'selected' : ''}>Ended</option>
                                </select>
                            </div>
                            <div>
                                <label style="display: block; color: #888; font-size: 0.85em; margin-bottom: 4px;">Time Mode:</label>
                                <select id="session-edit-time-mode" style="width: 100%; padding: 6px 8px; background: #1a1a1a; border: 1px solid #444; border-radius: 3px; color: #e0e0e0; font-size: 0.9em;">
                                    <option value="real-time" ${session.time_mode_preference === 'real-time' ? 'selected' : ''}>Real-time</option>
                                    <option value="turn-based" ${session.time_mode_preference === 'turn-based' ? 'selected' : ''}>Turn-based</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Player Management -->
                    <div style="background: #2a2a2a; padding: 15px; border-radius: 4px;">
                        <h4 style="margin: 0 0 12px 0; color: #10b981; font-size: 1.1em;">Players (${currentPlayerIds.length})</h4>
                        <div id="session-players-list" style="margin-bottom: 12px; max-height: 200px; overflow-y: auto;">
                            ${currentPlayerIds.length === 0 
                                ? '<div style="color: #888; font-size: 0.85em; padding: 8px;">No players in this session</div>'
                                : currentPlayerIds.map(playerId => {
                                    const player = allUsers.find(u => u.user_id === playerId);
                                    return player ? `
                                        <div style="padding: 6px 8px; margin-bottom: 4px; background: #1a1a1a; border-radius: 3px; display: flex; justify-content: space-between; align-items: center;">
                                            <span style="color: #e0e0e0; font-size: 0.9em;">${escapeHTML(player.username)} (${escapeHTML(player.email)})</span>
                                            <button onclick="removePlayerFromSession('${sessionId}', '${playerId}', '${escapeHTML(player.username)}')" style="padding: 4px 8px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em;">Remove</button>
                                        </div>
                                    ` : '';
                                }).join('')}
                        </div>
                        <div>
                            <label style="display: block; color: #888; font-size: 0.85em; margin-bottom: 4px;">Add Player:</label>
                            <select id="session-add-player-select" style="width: 100%; padding: 6px 8px; background: #1a1a1a; border: 1px solid #444; border-radius: 3px; color: #e0e0e0; font-size: 0.9em;">
                                <option value="">Select a player...</option>
                                ${players.filter(p => !currentPlayerIds.includes(p.user_id)).map(p => 
                                    `<option value="${p.user_id}">${escapeHTML(p.username)} (${escapeHTML(p.email)})</option>`
                                ).join('')}
                            </select>
                            <button onclick="addPlayerToSession('${sessionId}')" style="margin-top: 8px; padding: 6px 12px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Add Player</button>
                        </div>
                    </div>
                    
                    <!-- Actions -->
                    <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px;">
                        <button onclick="this.closest('div[style*=\"position: fixed\"]').remove()" style="padding: 8px 16px; background: #666; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em;">Cancel</button>
                        <button onclick="saveSessionChanges('${sessionId}')" style="padding: 8px 16px; background: #4a9eff; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em; font-weight: bold;">Save Changes</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    } catch (error) {
        console.error('Error loading session management:', error);
        alert('Error loading session management: ' + error.message);
    }
};

// Save session changes
window.saveSessionChanges = async function(sessionId) {
    const token = authToken || localStorage.getItem('authToken');
    const currentUser = window.currentUser;
    
    if (!token || !currentUser) {
        alert('Please log in first');
        return;
    }
    
    try {
        const name = document.getElementById('session-edit-name').value.trim();
        if (!name) {
            alert('Session name is required');
            return;
        }
        
        const description = document.getElementById('session-edit-description').value.trim();
        const gameSystem = document.getElementById('session-edit-game-system').value.trim();
        const status = document.getElementById('session-edit-status').value;
        const timeMode = document.getElementById('session-edit-time-mode').value;
        
        const response = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}?gm_user_id=${currentUser.user_id}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description || null,
                game_system_type: gameSystem || null,
                status: status,
                time_mode_preference: timeMode
            })
        });
        
        if (response.ok) {
            addSystemMessage('Session updated successfully', 'success');
            document.querySelector('div[style*="position: fixed"][style*="z-index: 2000"]')?.remove();
            await refreshSessions();
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to update session';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            alert(errorMessage);
        }
    } catch (error) {
        console.error('Error saving session changes:', error);
        alert('Error saving session changes: ' + error.message);
    }
};

// Add player to session
window.addPlayerToSession = async function(sessionId) {
    const token = authToken || localStorage.getItem('authToken');
    const currentUser = window.currentUser;
    
    if (!token || !currentUser) {
        alert('Please log in first');
        return;
    }
    
    const select = document.getElementById('session-add-player-select');
    const userId = select.value;
    
    if (!userId) {
        alert('Please select a player');
        return;
    }
    
    try {
        const response = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}/players/${userId}?gm_user_id=${currentUser.user_id}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            addSystemMessage('Player added to session', 'success');
            // Reload the management modal
            document.querySelector('div[style*="position: fixed"][style*="z-index: 2000"]')?.remove();
            await manageSession(sessionId);
            await refreshSessions();
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to add player';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            alert(errorMessage);
        }
    } catch (error) {
        console.error('Error adding player:', error);
        alert('Error adding player: ' + error.message);
    }
};

// Remove player from session
window.removePlayerFromSession = async function(sessionId, userId, username) {
    const token = authToken || localStorage.getItem('authToken');
    const currentUser = window.currentUser;
    
    if (!token || !currentUser) {
        alert('Please log in first');
        return;
    }
    
    const confirmed = await customConfirm(
        `Remove "${username}" from this session?`,
        'Remove Player'
    );
    
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}/players/${userId}?gm_user_id=${currentUser.user_id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            addSystemMessage(`Player "${username}" removed from session`, 'success');
            // Reload the management modal
            document.querySelector('div[style*="position: fixed"][style*="z-index: 2000"]')?.remove();
            await manageSession(sessionId);
            await refreshSessions();
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to remove player';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            alert(errorMessage);
        }
    } catch (error) {
        console.error('Error removing player:', error);
        alert('Error removing player: ' + error.message);
    }
};

// Delete session function - use non-blocking custom confirm
window.deleteSession = async function(sessionId, sessionName) {
    const confirmed = await customConfirm(
        `Are you sure you want to delete the session "${sessionName}"?\n\nThis will permanently delete the session and all associated data. This cannot be undone!`,
        'Delete Session'
    );
    
    if (!confirmed) {
        return;
    }
    
    try {
        const token = authToken || localStorage.getItem('authToken');
        const currentUser = window.currentUser;
        
        if (!currentUser) {
            alert('You must be logged in to delete a session.');
            return;
        }
        
        const response = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}?gm_user_id=${currentUser.user_id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            // Refresh sessions in background
            refreshSessions().catch(err => console.error('Error refreshing sessions:', err));
            alert(`Session "${sessionName}" deleted successfully!`);
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to delete session';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            alert(errorMessage);
        }
    } catch (error) {
        console.error('Error deleting session:', error);
        alert('Error deleting session: ' + error.message);
    }
};

// User management for GMs - set up event listener when button is available
function setupManageUsersButton() {
    const manageUsersBtn = document.getElementById('manage-users-btn');
    if (manageUsersBtn && !manageUsersBtn.hasAttribute('data-listener-attached')) {
        manageUsersBtn.setAttribute('data-listener-attached', 'true');
        manageUsersBtn.addEventListener('click', async () => {
            await showUserManagementModal();
        });
    }
}

async function showUserManagementModal() {
    try {
        const token = authToken || localStorage.getItem('authToken');
        
        // Load users
        const usersResponse = await fetch(`${AUTH_URL}/users`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!usersResponse.ok) {
            alert('Could not load users. You must be a GM to manage users.');
            return;
        }
        
        const users = await usersResponse.json();
        
        // Load all characters for assignment (from auth service)
        let allCharacters = [];
        try {
            const charsResponse = await fetch(`${AUTH_URL}/beings/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (charsResponse.ok) {
                const charsData = await charsResponse.json();
                allCharacters = charsData.characters || [];
            }
        } catch (e) {
            console.warn('Could not load characters:', e);
        }
        
        // Create modal
        const modal = document.createElement('div');
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 1000; display: flex; align-items: center; justify-content: center; overflow-y: auto;';
        
        const usersHtml = users.map(user => {
            const isCurrentUser = user.user_id === window.currentUser?.user_id;
            const roleColor = user.role === 'gm' ? '#f59e0b' : '#4a9eff';
            const roleIcon = user.role === 'gm' ? '👑' : '👤';
            
            return `
                <div id="user-${user.user_id}" style="padding: 6px 8px; margin-bottom: 4px; background: #2a2a2a; border-radius: 3px; border-left: 3px solid ${roleColor}; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <div style="display: flex; align-items: center; gap: 6px; min-width: 150px; flex: 1;">
                        <strong style="color: ${roleColor}; font-size: 0.9em;">${roleIcon} ${user.username}</strong>
                        ${isCurrentUser ? '<span style="color: #888; font-size: 0.75em;">(You)</span>' : ''}
                    </div>
                    <div style="color: #888; font-size: 0.8em; min-width: 180px; flex: 1;">${user.email}</div>
                    <div style="display: flex; gap: 4px; align-items: center; flex-wrap: wrap;">
                        <select id="role-${user.user_id}" style="padding: 3px 6px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.8em;">
                            <option value="player" ${user.role === 'player' ? 'selected' : ''}>Player</option>
                            <option value="gm" ${user.role === 'gm' ? 'selected' : ''}>GM</option>
                        </select>
                        <button onclick="updateUserRole('${user.user_id}')" style="padding: 3px 8px; background: #4a9eff; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.8em;">Update</button>
                        <button onclick="manageUserCharacters('${user.user_id}', '${user.username}')" style="padding: 3px 8px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.8em;">📋</button>
                        ${!isCurrentUser ? `<button onclick="deleteUser('${user.user_id}', '${user.username}')" style="padding: 3px 8px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.8em;">🗑️</button>` : '<span style="color: #666; font-size: 0.75em;">-</span>'}
                    </div>
                    <div style="color: #666; font-size: 0.75em; min-width: 140px; text-align: right;">${new Date(user.created_at).toLocaleDateString()}</div>
                </div>
            `;
        }).join('');
        
        modal.innerHTML = `
            <div style="background: #1a1a1a; padding: 10px; border-radius: 4px; max-width: 900px; width: 90%; max-height: 90vh; overflow-y: auto; position: relative;">
                <button onclick="this.parentElement.parentElement.remove()" style="position: absolute; top: 8px; right: 8px; background: #ef4444; color: white; border: none; border-radius: 3px; padding: 5px 10px; cursor: pointer; font-size: 0.85em;">✕ Close</button>
                <h2 style="margin-top: 0; margin-bottom: 8px; color: #e0e0e0; font-size: 1.1em;">👥 User Management</h2>
                <p style="color: #888; font-size: 0.85em; margin-bottom: 8px;">
                    Manage user accounts: change roles, assign characters, and delete accounts. Only Game Masters can access this panel.
                </p>
                <div id="users-list" style="margin-bottom: 8px;">
                    ${usersHtml}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Store data for use by button handlers
        window.userManagementData = { users, allCharacters, token };
        
    } catch (error) {
        console.error('Error loading user management:', error);
        alert('Error loading user management: ' + error.message);
    }
}

// Update user role
window.updateUserRole = async function(userId) {
    try {
        const roleSelect = document.getElementById(`role-${userId}`);
        const newRole = roleSelect.value;
        const token = window.userManagementData?.token || authToken || localStorage.getItem('authToken');
        
        const response = await fetch(`${AUTH_URL}/users/${userId}/role?role=${newRole}`, {
            method: 'PUT',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`User role updated to ${newRole}!`);
            
            // If current user's role changed, reload page
            if (userId === window.currentUser?.user_id) {
                alert('Your role was changed. Refreshing page...');
                window.location.reload();
            } else {
                // Refresh the modal
                document.querySelector('div[style*="position: fixed"]')?.remove();
                await showUserManagementModal();
            }
        } else {
            const error = await response.text();
            alert('Failed to update role: ' + error);
        }
    } catch (error) {
        console.error('Error updating role:', error);
        alert('Error updating role: ' + error.message);
    }
};

// Delete user
window.deleteUser = async function(userId, username) {
    const confirmed = await customConfirm(
        `Are you sure you want to delete user "${username}"?\n\nThis will:\n- Delete their account permanently\n- Remove them from all character assignments\n- Cannot be undone!`,
        'Delete User'
    );
    if (!confirmed) {
        return;
    }
    
    try {
        const token = window.userManagementData?.token || authToken || localStorage.getItem('authToken');
        
        const response = await fetch(`${AUTH_URL}/users/${userId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            alert(`User "${username}" deleted successfully!`);
            // Refresh the modal
            document.querySelector('div[style*="position: fixed"]')?.remove();
            await showUserManagementModal();
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to delete user';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            alert(errorMessage);
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        alert('Error deleting user: ' + error.message);
    }
};

// Manage user characters
window.manageUserCharacters = async function(userId, username) {
    try {
        const token = window.userManagementData?.token || authToken || localStorage.getItem('authToken');
        
        // Get user's current characters
        const userCharsResponse = await fetch(`${AUTH_URL}/users/${userId}/characters`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        let userCharacters = { owned: [], assigned: [] };
        if (userCharsResponse.ok) {
            userCharacters = await userCharsResponse.json();
        }
        
        // Get all available characters
        const allChars = window.userManagementData?.allCharacters || [];
        
        // Create character assignment modal
        const modal = document.createElement('div');
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 2000; display: flex; align-items: center; justify-content: center; overflow-y: auto;';
        
        const ownedChars = userCharacters.owned || [];
        const assignedChars = userCharacters.assigned || [];
        const ownedIds = new Set(ownedChars.map(c => c.being_id));
        const assignedIds = new Set(assignedChars.map(c => c.being_id));
        
        const availableChars = allChars.filter(c => !ownedIds.has(c.being_id));
        
        const ownedHtml = ownedChars.length > 0 
            ? ownedChars.map(c => {
                const char = allChars.find(ch => ch.being_id === c.being_id);
                return `
                    <div style="padding: 8px; margin-bottom: 5px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid #10b981;">
                        <strong>${char?.name || c.being_id}</strong> <span style="color: #888; font-size: 0.85em;">(Owner)</span>
                    </div>
                `;
            }).join('')
            : '<div style="color: #888; font-style: italic;">No owned characters</div>';
        
        const assignedHtml = assignedChars.length > 0
            ? assignedChars.map(c => {
                const char = allChars.find(ch => ch.being_id === c.being_id);
                return `
                    <div style="padding: 8px; margin-bottom: 5px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid #4a9eff; display: flex; justify-content: space-between; align-items: center;">
                        <div><strong>${char?.name || c.being_id}</strong> <span style="color: #888; font-size: 0.85em;">(Assigned)</span></div>
                        <button onclick="unassignCharacter('${c.being_id}', '${userId}', '${username}')" style="padding: 3px 8px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em;">Remove</button>
                    </div>
                `;
            }).join('')
            : '<div style="color: #888; font-style: italic;">No assigned characters</div>';
        
        const availableHtml = availableChars.length > 0
            ? availableChars.map(char => {
                return `
                    <div style="padding: 8px; margin-bottom: 5px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid #888; display: flex; justify-content: space-between; align-items: center;">
                        <div><strong>${char.name || char.being_id}</strong> <span style="color: #666; font-size: 0.85em;">(Owner: ${char.owner_username || 'Unknown'})</span></div>
                        <button onclick="assignCharacter('${char.being_id}', '${userId}', '${username}')" style="padding: 3px 8px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em;">Assign</button>
                    </div>
                `;
            }).join('')
            : '<div style="color: #888; font-style: italic;">No available characters to assign</div>';
        
        modal.innerHTML = `
            <div style="background: #1a1a1a; padding: 25px; border-radius: 8px; max-width: 700px; width: 90%; max-height: 90vh; overflow-y: auto; position: relative;">
                <button onclick="this.parentElement.parentElement.remove()" style="position: absolute; top: 15px; right: 15px; background: #ef4444; color: white; border: none; border-radius: 4px; padding: 8px 15px; cursor: pointer; font-size: 0.9em;">✕ Close</button>
                <h3 style="margin-top: 0; margin-bottom: 15px; color: #e0e0e0;">📋 Character Management: ${username}</h3>
                
                <div style="margin-bottom: 20px;">
                    <h4 style="color: #10b981; margin-bottom: 8px;">Owned Characters</h4>
                    <div style="max-height: 150px; overflow-y: auto;">
                        ${ownedHtml}
                    </div>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <h4 style="color: #4a9eff; margin-bottom: 8px;">Assigned Characters</h4>
                    <div style="max-height: 150px; overflow-y: auto;">
                        ${assignedHtml}
                    </div>
                </div>
                
                <div>
                    <h4 style="color: #888; margin-bottom: 8px;">Available to Assign</h4>
                    <div style="max-height: 200px; overflow-y: auto;">
                        ${availableHtml}
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
    } catch (error) {
        console.error('Error loading character management:', error);
        alert('Error loading character management: ' + error.message);
    }
};

// Assign character to user
window.assignCharacter = async function(beingId, userId, username) {
    try {
        const token = window.userManagementData?.token || authToken || localStorage.getItem('authToken');
        
        const response = await fetch(`${AUTH_URL}/beings/${beingId}/assign?user_id=${userId}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            alert(`Character assigned to ${username}!`);
            // Refresh character management modal
            document.querySelector('div[style*="z-index: 2000"]')?.remove();
            await manageUserCharacters(userId, username);
        } else {
            const error = await response.text();
            alert('Failed to assign character: ' + error);
        }
    } catch (error) {
        console.error('Error assigning character:', error);
        alert('Error assigning character: ' + error.message);
    }
};

// Unassign character from user
window.unassignCharacter = async function(beingId, userId, username) {
    try {
        const token = window.userManagementData?.token || authToken || localStorage.getItem('authToken');
        
        const response = await fetch(`${AUTH_URL}/beings/${beingId}/assign?user_id=${userId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            alert(`Character unassigned from ${username}!`);
            // Refresh character management modal
            document.querySelector('div[style*="z-index: 2000"]')?.remove();
            await manageUserCharacters(userId, username);
        } else {
            const error = await response.text();
            alert('Failed to unassign character: ' + error);
        }
    } catch (error) {
        console.error('Error unassigning character:', error);
        alert('Error unassigning character: ' + error.message);
    }
};

// Setup validate system button (GM only)
function setupValidateSystemButton() {
    const validateBtn = document.getElementById('validate-system-btn');
    if (validateBtn && window.currentUser?.role === 'gm') {
        validateBtn.style.display = 'inline-block';
        if (!validateBtn.hasAttribute('data-listener-attached')) {
            validateBtn.setAttribute('data-listener-attached', 'true');
            validateBtn.addEventListener('click', async () => {
                const token = authToken || localStorage.getItem('authToken');
                if (!token) {
                    alert('You must be logged in to check system health.');
                    return;
                }
                
                // Show loading state
                const originalText = validateBtn.textContent;
                validateBtn.disabled = true;
                validateBtn.textContent = '⏳ Checking...';
                validateBtn.style.opacity = '0.7';
                
                try {
                    const response = await fetch(`${BEING_REGISTRY_URL}/system/validate`, {
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    
                    if (response.ok) {
                        const report = await response.json();
                        displayValidationReport(report);
                    } else {
                        const errorText = await response.text();
                        let errorMessage = 'Failed to check system health';
                        try {
                            const errorJson = JSON.parse(errorText);
                            errorMessage = errorJson.detail || errorMessage;
                        } catch {
                            errorMessage = errorText || errorMessage;
                        }
                        alert(`System Health Check Failed:\n\n${errorMessage}\n\nStatus: ${response.status}`);
                    }
                } catch (error) {
                    console.error('Error validating system:', error);
                    alert(`System Health Check Error:\n\n${error.message}\n\nThis might indicate a network issue or that the Being Registry service is not available.`);
                } finally {
                    // Restore button state
                    validateBtn.disabled = false;
                    validateBtn.textContent = originalText;
                    validateBtn.style.opacity = '1';
                }
            });
        }
    } else if (validateBtn) {
        validateBtn.style.display = 'none';
    }
}

function displayValidationReport(report) {
    const modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 1000; display: flex; align-items: center; justify-content: center; overflow-y: auto;';
    
    const overallStatus = report.overall_status;
    const statusColor = overallStatus === 'healthy' ? '#10b981' : overallStatus === 'degraded' ? '#f59e0b' : '#ef4444';
    const statusIcon = overallStatus === 'healthy' ? '✅' : overallStatus === 'degraded' ? '⚠️' : '❌';
    
    let servicesHtml = '';
    for (const [name, status] of Object.entries(report.services || {})) {
        const serviceStatus = status.status || 'unknown';
        const serviceColor = serviceStatus === 'healthy' ? '#10b981' : '#ef4444';
        const serviceIcon = serviceStatus === 'healthy' ? '✅' : '❌';
        const responseTime = status.response_time_ms ? ` (${status.response_time_ms.toFixed(0)}ms)` : '';
        servicesHtml += `
            <div style="padding: 5px 6px; margin-bottom: 4px; background: #2a2a2a; border-radius: 3px; border-left: 2px solid ${serviceColor};">
                <strong style="font-size: 0.9em;">${serviceIcon} ${name}</strong>
                <span style="color: ${serviceColor}; margin-left: 8px; font-size: 0.85em;">${status.message || serviceStatus}${responseTime}</span>
            </div>
        `;
    }
    
    let integrationsHtml = '';
    if (report.integrations && Object.keys(report.integrations).length > 0) {
        for (const [name, integration] of Object.entries(report.integrations)) {
            const intStatus = (typeof integration === 'object' && integration.healthy !== undefined) 
                ? (integration.healthy ? 'ok' : 'error')
                : (typeof integration === 'object' && integration.status) 
                    ? integration.status 
                    : 'unknown';
            const intColor = intStatus === 'ok' || intStatus === 'healthy' ? '#10b981' : intStatus === 'warning' ? '#f59e0b' : '#ef4444';
            const intIcon = intStatus === 'ok' || intStatus === 'healthy' ? '✅' : intStatus === 'warning' ? '⚠️' : '❌';
            const intObj = typeof integration === 'object' ? integration : { message: integration };
            let detailsHtml = '';
            if (intObj.details) {
                detailsHtml = `<div style="color: #666; font-size: 0.8em; margin-top: 3px; padding-left: 8px;">${JSON.stringify(intObj.details, null, 2).replace(/\n/g, '<br>').replace(/ /g, '&nbsp;')}</div>`;
            }
            integrationsHtml += `
                <div style="padding: 5px 6px; margin-bottom: 4px; background: #2a2a2a; border-radius: 3px; border-left: 2px solid ${intColor};">
                    <strong style="font-size: 0.9em;">${intIcon} ${name.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</strong>
                    <div style="color: #888; font-size: 0.85em; margin-top: 3px;">${intObj.message || intStatus}</div>
                    ${detailsHtml}
                </div>
            `;
        }
    } else {
        integrationsHtml = '<div style="color: #888; font-size: 0.85em; padding: 6px;">No integration data available</div>';
    }
    
    modal.innerHTML = `
        <div style="background: #1a1a1a; padding: 10px; border-radius: 4px; max-width: 80%; max-height: 90%; overflow: auto; position: relative; min-width: 600px;">
            <button onclick="this.parentElement.parentElement.remove()" style="position: absolute; top: 8px; right: 8px; background: #ef4444; color: white; border: none; border-radius: 3px; padding: 5px 10px; cursor: pointer; font-size: 0.85em;">Close</button>
            <h2 style="margin-top: 0; margin-bottom: 8px; color: ${statusColor}; font-size: 1.1em;">
                ${statusIcon} System Validation Report
            </h2>
            <div style="margin-bottom: 8px; padding: 8px; background: #2a2a2a; border-radius: 3px; border-left: 2px solid #4a9eff;">
                <p style="color: #e0e0e0; margin: 0; font-size: 0.85em;">
                    <strong>What this does:</strong> Checks the health and connectivity of all core services (Auth, Rules Engine, Game Master, Worlds, Being Registry, Time Management) and validates key integrations between services. Use this to diagnose system issues.
                </p>
            </div>
            <div style="margin-bottom: 8px; padding: 6px 8px; background: #2a2a2a; border-radius: 3px; border-left: 2px solid ${statusColor};">
                <strong style="font-size: 0.9em;">Overall Status: <span style="color: ${statusColor};">${overallStatus.toUpperCase()}</span></strong>
                <div style="color: #888; font-size: 0.8em; margin-top: 3px;">Validated at: ${new Date(report.timestamp || Date.now()).toLocaleString()}</div>
            </div>
            
            <h3 style="color: #e0e0e0; margin-bottom: 6px; font-size: 1em;">Services</h3>
            <div style="margin-bottom: 8px;">
                ${servicesHtml}
            </div>
            
            <h3 style="color: #e0e0e0; margin-bottom: 6px; font-size: 1em;">Integrations</h3>
            <div style="margin-bottom: 8px;">
                ${integrationsHtml}
            </div>
            
            ${report.recommendations && report.recommendations.length > 0 ? `
                <h3 style="color: #f59e0b; margin-bottom: 6px; font-size: 1em;">Recommendations</h3>
                <ul style="color: #888; font-size: 0.85em; margin: 0; padding-left: 20px;">
                    ${report.recommendations.map(r => `<li style="margin-bottom: 3px;">${r}</li>`).join('')}
                </ul>
            ` : ''}
        </div>
    `;
    document.body.appendChild(modal);
}

// Make joinSession available globally
window.joinSession = async function(sessionId) {
    try {
        const token = authToken || localStorage.getItem('authToken');
        if (!token) {
            addSystemMessage('Please log in first', 'warning');
            return;
        }
        
        const userResponse = await fetch(`${AUTH_URL}/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const user = await userResponse.json();
        
        const response = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}/join?user_id=${user.user_id}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            // Get session details
            const sessionResponse = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (sessionResponse.ok) {
                const session = await sessionResponse.json();
                window.currentSession = session;
                localStorage.setItem('currentSessionId', sessionId);
                updateCurrentSessionIndicator();
            }
            
            // Session join is a system message
            addSystemMessage(`You joined session "${session.name || sessionId}"`, 'success');
            await refreshSessions();
            // Reload characters for this session
            await loadUserCharacters();
            // Reload being chat data
            loadBeingChatCharacters();
            loadNearbyBeings();
            loadAllBeings();
            // Update active prompts indicator if LLM service is active in being chat
            if (currentChatType === 'llm' && currentBeingChatId) {
                await updateActivePromptsIndicator(currentBeingChatId);
            }
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to join session';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            addSystemMessage(`Failed to join session: ${errorMessage}`, 'error');
        }
    } catch (error) {
        console.error('Error joining session:', error);
        addSystemMessage(`Error joining session: ${error.message}`, 'error');
    }
};

// Make leaveSession available globally
window.leaveSession = async function(sessionId) {
    try {
        const token = authToken || localStorage.getItem('authToken');
        if (!token) {
            addSystemMessage('Please log in first', 'warning');
            return;
        }
        
        const userResponse = await fetch(`${AUTH_URL}/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const user = await userResponse.json();
        
        // Get session name before leaving
        let sessionName = sessionId;
        try {
            const sessionResponse = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (sessionResponse.ok) {
                const session = await sessionResponse.json();
                sessionName = session.name || sessionId;
            }
        } catch (e) {
            // Continue even if we can't get session name
        }
        
        const response = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}/leave?user_id=${user.user_id}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            // Clear current session if it's the one we're leaving
            if (window.currentSession && window.currentSession.session_id === sessionId) {
                window.currentSession = null;
                localStorage.removeItem('currentSessionId');
                updateCurrentSessionIndicator();
            }
            
            addSystemMessage(`You left session "${sessionName}"`, 'info');
            await refreshSessions();
            // Reload characters (they may have been session-specific)
            await loadUserCharacters();
            loadBeingChatCharacters();
            loadNearbyBeings();
            loadAllBeings();
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to leave session';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            addSystemMessage(`Failed to leave session: ${errorMessage}`, 'error');
        }
    } catch (error) {
        console.error('Error leaving session:', error);
        addSystemMessage(`Error leaving session: ${error.message}`, 'error');
    }
};

// Update current session indicator
function updateCurrentSessionIndicator() {
    const indicator = document.getElementById('current-session-indicator');
    const nameSpan = document.getElementById('current-session-name');
    const infoSpan = document.getElementById('current-session-info');
    const clearBtn = document.getElementById('clear-session-btn');
    
    if (!indicator || !nameSpan || !infoSpan || !clearBtn) return;
    
    const currentSession = window.currentSession;
    
    if (currentSession) {
        indicator.style.display = 'block';
        nameSpan.textContent = currentSession.name || currentSession.session_id.substring(0, 16) + '...';
        const playerCount = currentSession.player_user_ids?.length || 0;
        infoSpan.textContent = `${currentSession.status} • ${playerCount} player${playerCount !== 1 ? 's' : ''}${currentSession.game_system_type ? ` • ${currentSession.game_system_type}` : ''}`;
        clearBtn.onclick = () => {
            if (window.currentSession) {
                leaveSession(window.currentSession.session_id);
            }
        };
    } else {
        indicator.style.display = 'none';
    }
}

// Load user info and set up UI
async function loadUserInfo() {
    // Get token from localStorage if not in memory
    const token = authToken || localStorage.getItem('authToken');
    if (!token) {
        console.log('No auth token available for loadUserInfo');
        return;
    }
    
    try {
        const userResponse = await fetch(`${AUTH_URL}/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (userResponse.ok) {
            const user = await userResponse.json();
            const roleDisplay = document.getElementById('user-role');
            const manageUsersBtn = document.getElementById('manage-users-btn');
            
            if (roleDisplay) {
                roleDisplay.textContent = `(${user.role})`;
            }
            
            // Show "Manage Users", "Manage Rules", and "Validate System" buttons for GMs
            if (user.role === 'gm') {
                if (manageUsersBtn) {
                    manageUsersBtn.style.display = 'inline-block';
                    // Set up event listener when button becomes visible
                    setupManageUsersButton();
                }
                const manageRulesBtn = document.getElementById('manage-rules-btn');
                if (manageRulesBtn) {
                    manageRulesBtn.style.display = 'inline-block';
                }
                // Show LLM Services section in being chat sidebar
                const llmServicesSection = document.getElementById('llm-services-section');
                if (llmServicesSection) {
                    llmServicesSection.style.display = 'block';
                }
                // Add click handlers for LLM service items
                document.querySelectorAll('.llm-service-item').forEach(item => {
                    item.addEventListener('click', () => {
                        const service = item.dataset.service;
                        switchBeingChat(service, null, 'llm');
                    });
                });
                const validateSystemBtn = document.getElementById('validate-system-btn');
                if (validateSystemBtn) {
                    validateSystemBtn.style.display = 'inline-block';
                }
                const systemPromptsBtn = document.getElementById('system-prompts-btn');
                if (systemPromptsBtn) {
                    systemPromptsBtn.style.display = 'inline-block';
                }
            } else {
                const manageRulesBtn = document.getElementById('manage-rules-btn');
                if (manageRulesBtn) {
                    manageRulesBtn.style.display = 'none';
                }
                // Hide LLM Services section for non-GMs
                const llmServicesSection = document.getElementById('llm-services-section');
                if (llmServicesSection) {
                    llmServicesSection.style.display = 'none';
                }
                const validateSystemBtn = document.getElementById('validate-system-btn');
                if (validateSystemBtn) {
                    validateSystemBtn.style.display = 'none';
                }
                const systemPromptsBtn = document.getElementById('system-prompts-btn');
                if (systemPromptsBtn) {
                    systemPromptsBtn.style.display = 'none';
                }
            }
            
            // Store user info globally
            window.currentUser = user;
        }
    } catch (error) {
        console.error('Error loading user info:', error);
    }
}

// Load initial game state
async function loadGameState() {
    try {
        // Get token from localStorage if not in memory
        const token = authToken || localStorage.getItem('authToken');
        if (!token) {
            console.log('No auth token available for loadGameState');
            return;
        }
        
        // Get user info
        const userResponse = await fetch(`${AUTH_URL}/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (userResponse.ok) {
            const user = await userResponse.json();
            addSystemMessage(`User logged in: ${user.username} (${user.role})`);
        }
        
        // List game sessions (no auth required for listing)
        try {
            const sessionsResponse = await fetch(`${GAME_SESSION_URL}/sessions`);
            
            if (sessionsResponse.ok) {
                const sessions = await sessionsResponse.json();
                if (sessions.length > 0) {
                    addSystemMessage(`Found ${sessions.length} game session(s)`);
                }
            } else {
                addSystemMessage(`Could not list sessions: HTTP ${sessionsResponse.status}`, 'error');
            }
        } catch (e) {
            addSystemMessage(`Error listing sessions: ${e.message}`, 'error');
        }
        
        // System initialization - this is a system event, not a game event
        // Game Events should only show actual game mechanics (actions, world changes, etc.)
        addSystemMessage('System initialized. Ready to play!');
        
    } catch (error) {
        console.error('Error loading game state:', error);
        addSystemMessage('Could not load game state. Some features may not work.');
    }
    
    // Load user's characters
    await loadUserCharacters();
    
    // Load being chat characters and nearby beings
    loadBeingChatCharacters();
    loadNearbyBeings();
    
    // Load all beings for GM
    loadAllBeings();
    setupAllBeingsSearch();
}

// Load user's characters
async function loadUserCharacters() {
    // Get token from localStorage if not in memory
    const token = authToken || localStorage.getItem('authToken');
    if (!token) {
        console.log('No auth token available, skipping character load');
        return;
    }
    
    try {
        const response = await fetch(`${BEING_REGISTRY_URL}/beings/my-characters`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const select = document.getElementById('character-select');
            
            // Only update if the select element exists (it might not be on all pages)
            if (select) {
                // Clear existing options except the first one
                while (select.options.length > 1) {
                    select.remove(1);
                }
                
                // Add characters to select
                if (data.characters && data.characters.length > 0) {
                    data.characters.forEach(char => {
                        const option = document.createElement('option');
                        option.value = char.being_id;
                        option.textContent = char.name || char.being_id;
                        select.appendChild(option);
                    });
                }
            }
        } else if (response.status === 401) {
            // Token expired or invalid, clear it and show login
            addSystemMessage('Authentication failed, please log in again', 'error');
            authToken = null;
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
        } else {
            addSystemMessage(`Error loading characters: HTTP ${response.status}`, 'error');
        }
    } catch (error) {
        console.error('Error loading characters:', error);
        addSystemMessage(`Error loading characters: ${error.message}`, 'error');
    }
}

// Rules management (GM only) - with auto-refresh
document.getElementById('manage-characters-btn')?.addEventListener('click', () => {
    const panel = document.getElementById('character-management');
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
        loadCharactersForManagement();
    } else {
        panel.style.display = 'none';
    }
});

// Setup character search and filter
document.getElementById('character-search')?.addEventListener('input', (e) => {
    filterCharactersList(e.target.value, document.getElementById('character-filter').value);
});

document.getElementById('character-filter')?.addEventListener('change', (e) => {
    filterCharactersList(document.getElementById('character-search').value, e.target.value);
});

document.getElementById('manage-rules-btn')?.addEventListener('click', () => {
    const panel = document.getElementById('rules-management');
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
        startRulesAutoRefresh();
        listRules(); // Load immediately
    } else {
        panel.style.display = 'none';
        stopRulesAutoRefresh();
    }
});

// LLM Services Chat (Slack-like interface)
let currentLLMService = 'rules_engine'; // Default channel

// Service configuration
const LLM_SERVICES = {
    rules_engine: {
        name: "Ma'at (Rules Engine)",
        icon: "⚖️",
        url: RULES_ENGINE_URL + '/query',
        color: '#10b981'
    },
    game_master: {
        name: "Thoth (Game Master)",
        icon: "📜",
        url: GM_URL + '/query',
        color: '#f59e0b'
    },
    being: {
        name: "Atman (Being Service)",
        icon: "🧠",
        url: BEING_URL + '/query',
        color: '#8b5cf6'
    },
    worlds: {
        name: "Gaia (Worlds Service)",
        icon: "🌍",
        url: WORLDS_URL + '/query',
        color: '#06b6d4'
    }
};

// Load conversation history from localStorage
function loadLLMConversationHistory(service) {
    const key = `llm_chat_${service}`;
    const history = localStorage.getItem(key);
    return history ? JSON.parse(history) : [];
}

// Save conversation history to localStorage
function saveLLMConversationHistory(service, history) {
    const key = `llm_chat_${service}`;
    localStorage.setItem(key, JSON.stringify(history));
}

// Add message to conversation history
function addLLMMessage(service, role, content, metadata = {}) {
    const history = loadLLMConversationHistory(service);
    history.push({
        role: role, // 'user' or 'assistant'
        content: content,
        timestamp: new Date().toISOString(),
        metadata: metadata
    });
    // Keep only last 100 messages per service
    if (history.length > 100) {
        history.shift();
    }
    saveLLMConversationHistory(service, history);
    return history;
}

// Render conversation history
function renderLLMConversation(service) {
    const messagesDiv = document.getElementById('llm-chat-messages');
    const history = loadLLMConversationHistory(service);
    
    if (history.length === 0) {
        messagesDiv.innerHTML = `
            <div style="text-align: center; color: #888; padding: 40px 20px;">
                <div style="font-size: 2em; margin-bottom: 8px;">${LLM_SERVICES[service].icon}</div>
                <div style="font-weight: bold; margin-bottom: 4px;">${LLM_SERVICES[service].name}</div>
                <div style="font-size: 0.85em;">Start a conversation by sending a message below</div>
            </div>
        `;
        return;
    }
    
    messagesDiv.innerHTML = history.map(msg => {
        const isUser = msg.role === 'user';
        const timestamp = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        return `
            <div style="display: flex; gap: 12px; ${isUser ? 'flex-direction: row-reverse;' : ''}">
                <div style="flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%; background: ${isUser ? '#4a9eff' : LLM_SERVICES[service].color}; display: flex; align-items: center; justify-content: center; font-size: 1.2em;">
                    ${isUser ? '👤' : LLM_SERVICES[service].icon}
                </div>
                <div style="flex: 1; ${isUser ? 'text-align: right;' : ''}">
                    <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px; ${isUser ? 'justify-content: flex-end;' : ''}">
                        <span style="font-weight: bold; color: ${isUser ? '#4a9eff' : LLM_SERVICES[service].color}; font-size: 0.9em;">
                            ${isUser ? 'You' : LLM_SERVICES[service].name.split(' ')[0]}
                        </span>
                        <span style="font-size: 0.75em; color: #888;">${timestamp}</span>
                    </div>
                    <div style="background: ${isUser ? '#4a9eff20' : '#2a2a2a'}; padding: 10px 12px; border-radius: 8px; color: #e0e0e0; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word;">
                        ${escapeHTML(msg.content).replace(/\n/g, '<br>')}
                    </div>
                    ${!isUser ? `
                        <div style="margin-top: 6px; display: flex; gap: 6px; align-items: center;">
                            <button class="save-prompt-btn" data-service="${service}" data-content="${escapeHTML(msg.content).replace(/"/g, '&quot;').replace(/\n/g, '\\n')}" style="padding: 4px 8px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em; display: flex; align-items: center; gap: 4px;">
                                <span>💾</span>
                                <span>Save as Prompt</span>
                            </button>
                        </div>
                    ` : ''}
                    ${msg.metadata && msg.metadata.rules_found !== undefined ? `
                        <div style="font-size: 0.75em; color: #888; margin-top: 4px; ${isUser ? 'text-align: right;' : ''}">
                            Rules found: ${msg.metadata.rules_found}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
    
    // Add event listeners to "Save as Prompt" buttons
    messagesDiv.querySelectorAll('.save-prompt-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const service = btn.dataset.service;
            const content = btn.dataset.content.replace(/\\n/g, '\n');
            saveMessageAsPrompt(service, content);
        });
    });
    
    // Setup text selection handler for "Save Selection as Prompt"
    setupTextSelectionHandler(messagesDiv, service);
    
    // Auto-scroll to bottom
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Switch to a different LLM service channel
async function switchLLMChannel(service) {
    currentLLMService = service;
    const serviceConfig = LLM_SERVICES[service];
    
    // Remove any typing indicators (from any channel)
    document.querySelectorAll('[id^="llm-typing-indicator-"]').forEach(indicator => {
        indicator.remove();
    });
    
    // Update header
    document.getElementById('llm-chat-service-icon').textContent = serviceConfig.icon;
    document.getElementById('llm-chat-service-name').textContent = serviceConfig.name;
    
    // Update input placeholder
    document.getElementById('llm-chat-input').placeholder = `Message ${serviceConfig.name.split(' ')[0]}...`;
    
    // Update active channel in sidebar
    document.querySelectorAll('.llm-channel-item').forEach(item => {
        if (item.dataset.service === service) {
            item.style.background = '#3a3a3a';
            item.style.borderLeft = `3px solid ${serviceConfig.color}`;
        } else {
            item.style.background = '#2a2a2a';
            item.style.borderLeft = 'none';
        }
    });
    
    // Render conversation history
    renderLLMConversation(service);
}

// Submit message to LLM service
window.submitLLMMessage = async function() {
    const input = document.getElementById('llm-chat-input');
    const message = input.value.trim();
    
    if (!message) {
        return;
    }
    
    // CRITICAL: Capture the service at request time to prevent race conditions
    // If user switches channels while request is in flight, we still use the original service
    const requestService = currentLLMService;
    const serviceConfig = LLM_SERVICES[requestService];
    
    // Clear input
    input.value = '';
    
    // Add user message to history and render
    addLLMMessage(requestService, 'user', message);
    // Only render if this is still the active channel
    if (currentLLMService === requestService) {
        renderLLMConversation(requestService);
    }
    
    // Show typing indicator (only if this is still the active channel)
    let typingIndicator = null;
    if (currentLLMService === requestService) {
        const messagesDiv = document.getElementById('llm-chat-messages');
        typingIndicator = document.createElement('div');
        typingIndicator.id = `llm-typing-indicator-${requestService}`;
        typingIndicator.style.cssText = 'display: flex; gap: 12px;';
        typingIndicator.innerHTML = `
            <div style="flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%; background: ${serviceConfig.color}; display: flex; align-items: center; justify-content: center; font-size: 1.2em;">
                ${serviceConfig.icon}
            </div>
            <div style="flex: 1;">
                <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 4px;">
                    <span style="font-weight: bold; color: ${serviceConfig.color}; font-size: 0.9em;">
                        ${serviceConfig.name.split(' ')[0]}
                    </span>
                    <span style="font-size: 0.75em; color: #888;">typing...</span>
                </div>
                <div style="background: #2a2a2a; padding: 10px 12px; border-radius: 8px; color: #888;">
                    <span style="animation: blink 1s infinite;">●</span>
                </div>
            </div>
        `;
        messagesDiv.appendChild(typingIndicator);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
    
    try {
        const token = authToken || localStorage.getItem('authToken');
        
        const response = await fetch(serviceConfig.url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                query: message
            })
        });
        
        // Remove typing indicator if it exists and is still visible
        if (typingIndicator && typingIndicator.parentNode) {
            typingIndicator.remove();
        }
        
        if (response.ok) {
            const result = await response.json();
            
            if (result.error) {
                // Always save to the correct service's history
                addLLMMessage(requestService, 'assistant', `Error: ${result.error}`, { error: true });
            } else {
                const responseText = result.response || 'No response received';
                // Always save to the correct service's history
                addLLMMessage(requestService, 'assistant', responseText, {
                    rules_found: result.rules_found,
                    metadata: result.metadata
                });
            }
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to process query';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            // Always save to the correct service's history
            addLLMMessage(requestService, 'assistant', `Error: ${errorMessage}`, { error: true });
        }
        
        // Only re-render if this response is for the currently active channel
        // This prevents responses from appearing in the wrong channel
        if (currentLLMService === requestService) {
            renderLLMConversation(requestService);
        } else {
            // If user switched channels, update the channel indicator if needed
            // (optional: could show a badge indicating new messages in other channels)
        }
    } catch (error) {
        // Remove typing indicator if it exists
        if (typingIndicator && typingIndicator.parentNode) {
            typingIndicator.remove();
        }
        // Always save to the correct service's history
        addLLMMessage(requestService, 'assistant', `Error: ${error.message}`, { error: true });
        // Only render if this is still the active channel
        if (currentLLMService === requestService) {
            renderLLMConversation(requestService);
        }
    }
};

// LLM Services are now integrated into being chat - no separate panel needed

// System Prompts Management
document.getElementById('system-prompts-btn')?.addEventListener('click', () => {
    const panel = document.getElementById('system-prompts-panel');
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
        loadPrompts();
    } else {
        panel.style.display = 'none';
    }
});

document.getElementById('refresh-prompts-btn')?.addEventListener('click', () => {
    loadPrompts();
});

document.getElementById('prompt-service-select')?.addEventListener('change', () => {
    loadPrompts();
});

document.getElementById('create-prompt-btn')?.addEventListener('click', () => {
    showCreatePromptModal();
});

// Channel switching
document.querySelectorAll('.llm-channel-item').forEach(item => {
    item.addEventListener('click', () => {
        switchLLMChannel(item.dataset.service);
    });
});

// Enter key to send (Shift+Enter for new line)
document.getElementById('llm-chat-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitLLMMessage();
    }
});

document.getElementById('upload-rules-btn')?.addEventListener('click', () => {
    // Defer async work to prevent blocking
    setTimeout(async () => {
        const fileInput = document.getElementById('rules-file-input');
        const file = fileInput.files[0];
        
        if (!file) {
            await customConfirm('Please select a rules file first.', 'No File Selected');
            return;
        }
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch(`${RULES_ENGINE_URL}/rules/upload`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${authToken}`
                },
                body: formData
            });
            
            if (response.ok) {
                const result = await response.json();
                addSystemMessage(`Rules uploaded successfully: ${result.filename}`);
                fileInput.value = '';
                await listRules();
                // Start polling for progress immediately if file needs indexing
                if (result.file_id && (result.category === 'text' || result.category === 'document')) {
                    setTimeout(() => {
                        startIndexingProgressPoll(result.file_id);
                    }, 500);
                }
            } else {
                const error = await response.text();
                addSystemMessage(`Failed to upload rules: ${error}`, 'error');
            }
        } catch (error) {
            console.error('Error uploading rules:', error);
            addSystemMessage(`Error uploading rules: ${error.message}`, 'error');
        }
    }, 0);
});

document.getElementById('list-rules-btn')?.addEventListener('click', async () => {
    await listRules();
});

// Auto-refresh rules list every 5 seconds when rules management panel is visible
let rulesAutoRefreshInterval = null;

function startRulesAutoRefresh() {
    if (rulesAutoRefreshInterval) {
        return; // Already running
    }
    rulesAutoRefreshInterval = setInterval(async () => {
        const rulesPanel = document.getElementById('rules-management');
        if (rulesPanel && rulesPanel.style.display !== 'none') {
            await listRules();
        } else {
            // Panel is hidden, stop auto-refresh
            stopRulesAutoRefresh();
        }
    }, 5000); // Refresh every 5 seconds
}

function stopRulesAutoRefresh() {
    if (rulesAutoRefreshInterval) {
        clearInterval(rulesAutoRefreshInterval);
        rulesAutoRefreshInterval = null;
    }
}

// Track active polling intervals for indexing progress
const indexingProgressPollers = new Map();

// Indexing progress polling functions
function startIndexingProgressPoll(fileId) {
    if (indexingProgressPollers.has(fileId)) {
        return; // Already polling
    }
    
    const pollInterval = setInterval(async () => {
        try {
            const token = authToken || localStorage.getItem('authToken');
            const response = await fetch(`${RULES_ENGINE_URL}/rules/${fileId}/indexing-progress`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (response.ok) {
                const progressData = await response.json();
                // #region agent log
                fetch('http://127.0.0.1:7242/ingest/a72a0cbe-2d6f-4267-8f50-7b71184c1dc8',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'app.js:startIndexingProgressPoll',message:'Progress poll response',data:{fileId,status:progressData.indexing_status,progress:progressData.indexing_progress,percentage:progressData.indexing_progress?.percentage},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
                // #endregion
                
                // Update the rule in the list if still indexing or pending
                if (progressData.indexing_status === 'indexing' || progressData.indexing_status === 'pending') {
                    // Trigger a refresh of the rules list to show updated progress
                    listRules();
                } else {
                    // Stop polling when indexing is complete or failed
                    stopIndexingProgressPoll(fileId);
                    listRules(); // Refresh to show final status
                }
            } else if (response.status === 404) {
                // File not found (likely deleted), stop polling
                stopIndexingProgressPoll(fileId);
                return; // Exit early, don't continue polling
            } else {
                // Other error, continue polling but less frequently
                console.warn('Error polling indexing progress:', response.status);
            }
        } catch (error) {
            console.error('Error polling indexing progress:', error);
            // Don't stop polling on network errors, they might be temporary
        }
    }, 1000); // Poll every second
    
    indexingProgressPollers.set(fileId, pollInterval);
}

function stopIndexingProgressPoll(fileId) {
    const pollInterval = indexingProgressPollers.get(fileId);
    if (pollInterval) {
        clearInterval(pollInterval);
        indexingProgressPollers.delete(fileId);
    }
}

// Track which error details are expanded
const expandedErrorDetails = new Set();

async function listRules() {
    try {
        // Before refreshing, save which details are currently open
        const rulesList = document.getElementById('rules-list');
        if (rulesList) {
            const openDetails = rulesList.querySelectorAll('details[open]');
            expandedErrorDetails.clear();
            openDetails.forEach(details => {
                const errorId = details.closest('[data-file-id]')?.getAttribute('data-file-id');
                if (errorId) {
                    expandedErrorDetails.add(errorId);
                }
            });
        }
        
        const token = authToken || localStorage.getItem('authToken');
        const response = await fetch(`${RULES_ENGINE_URL}/rules/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.rules && data.rules.length > 0) {
                rulesList.innerHTML = data.rules.map(rule => {
                    // Start polling for progress if file is indexing
                    if (rule.indexed_status === 'indexing' && !indexingProgressPollers.has(rule.file_id)) {
                        startIndexingProgressPoll(rule.file_id);
                    } else if (rule.indexed_status !== 'indexing' && indexingProgressPollers.has(rule.file_id)) {
                        stopIndexingProgressPoll(rule.file_id);
                    }
                    
                    // Also start polling for pending files that should be indexed
                    if ((rule.indexed_status === 'pending' || !rule.indexed_status) && 
                        (rule.is_text || rule.is_pdf || rule.is_epub) && 
                        !indexingProgressPollers.has(rule.file_id)) {
                        // Check if indexing should have started - poll briefly to catch status change
                        setTimeout(() => {
                            if (!indexingProgressPollers.has(rule.file_id)) {
                                startIndexingProgressPoll(rule.file_id);
                            }
                        }, 1000);
                    }
                    const sizeKB = ((rule.size || 0) / 1024).toFixed(1);
                    const category = rule.category || 'unknown';
                    const categoryIcon = category === 'image' ? '🖼️' : category === 'document' ? (rule.is_epub ? '📚' : '📄') : '📝';
                    const categoryColor = category === 'image' ? '#4a9eff' : category === 'document' ? '#f59e0b' : '#10b981';
                    
                    // Indexing status indicator
                    const indexingStatus = rule.indexing_status || 'pending';
                    let statusBadge = '';
                    if (rule.is_text || rule.is_document || rule.is_pdf || rule.is_epub) {
                        let statusColor = '#888';
                        let statusText = 'Pending';
                        let statusIcon = '⏳';
                        
                        if (indexingStatus === 'indexing') {
                            statusColor = '#f59e0b';
                            // Show progress if available
                            const progress = rule.indexing_progress || {};
                            const percentage = progress.percentage || 0;
                            const stage = progress.stage || 'indexing';
                            const stageLabels = {
                                'starting': 'Starting...',
                                'extracting': 'Extracting content from file...',
                                'chunking': 'Chunking content (respecting paragraphs)...',
                                'generating_embeddings': 'Generating embeddings (this may take a while)...',
                                'preparing_data': 'Preparing data for storage...',
                                'storing': 'Storing in database...',
                                'complete': 'Complete',
                                'error': 'Error'
                            };
                            const stageLabel = stageLabels[stage] || 'Indexing...';
                            statusText = `${stageLabel} ${percentage}%`;
                            statusIcon = '🔄';
                        } else if (indexingStatus === 'indexed') {
                            statusColor = '#10b981';
                            statusText = 'Indexed';
                            statusIcon = '✅';
                        } else if (indexingStatus === 'failed') {
                            statusColor = '#ef4444';
                            statusText = 'Indexing Failed';
                            statusIcon = '❌';
                        } else {
                            statusText = 'Pending Indexing';
                        }
                        
                        if (indexingStatus === 'indexing' && rule.indexing_progress) {
                            // Show progress bar for indexing
                            const progress = rule.indexing_progress;
                            const percentage = progress.percentage || 0;
                            statusBadge = `
                                <div style="margin-left: 10px; display: inline-block;">
                                    <span style="color: ${statusColor}; font-size: 0.85em; font-weight: bold;">${statusIcon} ${statusText}</span>
                                    <div style="width: 200px; height: 6px; background: #2a2a2a; border-radius: 3px; margin-top: 4px; overflow: hidden;">
                                        <div style="width: ${percentage}%; height: 100%; background: linear-gradient(90deg, #f59e0b, #fbbf24); transition: width 0.3s;"></div>
                                    </div>
                                </div>
                            `;
                        } else {
                            statusBadge = `<span style="color: ${statusColor}; margin-left: 10px; font-size: 0.85em; font-weight: bold;">${statusIcon} ${statusText}</span>`;
                        }
                        if (rule.indexed_at) {
                            statusBadge += `<span style="color: #666; margin-left: 5px; font-size: 0.75em;">(${new Date(rule.indexed_at).toLocaleString()})</span>`;
                        }
                        if (indexingStatus === 'failed' && rule.indexing_error) {
                            // Format error message better
                            let errorMsg = rule.indexing_error;
                            let errorType = 'Error';
                            let errorColor = '#ef4444';
                            
                            // Categorize errors
                            if (errorMsg.includes('429') || errorMsg.includes('quota') || errorMsg.includes('exceeded')) {
                                errorType = '⚠️ Quota Exceeded';
                                errorMsg = 'API quota exceeded. Please check your billing and plan limits.';
                            } else if (errorMsg.includes('401') || errorMsg.includes('unauthorized') || errorMsg.includes('credentials')) {
                                errorType = '🔐 Authentication Error';
                                errorMsg = 'Authentication failed. Please check your API credentials.';
                            } else if (errorMsg.includes('404') || errorMsg.includes('not found')) {
                                errorType = '📁 File Not Found';
                                errorMsg = 'File or resource not found.';
                            } else if (errorMsg.includes('timeout') || errorMsg.includes('timed out')) {
                                errorType = '⏱️ Timeout';
                                errorMsg = 'Request timed out. Please try again.';
                            }
                            
                            // Show full error in a collapsible section
                            const errorId = rule.file_id;
                            const shouldBeOpen = expandedErrorDetails.has(errorId);
                            statusBadge += `
                                <div style="margin-top: 8px; padding: 8px; background: #2a1a1a; border-left: 3px solid ${errorColor}; border-radius: 4px;">
                                    <div style="color: ${errorColor}; font-weight: bold; font-size: 0.85em; margin-bottom: 4px;">
                                        ${errorType}
                                    </div>
                                    <div style="color: #e0e0e0; font-size: 0.8em; margin-bottom: 6px;">
                                        ${errorMsg}
                                    </div>
                                    <details ${shouldBeOpen ? 'open' : ''} style="margin-top: 4px;">
                                        <summary style="color: #888; font-size: 0.75em; cursor: pointer; user-select: none;">Show technical details</summary>
                                        <pre style="color: #aaa; font-size: 0.7em; margin-top: 4px; white-space: pre-wrap; word-break: break-word; max-height: 100px; overflow-y: auto;">${rule.indexing_error.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
                                    </details>
                                    <button onclick="retryIndexing('${rule.file_id}')" style="margin-top: 6px; padding: 4px 12px; background: #f59e0b; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em; font-weight: bold;">🔄 Retry Indexing</button>
                                </div>
                            `;
                        }
                    }
                    
                    // Add validate button for indexed files (GM only - will be checked server-side)
                    let validateButton = '';
                    if (indexingStatus === 'indexed' && (rule.is_text || rule.is_document || rule.is_pdf || rule.is_epub)) {
                        validateButton = `<button onclick="validateIndexing('${rule.file_id}')" style="margin-left: 8px; padding: 4px 12px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em; font-weight: bold;" title="Test if file is actually searchable in the index (GM only)">✓ Validate</button>`;
                    }
                    
                    // Show associations badges
                    const gameSystemBadge = rule.game_system 
                        ? `<span style="background: #8b5cf6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 6px;">Game: ${escapeHTML(rule.game_system)}</span>`
                        : '';
                    const sessionBadge = rule.session_ids && rule.session_ids.length > 0
                        ? `<span style="background: #f59e0b; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 6px;">Sessions: ${rule.session_ids.length}</span>`
                        : rule.game_system || (rule.session_ids && rule.session_ids.length > 0) ? '' : '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 6px;">Global</span>';
                    
                    return `
                        <div data-file-id="${rule.file_id}" style="padding: 10px; margin-bottom: 8px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid ${categoryColor};">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div style="flex: 1;">
                                    <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-bottom: 4px;">
                                        <strong style="color: ${categoryColor};">${categoryIcon} ${escapeHTML(rule.filename || rule.original_filename)}</strong>
                                        <span style="color: #888; font-size: 0.9em;">${sizeKB} KB</span>
                                        <span style="color: #666; font-size: 0.85em;">(${category})</span>
                                        ${gameSystemBadge}
                                        ${sessionBadge}
                                    </div>
                                    ${statusBadge}
                                    ${validateButton}
                                </div>
                                <div style="display: flex; gap: 4px; flex-shrink: 0;">
                                    <button onclick="manageRuleAssociations('${rule.file_id}')" style="padding: 4px 8px; background: #ec4899; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;" title="Manage game system and session associations (GM only)">Associations</button>
                                    ${rule.is_text ? `<button onclick="viewRule('${rule.file_id}')" style="padding: 4px 8px; background: #666; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">View</button>` : ''}
                                    <button onclick="downloadRule('${rule.file_id}')" style="padding: 4px 8px; background: #4a9eff; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Download</button>
                                    <button onclick="deleteRule('${rule.file_id}')" style="padding: 4px 8px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Delete</button>
                                </div>
                            </div>
                            ${rule.is_image ? `<div style="margin-top: 8px;"><img src="${RULES_ENGINE_URL}/rules/${rule.file_id}" style="max-width: 100%; max-height: 200px; border-radius: 4px;" alt="${rule.filename}"></div>` : ''}
                            <div style="color: #888; font-size: 0.8em; margin-top: 5px;">Uploaded: ${new Date(rule.uploaded_at).toLocaleString()}</div>
                        </div>
                    `;
                }).join('');
                
                // After rendering, restore expanded state for details elements
                setTimeout(() => {
                    expandedErrorDetails.forEach(fileId => {
                        const fileElement = rulesList.querySelector(`[data-file-id="${fileId}"]`);
                        if (fileElement) {
                            const details = fileElement.querySelector('details');
                            if (details) {
                                details.open = true;
                            }
                        }
                    });
                }, 0);
            } else {
                rulesList.innerHTML = '<div style="color: #888; padding: 10px;">No files uploaded yet.</div>';
            }
        }
    } catch (error) {
        console.error('Error listing rules:', error);
    }
}

// View rule (for text files)
window.viewRule = async function(fileId) {
    try {
        const response = await fetch(`${RULES_ENGINE_URL}/rules/${fileId}`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const content = data.content || '';
            const filename = data.metadata?.filename || 'Unknown';
            
            // Show in a modal or new window
            const modal = document.createElement('div');
            modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 1000; display: flex; align-items: center; justify-content: center;';
            modal.innerHTML = `
                <div style="background: #1a1a1a; padding: 20px; border-radius: 8px; max-width: 80%; max-height: 80%; overflow: auto; position: relative;">
                    <button onclick="this.parentElement.parentElement.remove()" style="position: absolute; top: 10px; right: 10px; background: #ef4444; color: white; border: none; border-radius: 4px; padding: 5px 10px; cursor: pointer;">Close</button>
                    <h3 style="margin-top: 0;">${filename}</h3>
                    <pre style="background: #0a0a0a; padding: 15px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;">${content.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
                </div>
            `;
            document.body.appendChild(modal);
        }
    } catch (error) {
        console.error('Error viewing rule:', error);
        alert('Error viewing file: ' + error.message);
    }
};

// Download rule
window.downloadRule = async function(fileId) {
    try {
        const url = `${RULES_ENGINE_URL}/rules/${fileId}/download`;
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = fileId;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        } else {
            alert('Failed to download file');
        }
    } catch (error) {
        console.error('Error downloading rule:', error);
        alert('Error downloading file: ' + error.message);
    }
};

// Validate indexing for an indexed file
window.validateIndexing = async function(fileId) {
    try {
        const token = authToken || localStorage.getItem('authToken');
        addSystemMessage('Validating indexing...', 'info');
        
        const response = await fetch(`${RULES_ENGINE_URL}/rules/${fileId}/validate-indexing`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            
            if (result.valid) {
                let message = `✅ Indexing validation passed!\n\n`;
                message += `File content found in search index.\n`;
                message += `Test query: "${result.test_query || 'N/A'}"\n`;
                message += `Chunks found: ${result.chunks_found || 0}\n`;
                message += `Total search results: ${result.search_results_count || 0}`;
                await customConfirm(message, 'Validation Successful');
            } else {
                let message = `❌ Indexing validation failed!\n\n`;
                message += `Reason: ${result.reason || 'Unknown error'}\n`;
                if (result.test_query) {
                    message += `Test query: "${result.test_query}"\n`;
                }
                if (result.search_results_count !== undefined) {
                    message += `Search results: ${result.search_results_count}`;
                }
                await customConfirm(message, 'Validation Failed');
            }
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to validate indexing';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            addSystemMessage(`Validation error: ${errorMessage}`, 'error');
        }
    } catch (error) {
        console.error('Error validating indexing:', error);
        addSystemMessage(`Error validating indexing: ${error.message}`, 'error');
    }
};

// Retry indexing for a failed file
window.retryIndexing = async function(fileId) {
    const confirmed = await customConfirm('Retry indexing for this file? This will attempt to index the file again.', 'Retry Indexing');
    if (!confirmed) {
        return;
    }
    
    try {
        const token = authToken || localStorage.getItem('authToken');
        const response = await fetch(`${RULES_ENGINE_URL}/rules/${fileId}/retry-indexing`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            addSystemMessage('Indexing retry initiated! The file will be re-indexed in the background.');
            // Refresh the list to show updated status
            await listRules();
            // Start polling for progress
            setTimeout(() => {
                startIndexingProgressPoll(fileId);
            }, 500);
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to retry indexing';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            alert(errorMessage);
        }
    } catch (error) {
        console.error('Error retrying indexing:', error);
        alert('Error retrying indexing: ' + error.message);
    }
};

// Delete rule
window.deleteRule = async function(fileId) {
    const confirmed = await customConfirm(
        'Are you sure you want to delete this file?\n\nThis will permanently remove the file from:\n- Disk storage\n- Search index\n- System metadata',
        'Delete File'
    );
    if (!confirmed) {
        return;
    }
    
    try {
        // Stop any active polling for this file before deletion
        stopIndexingProgressPoll(fileId);
        
        const token = authToken || localStorage.getItem('authToken');
        const response = await fetch(`${RULES_ENGINE_URL}/rules/${fileId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            const deletedFrom = result.deleted_from || [];
            // Ensure polling is stopped (in case it wasn't already)
            stopIndexingProgressPoll(fileId);
            alert(`File deleted successfully!\n\nRemoved from: ${deletedFrom.join(', ')}`);
            await listRules();
        } else {
            const errorText = await response.text();
            let errorMessage = 'Failed to delete file';
            try {
                const errorJson = JSON.parse(errorText);
                errorMessage = errorJson.detail || errorMessage;
            } catch {
                errorMessage = errorText || errorMessage;
            }
            alert(errorMessage);
        }
    } catch (error) {
        console.error('Error deleting rule:', error);
        alert('Error deleting file: ' + error.message);
    }
};

// Initialize session on page load
async function initializeSession() {
    // Check if we have a stored token
    const storedToken = localStorage.getItem('authToken');
    const storedUsername = localStorage.getItem('username');
    
    if (!storedToken) {
        // No token, show login form
        return;
    }
    
    // Validate token by checking user info
    try {
        const response = await fetch(`${AUTH_URL}/me`, {
            headers: { 'Authorization': `Bearer ${storedToken}` }
        });
        
        if (response.ok) {
            // Token is valid, restore session
            authToken = storedToken;
            const user = await response.json();
            
            // Update UI to show logged-in state
            if (storedUsername) {
                document.getElementById('username-display').textContent = storedUsername;
            } else {
                document.getElementById('username-display').textContent = user.username;
            }
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('user-info').style.display = 'block';
            document.getElementById('game-section').style.display = 'block';
            
            // Load user info to show role and enable GM features
            await loadUserInfo();
            
            // Connect WebSockets
            connectWebSockets();
            
            // Load initial game state
            await loadGameState();
            
            // Start auto-refresh for sessions
            startSessionsAutoRefresh();
            
            // Setup system messages toggle
            setupSystemMessagesToggle();
        } else {
            // Token is invalid, clear it and show login form
            console.log('Stored token is invalid, clearing session');
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            authToken = null;
            stopSessionsAutoRefresh();
        }
    } catch (error) {
        console.error('Error validating stored token:', error);
        // On error, clear token and show login form
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        authToken = null;
    }
}

// Initialize session when page loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        initializeSession();
        setupSystemMessagesToggle();
        // Display version number (build timestamp)
        const versionDisplay = document.getElementById('version-display');
        if (versionDisplay) {
            const version = SYSTEM_VERSION === 'dev' ? 'dev' : `build-${SYSTEM_VERSION}`;
            versionDisplay.textContent = version;
            versionDisplay.title = `Build time: ${SYSTEM_VERSION === 'dev' ? 'Development mode' : SYSTEM_VERSION.replace(/-/g, ' ')}`;
        }
    });
} else {
    // DOM is already loaded
    initializeSession();
    setupSystemMessagesToggle();
    // Display version number (build timestamp)
    const versionDisplay = document.getElementById('version-display');
    if (versionDisplay) {
        const version = SYSTEM_VERSION === 'dev' ? 'dev' : `build-${SYSTEM_VERSION}`;
        versionDisplay.textContent = version;
        versionDisplay.title = `Build time: ${SYSTEM_VERSION === 'dev' ? 'Development mode' : SYSTEM_VERSION.replace(/-/g, ' ')}`;
    }
}

// Character creation
document.getElementById('create-character-btn')?.addEventListener('click', () => {
    const panel = document.getElementById('character-creation');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
});

document.getElementById('cancel-character-btn')?.addEventListener('click', () => {
    document.getElementById('character-creation').style.display = 'none';
    // Clear form
    document.getElementById('character-name').value = '';
    document.getElementById('character-backstory').value = '';
    document.getElementById('character-personality').value = '';
    document.getElementById('character-appearance').value = '';
    document.getElementById('auto-generate-character').checked = false;
});

document.getElementById('submit-character-btn')?.addEventListener('click', async () => {
    const name = document.getElementById('character-name').value;
    const autoGenerate = document.getElementById('auto-generate-character').checked;
    
    if (!autoGenerate && !name) {
        alert('Please enter a character name or enable auto-generation');
        return;
    }
    
    try {
        const requestData = {
            name: name || '',
            backstory: document.getElementById('character-backstory').value || null,
            personality: document.getElementById('character-personality').value || null,
            appearance: document.getElementById('character-appearance').value || null,
            session_id: window.currentSession?.session_id || null,
            automatic: autoGenerate
        };
        
        const response = await fetch(`${BEING_REGISTRY_URL}/beings/create`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Hide character creation panel
            document.getElementById('character-creation').style.display = 'none';
            
            // Clear form
            document.getElementById('character-name').value = '';
            document.getElementById('character-backstory').value = '';
            document.getElementById('character-personality').value = '';
            document.getElementById('character-appearance').value = '';
            document.getElementById('auto-generate-character').checked = false;
            
            // Reload characters
            await loadUserCharacters();
            
            // Reload all beings list for GM
            loadAllBeings();
            
            // Show character record viewer
            showCharacterRecord(result);
            
            // Character creation is a system action, not narrative
            console.log(`Character "${name || 'Auto-generated'}" created successfully!`);
        } else {
            const error = await response.text();
            alert('Failed to create character: ' + error);
        }
    } catch (error) {
        console.error('Error creating character:', error);
        alert('Error creating character: ' + error.message);
    }
});

// Character Record Viewer
function showCharacterRecord(characterData) {
    const overlay = document.getElementById('character-record-overlay');
    const content = document.getElementById('character-record-content');
    
    if (!overlay || !content) return;
    
    const charData = characterData.character_data || {};
    const flavor = charData.flavor || {};
    const mechanics = charData.mechanics || {};
    const registry = characterData.registry || {};
    
    // Build HTML for character record
    let html = '<div style="display: flex; flex-direction: column; gap: 16px;">';
    
    // Basic Info
    html += '<div style="background: #1a1a1a; padding: 12px; border-radius: 4px; border-left: 3px solid #4a9eff;">';
    html += '<h3 style="margin: 0 0 8px 0; color: #4a9eff; font-size: 1.1em;">Basic Information</h3>';
    html += `<div style="display: grid; grid-template-columns: 120px 1fr; gap: 8px; font-size: 0.9em;">`;
    html += `<div style="color: #888;">Name:</div><div>${escapeHTML(flavor.name || registry.name || 'Unknown')}</div>`;
    html += `<div style="color: #888;">Being ID:</div><div style="font-family: monospace; font-size: 0.85em; color: #888;">${escapeHTML(characterData.being_id)}</div>`;
    html += `<div style="color: #888;">Owner ID:</div><div style="font-family: monospace; font-size: 0.85em; color: #888;">${escapeHTML(registry.owner_id || 'Unknown')}</div>`;
    if (registry.session_id) {
        html += `<div style="color: #888;">Session:</div><div style="font-family: monospace; font-size: 0.85em; color: #888;">${escapeHTML(registry.session_id)}</div>`;
    }
    html += `</div></div>`;
    
    // Flavor Information
    if (flavor.backstory || flavor.personality || flavor.appearance) {
        html += '<div style="background: #1a1a1a; padding: 12px; border-radius: 4px; border-left: 3px solid #10b981;">';
        html += '<h3 style="margin: 0 0 8px 0; color: #10b981; font-size: 1.1em;">Character Flavor</h3>';
        if (flavor.backstory) {
            html += `<div style="margin-bottom: 8px;"><strong style="color: #888; font-size: 0.85em;">Backstory:</strong><div style="margin-top: 4px; white-space: pre-wrap; line-height: 1.5;">${escapeHTML(flavor.backstory)}</div></div>`;
        }
        if (flavor.personality) {
            html += `<div style="margin-bottom: 8px;"><strong style="color: #888; font-size: 0.85em;">Personality:</strong><div style="margin-top: 4px; white-space: pre-wrap; line-height: 1.5;">${escapeHTML(flavor.personality)}</div></div>`;
        }
        if (flavor.appearance) {
            html += `<div><strong style="color: #888; font-size: 0.85em;">Appearance:</strong><div style="margin-top: 4px; white-space: pre-wrap; line-height: 1.5;">${escapeHTML(flavor.appearance)}</div></div>`;
        }
        html += '</div>';
    }
    
    // Mechanics
    if (mechanics.stats || mechanics.skills || mechanics.abilities) {
        html += '<div style="background: #1a1a1a; padding: 12px; border-radius: 4px; border-left: 3px solid #8b5cf6;">';
        html += '<h3 style="margin: 0 0 8px 0; color: #8b5cf6; font-size: 1.1em;">Mechanics</h3>';
        if (mechanics.game_system) {
            html += `<div style="margin-bottom: 8px; font-size: 0.9em;"><strong style="color: #888;">Game System:</strong> ${escapeHTML(mechanics.game_system)}</div>`;
        }
        if (mechanics.stats && Object.keys(mechanics.stats).length > 0) {
            html += '<div style="margin-bottom: 8px;"><strong style="color: #888; font-size: 0.85em;">Stats:</strong><div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 8px;">';
            for (const [stat, value] of Object.entries(mechanics.stats)) {
                html += `<span style="background: #2a2a2a; padding: 4px 8px; border-radius: 3px; font-size: 0.85em;"><strong>${escapeHTML(stat)}:</strong> ${escapeHTML(String(value))}</span>`;
            }
            html += '</div></div>';
        }
        if (mechanics.skills && Object.keys(mechanics.skills).length > 0) {
            html += '<div style="margin-bottom: 8px;"><strong style="color: #888; font-size: 0.85em;">Skills:</strong><div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 8px;">';
            for (const [skill, value] of Object.entries(mechanics.skills)) {
                html += `<span style="background: #2a2a2a; padding: 4px 8px; border-radius: 3px; font-size: 0.85em;"><strong>${escapeHTML(skill)}:</strong> ${escapeHTML(String(value))}</span>`;
            }
            html += '</div></div>';
        }
        if (mechanics.abilities && Object.keys(mechanics.abilities).length > 0) {
            html += '<div><strong style="color: #888; font-size: 0.85em;">Abilities:</strong><div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 8px;">';
            for (const [ability, value] of Object.entries(mechanics.abilities)) {
                html += `<span style="background: #2a2a2a; padding: 4px 8px; border-radius: 3px; font-size: 0.85em;"><strong>${escapeHTML(ability)}:</strong> ${escapeHTML(String(value))}</span>`;
            }
            html += '</div></div>';
        }
        html += '</div>';
    }
    
    // Rules Validation
    if (charData.rules_validation) {
        const validation = charData.rules_validation;
        const statusColor = validation.status === 'validated' ? '#10b981' : '#f59e0b';
        html += '<div style="background: #1a1a1a; padding: 12px; border-radius: 4px; border-left: 3px solid ' + statusColor + ';">';
        html += '<h3 style="margin: 0 0 8px 0; color: ' + statusColor + '; font-size: 1.1em;">Rules Validation</h3>';
        html += `<div style="font-size: 0.9em;"><strong style="color: #888;">Status:</strong> <span style="color: ${statusColor};">${escapeHTML(validation.status || 'unknown')}</span></div>`;
        if (validation.message) {
            html += `<div style="margin-top: 8px; font-size: 0.9em; color: #bbb; white-space: pre-wrap;">${escapeHTML(validation.message)}</div>`;
        }
        html += '</div>';
    }
    
    // Raw Data (collapsible)
    html += '<div style="background: #1a1a1a; padding: 12px; border-radius: 4px; border-left: 3px solid #666;">';
    html += '<details style="cursor: pointer;"><summary style="color: #888; font-size: 0.9em; margin-bottom: 8px;">Raw Character Data (JSON)</summary>';
    html += `<pre style="background: #0a0a0a; padding: 12px; border-radius: 3px; overflow-x: auto; font-size: 0.8em; color: #888; margin: 0;">${escapeHTML(JSON.stringify(characterData, null, 2))}</pre>`;
    html += '</details></div>';
    
    html += '</div>';
    
    content.innerHTML = html;
    overlay.style.display = 'flex';
    
    // Close button handler
    const closeBtn = document.getElementById('character-record-close');
    if (closeBtn) {
        closeBtn.onclick = () => {
            overlay.style.display = 'none';
        };
    }
    
    // Close on overlay click (outside modal)
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            overlay.style.display = 'none';
        }
    };
}

// Helper function to escape HTML
function escapeHTML(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Character Management Functions
let allCharactersForManagement = [];

async function loadCharactersForManagement() {
    const token = authToken || localStorage.getItem('authToken');
    const currentUser = window.currentUser;
    if (!token) return;
    
    try {
        const charactersList = document.getElementById('characters-list');
        charactersList.innerHTML = '<div style="text-align: center; color: #888; padding: 20px;">Loading characters...</div>';
        
        let characters = [];
        
        if (currentUser && currentUser.role === 'gm') {
            // GM can see all characters
            const response = await fetch(`${AUTH_URL}/beings/list`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                characters = data.characters || [];
            }
        } else {
            // Regular users see their owned and assigned characters
            const ownedResponse = await fetch(`${BEING_REGISTRY_URL}/beings/my-characters`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (ownedResponse.ok) {
                const data = await ownedResponse.json();
                characters = data.characters || [];
            }
        }
        
        allCharactersForManagement = characters;
        renderCharactersList(characters);
    } catch (error) {
        console.error('Error loading characters:', error);
        document.getElementById('characters-list').innerHTML = 
            '<div style="text-align: center; color: #ef4444; padding: 20px;">Error loading characters</div>';
    }
}

function filterCharactersList(searchTerm, filterType) {
    let filtered = [...allCharactersForManagement];
    const currentUser = window.currentUser;
    const currentSession = window.currentSession;
    
    // Apply filter
    if (filterType === 'owned' && currentUser) {
        filtered = filtered.filter(c => c.owner_id === currentUser.user_id);
    } else if (filterType === 'assigned' && currentUser) {
        filtered = filtered.filter(c => {
            const assigned = c.assigned_user_ids || [];
            return assigned.includes(currentUser.user_id);
        });
    } else if (filterType === 'session' && currentSession) {
        filtered = filtered.filter(c => c.session_id === currentSession.session_id);
    }
    
    // Apply search
    if (searchTerm) {
        const searchLower = searchTerm.toLowerCase();
        filtered = filtered.filter(c => {
            const name = (c.name || c.being_id || '').toLowerCase();
            const owner = (c.owner_username || '').toLowerCase();
            const beingId = (c.being_id || '').toLowerCase();
            return name.includes(searchLower) || owner.includes(searchLower) || beingId.includes(searchLower);
        });
    }
    
    renderCharactersList(filtered);
}

function renderCharactersList(characters) {
    const charactersList = document.getElementById('characters-list');
    if (!charactersList) return;
    
    if (characters.length === 0) {
        charactersList.innerHTML = '<div style="text-align: center; color: #888; padding: 40px 20px; font-style: italic;">No characters found</div>';
        return;
    }
    
    const currentUser = window.currentUser;
    const currentSession = window.currentSession;
    
    charactersList.innerHTML = characters.map(char => {
        const isOwner = currentUser && char.owner_id === currentUser.user_id;
        const isAssigned = currentUser && (char.assigned_user_ids || []).includes(currentUser.user_id);
        const isInSession = currentSession && char.session_id === currentSession.session_id;
        const canDelete = isOwner || (currentUser && currentUser.role === 'gm');
        
        const charName = escapeHTML(char.name || `Character ${char.being_id.substring(0, 8)}`);
        const statusBadges = [];
        if (isOwner) statusBadges.push('<span style="color: #10b981; font-size: 0.75em;">Owner</span>');
        if (isAssigned && !isOwner) statusBadges.push('<span style="color: #4a9eff; font-size: 0.75em;">Assigned</span>');
        if (isInSession) statusBadges.push('<span style="color: #f59e0b; font-size: 0.75em;">In Session</span>');
        const statusText = statusBadges.length > 0 ? ' • ' + statusBadges.join(' • ') : '';
        
        const ownerText = char.owner_username ? ` • ${escapeHTML(char.owner_username)}` : '';
        const sessionText = char.session_id ? ` • Session: ${char.session_id.substring(0, 8)}` : ' • No Session';
        
        return `
            <div style="padding: 8px 10px; margin-bottom: 4px; background: #2a2a2a; border-radius: 3px; border-left: 3px solid ${isOwner ? '#10b981' : isAssigned ? '#4a9eff' : '#888'}; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                        <span style="font-size: 1em;">🧠</span>
                        <strong style="color: #e0e0e0; font-size: 0.9em; white-space: nowrap;">${charName}</strong>
                        <span style="font-size: 0.75em; color: #888;">${statusText}${ownerText}${sessionText}</span>
                    </div>
                </div>
                <div style="display: flex; gap: 4px; flex-shrink: 0;">
                    <button onclick="viewCharacterDetails('${char.being_id}')" style="padding: 4px 8px; background: #4a9eff; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em;">View</button>
                    <button onclick="openCharacterChat('${char.being_id}', '${charName}')" style="padding: 4px 8px; background: #8b5cf6; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em;">Chat</button>
                    ${canDelete ? `<button onclick="deleteCharacter('${char.being_id}', '${charName}')" style="padding: 4px 8px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em;">Delete</button>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// Toggle message visibility for players (GM only)
window.toggleMessageVisibility = function(beingId, messageTimestamp, makeVisible) {
    const currentUser = window.currentUser;
    if (!currentUser || currentUser.role !== 'gm') {
        return; // Only GMs can toggle visibility
    }
    
    const history = loadBeingChatHistory(beingId);
    const messageIndex = history.findIndex(msg => msg.timestamp === messageTimestamp);
    
    if (messageIndex !== -1) {
        history[messageIndex].visible_to_players = makeVisible;
        saveBeingChatHistory(beingId, history);
        
        // Re-render the chat
        const beingName = document.getElementById('being-chat-character-name')?.textContent || 'Character';
        renderBeingChat(beingId, beingName);
        
        // Show feedback
        addSystemMessage(
            makeVisible 
                ? `Message made visible to players` 
                : `Message hidden from players`,
            makeVisible ? 'success' : 'info'
        );
    }
};

// View character details (reuse character record viewer)
window.viewCharacterDetails = async function(beingId) {
    const token = authToken || localStorage.getItem('authToken');
    if (!token) {
        alert('Please log in first');
        return;
    }
    
    try {
        // Try to get character data from being registry
        const registryResponse = await fetch(`${BEING_REGISTRY_URL}/beings/${beingId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        let characterData = {
            being_id: beingId,
            registry: null,
            character_data: null
        };
        
        if (registryResponse.ok) {
            const registry = await registryResponse.json();
            characterData.registry = registry;
            characterData.character_data = {
                flavor: {
                    name: registry.name || `Character ${beingId.substring(0, 8)}`
                },
                mechanics: {}
            };
        } else if (registryResponse.status === 404) {
            // Character not found in registry, but might exist in auth service
            // Create minimal data structure from available info
            addSystemMessage(`Character ${beingId.substring(0, 8)} not found in registry. Showing minimal details.`, 'warning');
            characterData.registry = {
                being_id: beingId,
                name: `Character ${beingId.substring(0, 8)}`,
                owner_id: 'Unknown',
                session_id: null
            };
            characterData.character_data = {
                flavor: {
                    name: `Character ${beingId.substring(0, 8)}`
                },
                mechanics: {}
            };
        } else {
            const errorText = await registryResponse.text();
            throw new Error(`Failed to load character: ${registryResponse.status} - ${errorText}`);
        }
        
        showCharacterRecord(characterData);
    } catch (error) {
        console.error('Error loading character details:', error);
        addSystemMessage(`Error loading character details: ${error.message}`, 'error');
        alert('Error loading character details: ' + error.message);
    }
};

// Open character chat
window.openCharacterChat = function(beingId, beingName) {
    // Hide character management panel
    document.getElementById('character-management').style.display = 'none';
    
    // Switch to character chat
    switchBeingChat(beingId, beingName, 'being');
    
    // Scroll to character conversations panel
    const conversationsPanel = document.querySelector('.panel h2')?.parentElement;
    if (conversationsPanel && conversationsPanel.querySelector('h2')?.textContent.includes('Character Conversations')) {
        conversationsPanel.scrollIntoView({ behavior: 'smooth' });
    }
};

// Delete character
window.deleteCharacter = async function(beingId, characterName) {
    const confirmed = await customConfirm(
        `Are you sure you want to delete "${characterName}"?\n\nThis will:\n- Permanently delete the character\n- Remove all associated data\n- Cannot be undone!`,
        'Delete Character'
    );
    if (!confirmed) {
        return;
    }
    
    try {
        const token = authToken || localStorage.getItem('authToken');
        if (!token) {
            alert('Please log in first');
            return;
        }
        
        // Delete from being registry
        const response = await fetch(`${BEING_REGISTRY_URL}/beings/${beingId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`Character "${characterName}" deleted successfully!`);
            
            // Reload characters list
            await loadCharactersForManagement();
            
            // Also reload other character lists
            await loadUserCharacters();
            loadBeingChatCharacters();
            loadAllBeings();
        } else {
            const errorText = await response.text();
            throw new Error(errorText || `HTTP ${response.status}`);
        }
    } catch (error) {
        console.error('Error deleting character:', error);
        alert('Error deleting character: ' + error.message);
    }
};

// System Prompts Management Functions
async function loadPrompts() {
    const serviceSelect = document.getElementById('prompt-service-select');
    const service = serviceSelect ? serviceSelect.value : 'rules_engine';
    const serviceUrls = {
        'rules_engine': RULES_ENGINE_URL,
        'game_master': GM_URL,
        'being': BEING_URL,
        'worlds': WORLDS_URL
    };
    const serviceUrl = serviceUrls[service] || RULES_ENGINE_URL;
    const promptsList = document.getElementById('prompts-list');
    
    if (!promptsList) return;
    
    try {
        const token = authToken || localStorage.getItem('authToken');
        if (!token) {
            promptsList.innerHTML = '<div style="color: #888; padding: 20px; text-align: center;">Not authenticated</div>';
            return;
        }
        
        const response = await fetch(`${serviceUrl}/prompts`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            if (response.status === 403) {
                promptsList.innerHTML = '<div style="color: #f59e0b; padding: 20px; text-align: center;">GM role required</div>';
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const prompts = await response.json();
        
        if (prompts.length === 0) {
            promptsList.innerHTML = '<div style="color: #888; padding: 20px; text-align: center;">No prompts yet. Click "Create Prompt" to add one.</div>';
            return;
        }
        
        promptsList.innerHTML = prompts.map(prompt => {
            const scopeBadge = prompt.scope === 'global' 
                ? '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 6px;">Global</span>'
                : `<span style="background: #f59e0b; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 6px;">Session (${prompt.session_ids.length})</span>`;
            const gameSystemBadge = prompt.game_system 
                ? `<span style="background: #8b5cf6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 6px;">${escapeHTML(prompt.game_system)}</span>`
                : '';
            
            return `
                <div style="background: #2a2a2a; padding: 10px; margin-bottom: 8px; border-radius: 4px; border: 1px solid #444;">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 6px;">
                        <div style="flex: 1;">
                            <div style="font-weight: bold; color: #e0e0e0; margin-bottom: 4px; display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
                                ${escapeHTML(prompt.title)} ${scopeBadge} ${gameSystemBadge}
                            </div>
                            <div style="color: #888; font-size: 0.85em; margin-bottom: 4px;">
                                ${escapeHTML(prompt.content.substring(0, 150))}${prompt.content.length > 150 ? '...' : ''}
                            </div>
                            <div style="color: #666; font-size: 0.75em;">
                                Created: ${new Date(prompt.created_at).toLocaleString()}
                                ${prompt.session_ids.length > 0 ? ` | Sessions: ${prompt.session_ids.join(', ')}` : ''}
                            </div>
                        </div>
                        <div style="display: flex; gap: 4px; flex-shrink: 0;">
                            <button onclick="editPrompt('${prompt.prompt_id}', '${service}')" style="padding: 4px 8px; background: #4a9eff; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.8em;">Edit</button>
                            <button onclick="deletePrompt('${prompt.prompt_id}', '${service}')" style="padding: 4px 8px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.8em;">Delete</button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading prompts:', error);
        promptsList.innerHTML = `<div style="color: #ef4444; padding: 20px; text-align: center;">Error loading prompts: ${escapeHTML(error.message)}</div>`;
    }
}

async function showCreatePromptModal(prefillContent = null, prefillService = null) {
    const serviceSelect = document.getElementById('prompt-service-select');
    const service = prefillService || (serviceSelect ? serviceSelect.value : 'rules_engine');
    const serviceNames = {
        'rules_engine': "Ma'at (Rules Engine)",
        'game_master': "Thoth (Game Master)",
        'being': "Atman (Being Service)",
        'worlds': "Gaia (Worlds Service)"
    };
    const serviceName = serviceNames[service] || serviceNames['rules_engine'];
    
    // Update service selector if prefillService is provided
    if (prefillService && serviceSelect) {
        serviceSelect.value = prefillService;
    }
    
    // Get available sessions for session-scoped prompts
    let sessions = [];
    try {
        const token = authToken || localStorage.getItem('authToken');
        const response = await fetch(`${GAME_SESSION_URL}/sessions`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
            sessions = await response.json();
        }
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
    
    const modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); z-index: 10000; display: flex; align-items: center; justify-content: center;';
    modal.innerHTML = `
        <div style="background: #2a2a2a; border: 1px solid #444; border-radius: 6px; padding: 20px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto;">
            <h3 style="color: #e0e0e0; margin: 0 0 16px 0; font-size: 1.1em; font-weight: 600;">Create System Prompt for ${serviceName}</h3>
            <div style="margin-bottom: 12px;">
                <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Title:</label>
                <input type="text" id="prompt-title-input" placeholder="Prompt title" value="${prefillContent ? 'Saved from chat' : ''}" style="width: 100%; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
            </div>
            <div style="margin-bottom: 12px;">
                <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Content:</label>
                <textarea id="prompt-content-input" placeholder="Enter the prompt content that will be embedded into the LLM's system prompt..." style="width: 100%; min-height: 150px; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; font-family: inherit; resize: vertical; box-sizing: border-box;">${prefillContent ? escapeHTML(prefillContent) : ''}</textarea>
            </div>
            <div style="margin-bottom: 12px;">
                <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Scope:</label>
                <select id="prompt-scope-select" style="width: 100%; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
                    <option value="global">Global (applies to all sessions)</option>
                    <option value="session">Session (applies to specific sessions)</option>
                </select>
            </div>
            <div id="prompt-sessions-container" style="margin-bottom: 12px; display: none;">
                <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Sessions (select multiple):</label>
                <select id="prompt-sessions-select" multiple style="width: 100%; min-height: 100px; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
                    ${sessions.map(s => `<option value="${s.session_id}">${escapeHTML(s.name || s.session_id)}</option>`).join('')}
                </select>
                <div style="color: #888; font-size: 0.8em; margin-top: 4px;">Hold Ctrl/Cmd to select multiple sessions</div>
            </div>
            <div style="margin-bottom: 12px;">
                <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Game System (optional):</label>
                <input type="text" id="prompt-game-system-input" placeholder="e.g., D&D 5e, Pathfinder" style="width: 100%; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
            </div>
            <div style="display: flex; gap: 8px; justify-content: flex-end;">
                <button id="prompt-modal-cancel" style="padding: 8px 16px; background: #666; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em;">Cancel</button>
                <button id="prompt-modal-save" style="padding: 8px 16px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em;">Create Prompt</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Show/hide sessions selector based on scope
    const scopeSelect = document.getElementById('prompt-scope-select');
    const sessionsContainer = document.getElementById('prompt-sessions-container');
    scopeSelect.addEventListener('change', () => {
        sessionsContainer.style.display = scopeSelect.value === 'session' ? 'block' : 'none';
    });
    
    // Handle cancel
    document.getElementById('prompt-modal-cancel').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    // Handle save
    document.getElementById('prompt-modal-save').addEventListener('click', async () => {
        const title = document.getElementById('prompt-title-input').value.trim();
        const content = document.getElementById('prompt-content-input').value.trim();
        const scope = document.getElementById('prompt-scope-select').value;
        const gameSystem = document.getElementById('prompt-game-system-input').value.trim() || null;
        
        if (!title || !content) {
            addSystemMessage('Title and content are required');
            return;
        }
        
        const sessionIds = [];
        if (scope === 'session') {
            const sessionsSelect = document.getElementById('prompt-sessions-select');
            for (const option of sessionsSelect.selectedOptions) {
                sessionIds.push(option.value);
            }
            if (sessionIds.length === 0) {
                addSystemMessage('Please select at least one session for session-scoped prompts');
                return;
            }
        }
        
        try {
            const token = authToken || localStorage.getItem('authToken');
            const serviceUrls = {
                'rules_engine': RULES_ENGINE_URL,
                'game_master': GM_URL,
                'being': BEING_URL
            };
            const serviceUrl = serviceUrls[service] || RULES_ENGINE_URL;
            
            const response = await fetch(`${serviceUrl}/prompts`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title,
                    content,
                    scope,
                    session_ids: sessionIds,
                    game_system: gameSystem
                })
            });
            
            if (response.ok) {
                addSystemMessage(`Prompt "${title}" created successfully`);
                document.body.removeChild(modal);
                await loadPrompts();
            } else {
                const error = await response.text();
                addSystemMessage(`Failed to create prompt: ${error}`);
            }
        } catch (error) {
            console.error('Error creating prompt:', error);
            addSystemMessage(`Error creating prompt: ${error.message}`);
        }
    });
}

window.editPrompt = async function(promptId, service) {
    const serviceUrls = {
        'rules_engine': RULES_ENGINE_URL,
        'game_master': GM_URL,
        'being': BEING_URL,
        'worlds': WORLDS_URL
    };
    const serviceUrl = serviceUrls[service] || RULES_ENGINE_URL;
    const serviceName = service === 'rules_engine' ? "Ma'at (Rules Engine)" : "Thoth (Game Master)";
    
    try {
        const token = authToken || localStorage.getItem('authToken');
        const response = await fetch(`${serviceUrl}/prompts/${promptId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            addSystemMessage('Failed to load prompt');
            return;
        }
        
        const prompt = await response.json();
        
        // Get available sessions
        let sessions = [];
        try {
            const sessionsResponse = await fetch(`${GAME_SESSION_URL}/sessions`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (sessionsResponse.ok) {
                sessions = await sessionsResponse.json();
            }
        } catch (error) {
            console.error('Error loading sessions:', error);
        }
        
        const modal = document.createElement('div');
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); z-index: 10000; display: flex; align-items: center; justify-content: center;';
        modal.innerHTML = `
            <div style="background: #2a2a2a; border: 1px solid #444; border-radius: 6px; padding: 20px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto;">
                <h3 style="color: #e0e0e0; margin: 0 0 16px 0; font-size: 1.1em; font-weight: 600;">Edit System Prompt for ${serviceName}</h3>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Title:</label>
                    <input type="text" id="edit-prompt-title-input" value="${escapeHTML(prompt.title)}" style="width: 100%; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
                </div>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Content:</label>
                    <textarea id="edit-prompt-content-input" style="width: 100%; min-height: 150px; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; font-family: inherit; resize: vertical; box-sizing: border-box;">${escapeHTML(prompt.content)}</textarea>
                </div>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Scope:</label>
                    <select id="edit-prompt-scope-select" style="width: 100%; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
                        <option value="global" ${prompt.scope === 'global' ? 'selected' : ''}>Global (applies to all sessions)</option>
                        <option value="session" ${prompt.scope === 'session' ? 'selected' : ''}>Session (applies to specific sessions)</option>
                    </select>
                </div>
                <div id="edit-prompt-sessions-container" style="margin-bottom: 12px; display: ${prompt.scope === 'session' ? 'block' : 'none'};">
                    <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Sessions (select multiple):</label>
                    <select id="edit-prompt-sessions-select" multiple style="width: 100%; min-height: 100px; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
                        ${sessions.map(s => `<option value="${s.session_id}" ${prompt.session_ids.includes(s.session_id) ? 'selected' : ''}>${escapeHTML(s.name || s.session_id)}</option>`).join('')}
                    </select>
                    <div style="color: #888; font-size: 0.8em; margin-top: 4px;">Hold Ctrl/Cmd to select multiple sessions</div>
                </div>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Game System (optional):</label>
                    <input type="text" id="edit-prompt-game-system-input" value="${escapeHTML(prompt.game_system || '')}" placeholder="e.g., D&D 5e, Pathfinder" style="width: 100%; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
                </div>
                <div style="display: flex; gap: 8px; justify-content: flex-end;">
                    <button id="edit-prompt-modal-cancel" style="padding: 8px 16px; background: #666; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em;">Cancel</button>
                    <button id="edit-prompt-modal-save" style="padding: 8px 16px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em;">Save Changes</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Show/hide sessions selector based on scope
        const scopeSelect = document.getElementById('edit-prompt-scope-select');
        const sessionsContainer = document.getElementById('edit-prompt-sessions-container');
        scopeSelect.addEventListener('change', () => {
            sessionsContainer.style.display = scopeSelect.value === 'session' ? 'block' : 'none';
        });
        
        // Handle cancel
        document.getElementById('edit-prompt-modal-cancel').addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        
        // Handle save
        document.getElementById('edit-prompt-modal-save').addEventListener('click', async () => {
            const title = document.getElementById('edit-prompt-title-input').value.trim();
            const content = document.getElementById('edit-prompt-content-input').value.trim();
            const scope = document.getElementById('edit-prompt-scope-select').value;
            const gameSystem = document.getElementById('edit-prompt-game-system-input').value.trim() || null;
            
            if (!title || !content) {
                addSystemMessage('Title and content are required');
                return;
            }
            
            const sessionIds = [];
            if (scope === 'session') {
                const sessionsSelect = document.getElementById('edit-prompt-sessions-select');
                for (const option of sessionsSelect.selectedOptions) {
                    sessionIds.push(option.value);
                }
                if (sessionIds.length === 0) {
                    addSystemMessage('Please select at least one session for session-scoped prompts');
                    return;
                }
            }
            
            try {
                const token = authToken || localStorage.getItem('authToken');
                
                const response = await fetch(`${serviceUrl}/prompts/${promptId}`, {
                    method: 'PATCH',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        title,
                        content,
                        scope,
                        session_ids: sessionIds,
                        game_system: gameSystem
                    })
                });
                
                if (response.ok) {
                    addSystemMessage(`Prompt "${title}" updated successfully`);
                    document.body.removeChild(modal);
                    await loadPrompts();
                } else {
                    const error = await response.text();
                    addSystemMessage(`Failed to update prompt: ${error}`);
                }
            } catch (error) {
                console.error('Error updating prompt:', error);
                addSystemMessage(`Error updating prompt: ${error.message}`);
            }
        });
    } catch (error) {
        console.error('Error loading prompt for edit:', error);
        addSystemMessage(`Error loading prompt: ${error.message}`);
    }
};

window.deletePrompt = async function(promptId, service) {
    const serviceUrls = {
        'rules_engine': RULES_ENGINE_URL,
        'game_master': GM_URL,
        'being': BEING_URL,
        'worlds': WORLDS_URL
    };
    const serviceUrl = serviceUrls[service] || RULES_ENGINE_URL;
    const confirmed = await customConfirm(
        'Are you sure you want to delete this system prompt? This action cannot be undone.',
        'Delete System Prompt'
    );
    
    if (!confirmed) return;
    
    try {
        const token = authToken || localStorage.getItem('authToken');
        const response = await fetch(`${serviceUrl}/prompts/${promptId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            addSystemMessage('Prompt deleted successfully');
            await loadPrompts();
        } else {
            const error = await response.text();
            addSystemMessage(`Failed to delete prompt: ${error}`);
        }
    } catch (error) {
        console.error('Error deleting prompt:', error);
        addSystemMessage(`Error deleting prompt: ${error.message}`);
    }
};

// Rule File Associations Management
window.manageRuleAssociations = async function(fileId) {
    try {
        const token = authToken || localStorage.getItem('authToken');
        
        // Get current rule metadata
        const ruleResponse = await fetch(`${RULES_ENGINE_URL}/rules/list`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!ruleResponse.ok) {
            addSystemMessage('Failed to load rule file');
            return;
        }
        
        const data = await ruleResponse.json();
        const rule = data.rules.find(r => r.file_id === fileId);
        
        if (!rule) {
            addSystemMessage('Rule file not found');
            return;
        }
        
        // Get available sessions
        let sessions = [];
        try {
            const sessionsResponse = await fetch(`${GAME_SESSION_URL}/sessions`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (sessionsResponse.ok) {
                sessions = await sessionsResponse.json();
            }
        } catch (error) {
            console.error('Error loading sessions:', error);
        }
        
        const modal = document.createElement('div');
        modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); z-index: 10000; display: flex; align-items: center; justify-content: center;';
        modal.innerHTML = `
            <div style="background: #2a2a2a; border: 1px solid #444; border-radius: 6px; padding: 20px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto;">
                <h3 style="color: #e0e0e0; margin: 0 0 16px 0; font-size: 1.1em; font-weight: 600;">Manage Associations: ${escapeHTML(rule.filename || rule.original_filename)}</h3>
                <div style="margin-bottom: 12px; padding: 10px; background: #1a1a1a; border-radius: 4px; font-size: 0.85em; color: #888;">
                    <strong>Associations</strong> control when this rule file is used:
                    <ul style="margin: 8px 0 0 20px; padding: 0;">
                        <li><strong>Game System:</strong> Filter rules by game system (e.g., D&D 5e, Pathfinder)</li>
                        <li><strong>Sessions:</strong> Limit to specific sessions (empty = global, applies to all sessions)</li>
                    </ul>
                </div>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Game System (optional):</label>
                    <input type="text" id="rule-game-system-input" value="${escapeHTML(rule.game_system || '')}" placeholder="e.g., D&D 5e, Pathfinder, Custom" style="width: 100%; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
                    <div style="color: #888; font-size: 0.75em; margin-top: 4px;">Leave empty to make this file available for all game systems</div>
                </div>
                <div style="margin-bottom: 12px;">
                    <label style="display: block; color: #bbb; margin-bottom: 4px; font-size: 0.9em;">Sessions (select multiple, or leave empty for global):</label>
                    <select id="rule-sessions-select" multiple style="width: 100%; min-height: 150px; padding: 8px 12px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 3px; font-size: 0.95em; box-sizing: border-box;">
                        ${sessions.map(s => `<option value="${s.session_id}" ${(rule.session_ids || []).includes(s.session_id) ? 'selected' : ''}>${escapeHTML(s.name || s.session_id)}</option>`).join('')}
                    </select>
                    <div style="color: #888; font-size: 0.75em; margin-top: 4px;">Hold Ctrl/Cmd to select multiple sessions. Leave empty to make this file global (available to all sessions).</div>
                </div>
                <div style="display: flex; gap: 8px; justify-content: flex-end;">
                    <button id="rule-associations-cancel" style="padding: 8px 16px; background: #666; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em;">Cancel</button>
                    <button id="rule-associations-save" style="padding: 8px 16px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em;">Save Associations</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Handle cancel
        document.getElementById('rule-associations-cancel').addEventListener('click', () => {
            document.body.removeChild(modal);
        });
        
        // Handle save
        document.getElementById('rule-associations-save').addEventListener('click', async () => {
            const gameSystem = document.getElementById('rule-game-system-input').value.trim() || null;
            const sessionsSelect = document.getElementById('rule-sessions-select');
            const sessionIds = [];
            for (const option of sessionsSelect.selectedOptions) {
                sessionIds.push(option.value);
            }
            
            try {
                const token = authToken || localStorage.getItem('authToken');
                const response = await fetch(`${RULES_ENGINE_URL}/rules/${fileId}/associations`, {
                    method: 'PATCH',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        game_system: gameSystem,
                        session_ids: sessionIds
                    })
                });
                
                if (response.ok) {
                    addSystemMessage('Rule file associations updated successfully');
                    document.body.removeChild(modal);
                    await listRules();
                } else {
                    const error = await response.text();
                    addSystemMessage(`Failed to update associations: ${error}`);
                }
            } catch (error) {
                console.error('Error updating rule associations:', error);
                addSystemMessage(`Error updating associations: ${error.message}`);
            }
        });
    } catch (error) {
        console.error('Error loading rule for associations:', error);
        addSystemMessage(`Error loading rule: ${error.message}`);
    }
};

// Update active prompts indicator for current service
async function updateActivePromptsIndicator(service) {
    const indicator = document.getElementById('llm-active-prompts-indicator');
    const countSpan = document.getElementById('llm-active-prompts-count');
    
    if (!indicator || !countSpan) return;
    
    try {
        const token = authToken || localStorage.getItem('authToken');
        if (!token) {
            indicator.style.display = 'none';
            return;
        }
        
        const serviceUrls = {
            'rules_engine': RULES_ENGINE_URL,
            'game_master': GM_URL,
            'being': BEING_URL
        };
        const serviceUrl = serviceUrls[service] || RULES_ENGINE_URL;
        const currentSession = window.currentSession ? window.currentSession.session_id : null;
        
        // Get active prompts (global + session-specific)
        const response = await fetch(`${serviceUrl}/prompts?session_id=${currentSession || ''}&include_global=true`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const prompts = await response.json();
            const activePrompts = prompts.filter(p => {
                // Global prompts are always active
                if (p.scope === 'global') return true;
                // Session-scoped prompts are active if current session is in the list
                if (p.scope === 'session' && currentSession) {
                    return p.session_ids.includes(currentSession);
                }
                return false;
            });
            
            if (activePrompts.length > 0) {
                countSpan.textContent = activePrompts.length;
                indicator.style.display = 'block';
                
                // Store active prompts for viewing
                window.activePromptsForService = activePrompts;
            } else {
                indicator.style.display = 'none';
            }
        } else {
            indicator.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading active prompts:', error);
        indicator.style.display = 'none';
    }
}

// View active prompts
document.getElementById('llm-view-prompts-btn')?.addEventListener('click', () => {
    const prompts = window.activePromptsForService || [];
    if (prompts.length === 0) {
        addSystemMessage('No active prompts');
        return;
    }
    
    const modal = document.createElement('div');
    modal.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); z-index: 10000; display: flex; align-items: center; justify-content: center;';
    modal.innerHTML = `
        <div style="background: #2a2a2a; border: 1px solid #444; border-radius: 6px; padding: 20px; max-width: 700px; width: 90%; max-height: 90vh; overflow-y: auto;">
            <h3 style="color: #e0e0e0; margin: 0 0 16px 0; font-size: 1.1em; font-weight: 600;">Active System Prompts</h3>
            <div style="color: #888; font-size: 0.85em; margin-bottom: 16px;">
                These prompts are currently being applied to ${LLM_SERVICES[currentLLMService].name.split(' ')[0]}'s system prompt.
            </div>
            <div style="display: flex; flex-direction: column; gap: 12px;">
                ${prompts.map(prompt => {
                    const scopeBadge = prompt.scope === 'global' 
                        ? '<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em;">Global</span>'
                        : `<span style="background: #f59e0b; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em;">Session</span>`;
                    const gameSystemBadge = prompt.game_system 
                        ? `<span style="background: #8b5cf6; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; margin-left: 4px;">${escapeHTML(prompt.game_system)}</span>`
                        : '';
                    
                    return `
                        <div style="background: #1a1a1a; padding: 12px; border-radius: 4px; border-left: 3px solid ${LLM_SERVICES[currentLLMService].color};">
                            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                                <strong style="color: #e0e0e0;">${escapeHTML(prompt.title)}</strong>
                                ${scopeBadge}
                                ${gameSystemBadge}
                            </div>
                            <div style="color: #bbb; font-size: 0.9em; white-space: pre-wrap;">${escapeHTML(prompt.content)}</div>
                        </div>
                    `;
                }).join('')}
            </div>
            <div style="display: flex; justify-content: flex-end; margin-top: 16px;">
                <button onclick="this.closest('div[style*=\"position: fixed\"]').remove()" style="padding: 8px 16px; background: #666; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em;">Close</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
});

// Setup text selection handler for chat messages
function setupTextSelectionHandler(messagesDiv, service) {
    let selectionToolbar = null;
    
    // Remove existing toolbar if it exists
    const existingToolbar = document.getElementById('selection-toolbar');
    if (existingToolbar) {
        existingToolbar.remove();
    }
    
    // Create selection toolbar (initially hidden)
    selectionToolbar = document.createElement('div');
    selectionToolbar.id = 'selection-toolbar';
    selectionToolbar.style.cssText = 'position: absolute; display: none; background: #2a2a2a; border: 1px solid #444; border-radius: 4px; padding: 6px 8px; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,0.3);';
    selectionToolbar.innerHTML = `
        <button id="save-selection-btn" style="padding: 4px 8px; background: #10b981; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em; display: flex; align-items: center; gap: 4px;">
            <span>💾</span>
            <span>Save Selection as Prompt</span>
        </button>
    `;
    document.body.appendChild(selectionToolbar);
    
    // Handle mouseup events to detect text selection
    messagesDiv.addEventListener('mouseup', (e) => {
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();
        
        // Hide toolbar if no text is selected or selection is outside messages div
        if (!selectedText || selectedText.length === 0) {
            selectionToolbar.style.display = 'none';
            return;
        }
        
        // Check if selection is within the messages div
        const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;
        if (!range || !messagesDiv.contains(range.commonAncestorContainer)) {
            selectionToolbar.style.display = 'none';
            return;
        }
        
        // Get position for toolbar (near the selection)
        const rect = range.getBoundingClientRect();
        const toolbarRect = selectionToolbar.getBoundingClientRect();
        
        // Position toolbar above the selection, centered horizontally
        let top = rect.top - toolbarRect.height - 8;
        let left = rect.left + (rect.width / 2) - (toolbarRect.width / 2);
        
        // Adjust if toolbar would go off-screen
        if (top < 0) {
            top = rect.bottom + 8; // Show below instead
        }
        if (left < 0) {
            left = 8;
        }
        if (left + toolbarRect.width > window.innerWidth) {
            left = window.innerWidth - toolbarRect.width - 8;
        }
        
        selectionToolbar.style.top = `${top}px`;
        selectionToolbar.style.left = `${left}px`;
        selectionToolbar.style.display = 'block';
        
        // Store selected text and service in the button
        const saveBtn = document.getElementById('save-selection-btn');
        saveBtn.dataset.selectedText = selectedText;
        saveBtn.dataset.service = service;
    });
    
    // Hide toolbar when clicking elsewhere
    document.addEventListener('mousedown', (e) => {
        if (!selectionToolbar.contains(e.target) && !messagesDiv.contains(e.target)) {
            selectionToolbar.style.display = 'none';
        }
    });
    
    // Handle save selection button click
    document.getElementById('save-selection-btn').addEventListener('click', (e) => {
        const selectedText = e.target.dataset.selectedText || e.target.closest('#save-selection-btn').dataset.selectedText;
        const service = e.target.dataset.service || e.target.closest('#save-selection-btn').dataset.service;
        
        if (selectedText && service) {
            saveMessageAsPrompt(service, selectedText);
            selectionToolbar.style.display = 'none';
            // Clear selection
            window.getSelection().removeAllRanges();
        }
    });
}

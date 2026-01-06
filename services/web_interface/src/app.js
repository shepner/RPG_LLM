// TTRPG LLM System Web Interface

const AUTH_URL = 'http://localhost:8000';
const GAME_SESSION_URL = 'http://localhost:8001';
const WORLDS_URL = 'http://localhost:8004';
const GM_URL = 'http://localhost:8005';
const BEING_REGISTRY_URL = 'http://localhost:8007';

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
            document.getElementById('username-display').textContent = username;
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('user-info').style.display = 'block';
            document.getElementById('game-section').style.display = 'block';
            
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
function addEvent(event) {
    const log = document.getElementById('events-log');
    const div = document.createElement('div');
    div.className = 'event';
    div.innerHTML = `<strong>${event.event_type}</strong>: ${event.description}`;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

function addNarrative(narrative) {
    const log = document.getElementById('narrative-log');
    const div = document.createElement('div');
    div.className = 'narrative';
    div.textContent = narrative.text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
}

// Action submission
document.getElementById('submit-action').addEventListener('click', async () => {
    const action = document.getElementById('action-input').value;
    if (!action) {
        alert('Please describe an action');
        return;
    }
    
    addEvent({
        event_type: 'player_action',
        description: `You: ${action}`,
        game_time: Date.now()
    });
    
    // TODO: Submit action to being service
    console.log('Action:', action);
    document.getElementById('action-input').value = '';
    
    // Show feedback
    alert('Action submitted! (Full integration with being service coming soon)');
});

// Game session management
document.getElementById('create-session-btn').addEventListener('click', async () => {
    const sessionName = prompt('Enter a name for your game session:');
    if (!sessionName) return;
    
    try {
        // Get current user to determine if they're GM
        const userResponse = await fetch(`${AUTH_URL}/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (!userResponse.ok) {
            alert('Could not get user info. Please log in again.');
            return;
        }
        
        const user = await userResponse.json();
        const isGM = user.role === 'gm';
        
        if (!isGM) {
            alert('Only Game Masters can create sessions. Your role is: ' + user.role);
            return;
        }
        
        const response = await fetch(`${GAME_SESSION_URL}/sessions?gm_user_id=${user.user_id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
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
            addNarrative({
                text: `Created game session: ${session.name} (ID: ${session.session_id})`
            });
            addEvent({
                event_type: 'session_created',
                description: `New game session "${session.name}" created`,
                game_time: Date.now()
            });
            await refreshSessions();
        } else {
            const error = await response.text();
            alert('Failed to create session: ' + error);
        }
    } catch (error) {
        console.error('Error creating session:', error);
        alert('Error creating session: ' + error.message);
    }
});

document.getElementById('refresh-sessions-btn').addEventListener('click', async () => {
    await refreshSessions();
});

async function refreshSessions() {
    try {
        const response = await fetch(`${GAME_SESSION_URL}/sessions`);
        const sessionsList = document.getElementById('sessions-list');
        
        if (response.ok) {
            const sessions = await response.json();
            sessionsList.innerHTML = '';
            
            if (sessions.length === 0) {
                sessionsList.innerHTML = '<p style="color: #888;">No game sessions available.</p>';
                return;
            }
            
            sessions.forEach(session => {
                const div = document.createElement('div');
                div.style.marginBottom = '10px';
                div.style.padding = '10px';
                div.style.backgroundColor = '#2a2a2a';
                div.style.borderRadius = '4px';
                div.innerHTML = `
                    <strong style="color: #4a9eff;">${session.name}</strong>
                    <br><span style="color: #888; font-size: 0.9em;">Status: ${session.status} | Players: ${session.player_user_ids?.length || 0}</span>
                    <br><button onclick="joinSession('${session.session_id}')" style="margin-top: 5px; padding: 5px 10px; background: #4a9eff; color: white; border: none; border-radius: 4px; cursor: pointer;">Join Session</button>
                `;
                sessionsList.appendChild(div);
            });
        } else {
            sessionsList.innerHTML = '<p style="color: #f44;">Could not load sessions.</p>';
        }
    } catch (error) {
        console.error('Error refreshing sessions:', error);
    }
}

// Make joinSession available globally
window.joinSession = async function(sessionId) {
    try {
        const userResponse = await fetch(`${AUTH_URL}/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const user = await userResponse.json();
        
        const response = await fetch(`${GAME_SESSION_URL}/sessions/${sessionId}/join?user_id=${user.user_id}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            addNarrative({
                text: `Joined game session!`
            });
            addEvent({
                event_type: 'session_joined',
                description: `You joined session ${sessionId}`,
                game_time: Date.now()
            });
            await refreshSessions();
        } else {
            alert('Failed to join session');
        }
    } catch (error) {
        console.error('Error joining session:', error);
        alert('Error joining session: ' + error.message);
    }
};

// Load initial game state
async function loadGameState() {
    try {
        // Get user info
        const userResponse = await fetch(`${AUTH_URL}/me`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (userResponse.ok) {
            const user = await userResponse.json();
            addNarrative({
                text: `Welcome, ${user.username}! You are logged in as a ${user.role}.`
            });
        }
        
        // List game sessions (no auth required for listing)
        try {
            const sessionsResponse = await fetch(`${GAME_SESSION_URL}/sessions`);
            
            if (sessionsResponse.ok) {
                const sessions = await sessionsResponse.json();
                if (sessions.length > 0) {
                    addNarrative({
                        text: `Found ${sessions.length} game session(s). Select one to join or create a new one.`
                    });
                } else {
                    addNarrative({
                        text: 'No active game sessions. Create a new session to start playing!'
                    });
                }
            } else {
                console.warn('Could not list sessions:', sessionsResponse.status);
            }
        } catch (e) {
            console.warn('Error listing sessions:', e);
            // Don't show error to user, just log it
        }
        
        // Add welcome message
        addEvent({
            event_type: 'system',
            description: 'System initialized. Ready to play!',
            game_time: Date.now()
        });
        
    } catch (error) {
        console.error('Error loading game state:', error);
        addEvent({
            event_type: 'error',
            description: 'Could not load game state. Some features may not work.',
            game_time: Date.now()
        });
    }
}


// TTRPG LLM System Web Interface
// Version: 1.0.0

const AUTH_URL = 'http://localhost:8000';
const GAME_SESSION_URL = 'http://localhost:8001';
const RULES_ENGINE_URL = 'http://localhost:8002';
const WORLDS_URL = 'http://localhost:8004';
const GM_URL = 'http://localhost:8005';
const BEING_REGISTRY_URL = 'http://localhost:8007';

const SYSTEM_VERSION = '1.0.0';

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
    const characterId = document.getElementById('character-select').value;
    
    if (!action) {
        alert('Please describe an action');
        return;
    }
    
    if (!characterId) {
        alert('Please select a character first');
        return;
    }
    
    try {
        // Get current game time
        const currentSession = window.currentSession;
        if (!currentSession) {
            alert('Please join a game session first');
            return;
        }
        
        // TODO: Get actual game time from time management service
        const gameTime = Date.now() / 1000; // Temporary - should use actual game time
        
        // Submit action to being service
        // First, get the being service endpoint from registry
        const registryResponse = await fetch(`${BEING_REGISTRY_URL}/beings/${characterId}`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!registryResponse.ok) {
            throw new Error('Could not find character');
        }
        
        const registry = await registryResponse.json();
        const beingServiceUrl = registry.service_endpoint || `http://localhost:8006`; // Default being service port
        
        // Submit action to being service
        const actionResponse = await fetch(`${beingServiceUrl}/decide`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                being_id: characterId,
                context: action,
                game_time: gameTime
            })
        });
        
        if (actionResponse.ok) {
            const actionResult = await actionResponse.json();
            addEvent({
                event_type: 'player_action',
                description: `Character action: ${action}`,
                game_time: gameTime
            });
            document.getElementById('action-input').value = '';
            addNarrative({
                text: `Action submitted: ${action}`
            });
        } else {
            const error = await actionResponse.text();
            throw new Error(`Failed to submit action: ${error}`);
        }
    } catch (error) {
        console.error('Error submitting action:', error);
        alert('Error submitting action: ' + error.message);
    }
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
            const fixFirst = confirm('Only Game Masters can create sessions. Your role is: ' + user.role + '\n\nWould you like to check if you should be the first GM?');
            if (fixFirst) {
                try {
                    const fixResponse = await fetch(`${AUTH_URL}/users/fix-first-user`, {
                        method: 'POST',
                        headers: { 
                            'Authorization': `Bearer ${authToken}`,
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
                <div id="user-${user.user_id}" style="padding: 15px; margin-bottom: 10px; background: #2a2a2a; border-radius: 6px; border-left: 4px solid ${roleColor};">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;">
                                <strong style="color: ${roleColor}; font-size: 1.1em;">${roleIcon} ${user.username}</strong>
                                ${isCurrentUser ? '<span style="color: #888; font-size: 0.85em;">(You)</span>' : ''}
                            </div>
                            <div style="color: #888; font-size: 0.9em; margin-bottom: 8px;">${user.email}</div>
                            <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                                <select id="role-${user.user_id}" style="padding: 4px 8px; background: #1a1a1a; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; font-size: 0.9em;">
                                    <option value="player" ${user.role === 'player' ? 'selected' : ''}>Player</option>
                                    <option value="gm" ${user.role === 'gm' ? 'selected' : ''}>Game Master</option>
                                </select>
                                <button onclick="updateUserRole('${user.user_id}')" style="padding: 4px 12px; background: #4a9eff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85em;">Update Role</button>
                                <button onclick="manageUserCharacters('${user.user_id}', '${user.username}')" style="padding: 4px 12px; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85em;">📋 Manage Characters</button>
                                ${!isCurrentUser ? `<button onclick="deleteUser('${user.user_id}', '${user.username}')" style="padding: 4px 12px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85em;">🗑️ Delete</button>` : '<span style="color: #888; font-size: 0.85em;">(Cannot delete yourself)</span>'}
                            </div>
                        </div>
                    </div>
                    <div style="color: #666; font-size: 0.8em; margin-top: 8px;">
                        Created: ${new Date(user.created_at).toLocaleString()}
                    </div>
                </div>
            `;
        }).join('');
        
        modal.innerHTML = `
            <div style="background: #1a1a1a; padding: 25px; border-radius: 8px; max-width: 900px; width: 90%; max-height: 90vh; overflow-y: auto; position: relative;">
                <button onclick="this.parentElement.parentElement.remove()" style="position: absolute; top: 15px; right: 15px; background: #ef4444; color: white; border: none; border-radius: 4px; padding: 8px 15px; cursor: pointer; font-size: 0.9em;">✕ Close</button>
                <h2 style="margin-top: 0; margin-bottom: 20px; color: #e0e0e0;">👥 User Management</h2>
                <p style="color: #888; font-size: 0.9em; margin-bottom: 20px;">
                    Manage user accounts: change roles, assign characters, and delete accounts. Only Game Masters can access this panel.
                </p>
                <div id="users-list" style="margin-bottom: 20px;">
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
    if (!confirm(`Are you sure you want to delete user "${username}"?\n\nThis will:\n- Delete their account permanently\n- Remove them from all character assignments\n- Cannot be undone!`)) {
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
                try {
                    const response = await fetch(`${BEING_REGISTRY_URL}/system/validate`, {
                        headers: {
                            'Authorization': `Bearer ${authToken}`
                        }
                    });
                    
                    if (response.ok) {
                        const report = await response.json();
                        displayValidationReport(report);
                    } else {
                        const error = await response.text();
                        alert('Failed to validate system: ' + error);
                    }
                } catch (error) {
                    console.error('Error validating system:', error);
                    alert('Error validating system: ' + error.message);
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
            <div style="padding: 8px; margin-bottom: 5px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid ${serviceColor};">
                <strong>${serviceIcon} ${name}</strong>
                <span style="color: ${serviceColor}; margin-left: 10px;">${status.message || serviceStatus}${responseTime}</span>
            </div>
        `;
    }
    
    let integrationsHtml = '';
    for (const [name, integration] of Object.entries(report.integrations || {})) {
        const intStatus = integration.status || 'unknown';
        const intColor = intStatus === 'ok' ? '#10b981' : intStatus === 'warning' ? '#f59e0b' : '#ef4444';
        const intIcon = intStatus === 'ok' ? '✅' : intStatus === 'warning' ? '⚠️' : '❌';
        let detailsHtml = '';
        if (integration.details) {
            detailsHtml = `<div style="color: #666; font-size: 0.85em; margin-top: 3px; padding-left: 10px;">${JSON.stringify(integration.details, null, 2).replace(/\n/g, '<br>').replace(/ /g, '&nbsp;')}</div>`;
        }
        integrationsHtml += `
            <div style="padding: 8px; margin-bottom: 5px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid ${intColor};">
                <strong>${intIcon} ${name.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</strong>
                <div style="color: #888; font-size: 0.9em; margin-top: 3px;">${integration.message || intStatus}</div>
                ${detailsHtml}
            </div>
        `;
    }
    
    modal.innerHTML = `
        <div style="background: #1a1a1a; padding: 20px; border-radius: 8px; max-width: 80%; max-height: 90%; overflow: auto; position: relative; min-width: 600px;">
            <button onclick="this.parentElement.parentElement.remove()" style="position: absolute; top: 10px; right: 10px; background: #ef4444; color: white; border: none; border-radius: 4px; padding: 5px 10px; cursor: pointer;">Close</button>
            <h2 style="margin-top: 0; color: ${statusColor};">
                ${statusIcon} System Validation Report
            </h2>
            <div style="margin-bottom: 15px; padding: 12px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid #4a9eff;">
                <p style="color: #e0e0e0; margin: 0; font-size: 0.95em;">
                    <strong>What this does:</strong> Checks the health and connectivity of all core services (Auth, Rules Engine, Game Master, Worlds, Being Registry, Time Management) and validates key integrations between services. Use this to diagnose system issues.
                </p>
            </div>
            <div style="margin-bottom: 20px; padding: 10px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid ${statusColor};">
                <strong>Overall Status: <span style="color: ${statusColor};">${overallStatus.toUpperCase()}</span></strong>
                <div style="color: #888; font-size: 0.9em; margin-top: 5px;">Validated at: ${new Date(report.timestamp || Date.now()).toLocaleString()}</div>
            </div>
            
            <h3 style="color: #e0e0e0;">Services</h3>
            <div style="margin-bottom: 20px;">
                ${servicesHtml}
            </div>
            
            <h3 style="color: #e0e0e0;">Integrations</h3>
            <div style="margin-bottom: 20px;">
                ${integrationsHtml}
            </div>
            
            ${report.recommendations && report.recommendations.length > 0 ? `
                <h3 style="color: #f59e0b;">Recommendations</h3>
                <ul style="color: #888;">
                    ${report.recommendations.map(r => `<li>${r}</li>`).join('')}
                </ul>
            ` : ''}
        </div>
    `;
    document.body.appendChild(modal);
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
            // Find the session in the list to store it
            const sessionsResponse = await fetch(`${GAME_SESSION_URL}/sessions`);
            if (sessionsResponse.ok) {
                const sessions = await sessionsResponse.json();
                const session = sessions.find(s => s.session_id === sessionId);
                if (session) {
                    window.currentSession = session;
                }
            }
            
            // Session join is a game event, not narrative
            addEvent({
                event_type: 'session_joined',
                description: `You joined session ${sessionId}`,
                game_time: Date.now()
            });
            await refreshSessions();
            // Reload characters for this session
            await loadUserCharacters();
        } else {
            alert('Failed to join session');
        }
    } catch (error) {
        console.error('Error joining session:', error);
        alert('Error joining session: ' + error.message);
    }
};

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
                const validateSystemBtn = document.getElementById('validate-system-btn');
                if (validateSystemBtn) {
                    validateSystemBtn.style.display = 'inline-block';
                }
            } else {
                const manageRulesBtn = document.getElementById('manage-rules-btn');
                if (manageRulesBtn) {
                    manageRulesBtn.style.display = 'none';
                }
                const validateSystemBtn = document.getElementById('validate-system-btn');
                if (validateSystemBtn) {
                    validateSystemBtn.style.display = 'none';
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
            // Don't add system messages to narrative - narrative is for game story only
            console.log(`User logged in: ${user.username} (${user.role})`);
        }
        
        // List game sessions (no auth required for listing)
        try {
            const sessionsResponse = await fetch(`${GAME_SESSION_URL}/sessions`);
            
            if (sessionsResponse.ok) {
                const sessions = await sessionsResponse.json();
                // Don't add system messages to narrative - just log for debugging
                console.log(`Found ${sessions.length} game session(s)`);
            } else {
                console.warn('Could not list sessions:', sessionsResponse.status);
            }
        } catch (e) {
            console.warn('Error listing sessions:', e);
            // Don't show error to user, just log it
        }
        
        // System initialization - this is a system event, not a game event
        // Game Events should only show actual game mechanics (actions, world changes, etc.)
        console.log('System initialized. Ready to play!');
        
    } catch (error) {
        console.error('Error loading game state:', error);
        addEvent({
            event_type: 'error',
            description: 'Could not load game state. Some features may not work.',
            game_time: Date.now()
        });
    }
    
    // Load user's characters
    await loadUserCharacters();
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
        } else if (response.status === 401) {
            // Token expired or invalid, clear it and show login
            console.log('Authentication failed, clearing token');
            authToken = null;
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
        }
    } catch (error) {
        console.error('Error loading characters:', error);
    }
}

// Rules management (GM only) - with auto-refresh
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

document.getElementById('upload-rules-btn')?.addEventListener('click', async () => {
    const fileInput = document.getElementById('rules-file-input');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a rules file');
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
            alert(`Rules uploaded successfully: ${result.filename}`);
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
            alert('Failed to upload rules: ' + error);
        }
    } catch (error) {
        console.error('Error uploading rules:', error);
        alert('Error uploading rules: ' + error.message);
    }
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
                // File not found, stop polling
                stopIndexingProgressPoll(fileId);
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

async function listRules() {
    try {
        const token = authToken || localStorage.getItem('authToken');
        const response = await fetch(`${RULES_ENGINE_URL}/rules/list`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const rulesList = document.getElementById('rules-list');
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
                                'chunking': 'Chunking content...',
                                'generating_embeddings': 'Generating embeddings...',
                                'preparing_data': 'Preparing data...',
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
                            const errorId = `error-${rule.file_id}`;
                            statusBadge += `
                                <div style="margin-top: 8px; padding: 8px; background: #2a1a1a; border-left: 3px solid ${errorColor}; border-radius: 4px;">
                                    <div style="color: ${errorColor}; font-weight: bold; font-size: 0.85em; margin-bottom: 4px;">
                                        ${errorType}
                                    </div>
                                    <div style="color: #e0e0e0; font-size: 0.8em; margin-bottom: 6px;">
                                        ${errorMsg}
                                    </div>
                                    <details style="margin-top: 4px;">
                                        <summary style="color: #888; font-size: 0.75em; cursor: pointer; user-select: none;">Show technical details</summary>
                                        <pre style="color: #aaa; font-size: 0.7em; margin-top: 4px; white-space: pre-wrap; word-break: break-word; max-height: 100px; overflow-y: auto;">${rule.indexing_error.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
                                    </details>
                                    <button onclick="retryIndexing('${rule.file_id}')" style="margin-top: 6px; padding: 4px 12px; background: #f59e0b; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.75em; font-weight: bold;">🔄 Retry Indexing</button>
                                </div>
                            `;
                        }
                    }
                    
                    return `
                        <div style="padding: 10px; margin-bottom: 8px; background: #2a2a2a; border-radius: 4px; border-left: 3px solid ${categoryColor};">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong style="color: ${categoryColor};">${categoryIcon} ${rule.filename || rule.original_filename}</strong>
                                    <span style="color: #888; margin-left: 10px; font-size: 0.9em;">${sizeKB} KB</span>
                                    <span style="color: #666; margin-left: 10px; font-size: 0.85em;">(${category})</span>
                                    ${statusBadge}
                                </div>
                                <div>
                                    ${rule.is_text ? `<button onclick="viewRule('${rule.file_id}')" style="padding: 4px 8px; margin-right: 5px; background: #666; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">View</button>` : ''}
                                    <button onclick="downloadRule('${rule.file_id}')" style="padding: 4px 8px; margin-right: 5px; background: #4a9eff; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Download</button>
                                    <button onclick="deleteRule('${rule.file_id}')" style="padding: 4px 8px; background: #ef4444; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em;">Delete</button>
                                </div>
                            </div>
                            ${rule.is_image ? `<div style="margin-top: 8px;"><img src="${RULES_ENGINE_URL}/rules/${rule.file_id}" style="max-width: 100%; max-height: 200px; border-radius: 4px;" alt="${rule.filename}"></div>` : ''}
                            <div style="color: #888; font-size: 0.8em; margin-top: 5px;">Uploaded: ${new Date(rule.uploaded_at).toLocaleString()}</div>
                        </div>
                    `;
                }).join('');
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

// Retry indexing for a failed file
window.retryIndexing = async function(fileId) {
    if (!confirm('Retry indexing for this file? This will attempt to index the file again.')) {
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
            alert('Indexing retry initiated! The file will be re-indexed in the background.');
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
    if (!confirm('Are you sure you want to delete this file?\n\nThis will permanently remove the file from:\n- Disk storage\n- Search index\n- System metadata')) {
        return;
    }
    
    try {
        const response = await fetch(`${RULES_ENGINE_URL}/rules/${fileId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            const deletedFrom = result.deleted_from || [];
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
        } else {
            // Token is invalid, clear it and show login form
            console.log('Stored token is invalid, clearing session');
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            authToken = null;
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
        // Display version number
        const versionDisplay = document.getElementById('version-display');
        if (versionDisplay) {
            versionDisplay.textContent = `v${SYSTEM_VERSION}`;
        }
    });
} else {
    // DOM is already loaded
    initializeSession();
    // Display version number
    const versionDisplay = document.getElementById('version-display');
    if (versionDisplay) {
        versionDisplay.textContent = `v${SYSTEM_VERSION}`;
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
            alert(`Character created successfully! ID: ${result.being_id}`);
            document.getElementById('character-creation').style.display = 'none';
            
            // Clear form
            document.getElementById('character-name').value = '';
            document.getElementById('character-backstory').value = '';
            document.getElementById('character-personality').value = '';
            document.getElementById('character-appearance').value = '';
            document.getElementById('auto-generate-character').checked = false;
            
            // Reload characters
            await loadUserCharacters();
            
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


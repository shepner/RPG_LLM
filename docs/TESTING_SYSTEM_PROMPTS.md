# System Prompts & Rule File Management - Testing Checklist

## Overview
This document outlines all testing requirements for the System Prompts and Rule File Management features. These features allow GMs to provide persistent context to LLM services and manage rule file associations with game systems and sessions.

---

## Pre-Testing Setup

### Prerequisites
- [ ] All services are running (`docker compose up -d`)
- [ ] GM account is created and logged in
- [ ] At least one game session exists (for session-scoped testing)
- [ ] At least one rule file is uploaded (for rule file association testing)

### Test Data Preparation
- [ ] Create a test game session (e.g., "Test D&D Session")
- [ ] Create another test game session (e.g., "Test Pathfinder Session")
- [ ] Upload at least 2 rule files (e.g., one D&D rulebook, one Pathfinder rulebook)
- [ ] Note the session IDs for use in testing

---

## Part 1: Rules Engine (Ma'at) System Prompts

### 1.1 Create System Prompt (Global)
- [ ] Navigate to Rules Engine system prompts management UI
- [ ] Click "Create New Prompt"
- [ ] Enter title: "Test Global Prompt"
- [ ] Enter content: "Always use advantage/disadvantage rules from D&D 5e"
- [ ] Set scope to "Global"
- [ ] Leave game_system empty or set to "D&D 5e"
- [ ] Save prompt
- [ ] Verify prompt appears in list
- [ ] Verify prompt shows "Global" scope indicator

### 1.2 Create System Prompt (Session-Scoped)
- [ ] Click "Create New Prompt"
- [ ] Enter title: "Test Session Prompt"
- [ ] Enter content: "This session uses house rules for critical hits"
- [ ] Set scope to "Session"
- [ ] Select a specific session from dropdown
- [ ] Save prompt
- [ ] Verify prompt appears in list
- [ ] Verify prompt shows session name and "Session" scope indicator

### 1.3 View System Prompts
- [ ] View list of all prompts
- [ ] Verify global prompts are visible
- [ ] Verify session-scoped prompts are visible
- [ ] Filter by game system (if applicable)
- [ ] Filter by session (should show global + session-specific)
- [ ] Click on a prompt to view details
- [ ] Verify all fields are displayed correctly (title, content, scope, sessions, game_system, timestamps)

### 1.4 Edit System Prompt
- [ ] Select a prompt to edit
- [ ] Change the title
- [ ] Change the content
- [ ] Change scope from global to session (or vice versa)
- [ ] Add/remove sessions from session list
- [ ] Change game_system tag
- [ ] Save changes
- [ ] Verify changes are reflected in the list
- [ ] Verify updated_at timestamp changed

### 1.5 Delete System Prompt
- [ ] Select a prompt to delete
- [ ] Click delete button
- [ ] Confirm deletion
- [ ] Verify prompt is removed from list
- [ ] Verify prompt is no longer active in LLM calls

### 1.6 System Prompt Application (Global)
- [ ] Create a global prompt with specific instructions (e.g., "Always mention the page number when citing rules")
- [ ] Send a query to Rules Engine via chat interface
- [ ] Verify the response follows the global prompt instructions
- [ ] Switch to a different session
- [ ] Send another query
- [ ] Verify the global prompt still applies

### 1.7 System Prompt Application (Session-Scoped)
- [ ] Create a session-scoped prompt for Session A (e.g., "Use simplified combat rules")
- [ ] Create a different session-scoped prompt for Session B (e.g., "Use advanced combat rules")
- [ ] In chat interface, ensure current session is Session A
- [ ] Send a query about combat rules
- [ ] Verify response follows Session A prompt
- [ ] Switch to Session B in chat interface
- [ ] Send the same query about combat rules
- [ ] Verify response follows Session B prompt (different from Session A)

### 1.8 Multiple Prompts (Global + Session)
- [ ] Create a global prompt: "Always be concise"
- [ ] Create a session-scoped prompt for Session A: "Use technical terminology"
- [ ] Send a query from Session A
- [ ] Verify response is both concise (global) and uses technical terminology (session)
- [ ] Verify both prompts are combined correctly in the system prompt

### 1.9 Game System Filtering
- [ ] Create a prompt with game_system="D&D 5e"
- [ ] Create another prompt with game_system="Pathfinder"
- [ ] Send a query with game_system="D&D 5e" in the request
- [ ] Verify only D&D 5e prompt is applied
- [ ] Send a query with game_system="Pathfinder" in the request
- [ ] Verify only Pathfinder prompt is applied

### 1.10 Prompt Persistence
- [ ] Create a system prompt
- [ ] Restart the Rules Engine service container
- [ ] Verify prompt still exists after restart
- [ ] Verify prompt is still active in LLM calls

---

## Part 2: Game Master (Thoth) System Prompts

### 2.1 Create System Prompt (Global)
- [ ] Navigate to Game Master system prompts management UI
- [ ] Create a global prompt (e.g., "Always create vivid, immersive descriptions")
- [ ] Verify prompt is saved and appears in list

### 2.2 Create System Prompt (Session-Scoped)
- [ ] Create a session-scoped prompt (e.g., "This campaign is horror-themed")
- [ ] Verify prompt is saved with correct session association

### 2.3 System Prompt Application
- [ ] Create a global prompt: "Always include weather descriptions"
- [ ] Send a query to Game Master via chat interface
- [ ] Verify response includes weather descriptions
- [ ] Create a session-scoped prompt: "This session is set in a desert"
- [ ] Send a query from that session
- [ ] Verify response reflects desert setting

### 2.4 Edit and Delete
- [ ] Edit a Game Master prompt
- [ ] Verify changes are saved
- [ ] Delete a Game Master prompt
- [ ] Verify it's removed and no longer active

---

## Part 3: Rule File Associations

### 3.1 Associate Rule File with Game System
- [ ] Navigate to rule file management UI
- [ ] Select a rule file
- [ ] Set game_system field (e.g., "D&D 5e")
- [ ] Save association
- [ ] Verify game_system is displayed in file list
- [ ] Filter rules by game_system
- [ ] Verify only files with that game_system appear

### 3.2 Associate Rule File with Session
- [ ] Select a rule file
- [ ] Add session to session_ids array
- [ ] Save association
- [ ] Verify session is displayed in file metadata
- [ ] When querying from that session, verify the rule file is included in search
- [ ] When querying from a different session, verify the rule file is NOT included (unless also global)

### 3.3 Global Rule Files
- [ ] Verify rule files without session_ids are considered global
- [ ] Query from any session
- [ ] Verify global rule files are included in search results

### 3.4 Multiple Associations
- [ ] Associate a rule file with multiple sessions
- [ ] Verify it appears when querying from any of those sessions
- [ ] Verify it does NOT appear when querying from an unassociated session

### 3.5 Game System + Session Filtering
- [ ] Upload a D&D 5e rule file and associate it with Session A
- [ ] Upload a Pathfinder rule file and associate it with Session B
- [ ] Query from Session A with game_system="D&D 5e"
- [ ] Verify only D&D 5e file is searched
- [ ] Query from Session B with game_system="Pathfinder"
- [ ] Verify only Pathfinder file is searched

### 3.6 Rule File Association UI
- [ ] View rule file list
- [ ] Verify game_system is displayed for each file
- [ ] Verify session associations are displayed
- [ ] Edit a file's associations
- [ ] Verify changes are saved
- [ ] Remove a file's game_system association
- [ ] Verify it becomes "global" (no game system filter)

---

## Part 4: Integration Testing

### 4.1 Combined System Prompts + Rule Files
- [ ] Create a global system prompt: "Always cite page numbers"
- [ ] Associate a rule file with a specific session
- [ ] Query from that session
- [ ] Verify response:
  - Follows the system prompt (cites page numbers)
  - Uses the session-associated rule file in search

### 4.2 Multi-Service Context
- [ ] Create a system prompt for Rules Engine: "Use D&D 5e rules"
- [ ] Create a system prompt for Game Master: "Narrative style: dark fantasy"
- [ ] Query Rules Engine from a session
- [ ] Verify D&D 5e prompt is applied
- [ ] Query Game Master from the same session
- [ ] Verify dark fantasy prompt is applied
- [ ] Verify prompts are independent per service

### 4.3 Session Switching
- [ ] Create session-scoped prompts for Session A and Session B
- [ ] Associate different rule files with each session
- [ ] Query from Session A
- [ ] Verify Session A prompts and rules are used
- [ ] Switch to Session B in UI
- [ ] Query from Session B
- [ ] Verify Session B prompts and rules are used

### 4.4 Game System Switching
- [ ] Create prompts tagged with different game systems
- [ ] Associate rule files with different game systems
- [ ] Query with game_system="D&D 5e"
- [ ] Verify D&D 5e prompts and rules are used
- [ ] Query with game_system="Pathfinder"
- [ ] Verify Pathfinder prompts and rules are used

---

## Part 5: Edge Cases & Error Handling

### 5.1 Invalid Session ID
- [ ] Try to create a prompt with an invalid session_id
- [ ] Verify appropriate error message
- [ ] Verify prompt is not created

### 5.2 Empty Content
- [ ] Try to create a prompt with empty title
- [ ] Verify validation error
- [ ] Try to create a prompt with empty content
- [ ] Verify validation error

### 5.3 Non-Existent Prompt
- [ ] Try to get/edit/delete a non-existent prompt_id
- [ ] Verify 404 error response

### 5.4 Unauthorized Access
- [ ] Log in as non-GM user
- [ ] Try to access system prompt endpoints
- [ ] Verify 403 Forbidden error

### 5.5 Database Persistence
- [ ] Create multiple prompts
- [ ] Stop and remove the service container
- [ ] Restart the service
- [ ] Verify all prompts are still present
- [ ] Verify prompts are still functional

### 5.6 Large Content
- [ ] Create a prompt with very long content (e.g., 10,000 characters)
- [ ] Verify it's saved correctly
- [ ] Verify it's applied correctly in LLM calls
- [ ] Edit the prompt
- [ ] Verify changes are saved

### 5.7 Special Characters
- [ ] Create a prompt with special characters (quotes, newlines, unicode)
- [ ] Verify it's saved correctly
- [ ] Verify it's displayed correctly in UI
- [ ] Verify it's applied correctly in LLM calls

---

## Part 6: Performance Testing

### 6.1 Many Prompts
- [ ] Create 50+ system prompts (mix of global and session-scoped)
- [ ] Query the LLM
- [ ] Verify response time is acceptable (< 5 seconds)
- [ ] Verify all relevant prompts are combined correctly

### 6.2 Many Rule Files
- [ ] Upload 20+ rule files
- [ ] Associate them with different sessions/game systems
- [ ] Query from a session
- [ ] Verify search performance is acceptable
- [ ] Verify only relevant files are searched

### 6.3 Concurrent Queries
- [ ] Send multiple queries simultaneously from different sessions
- [ ] Verify each query uses the correct prompts and rules
- [ ] Verify no cross-contamination between sessions

---

## Part 7: UI/UX Testing

### 7.1 System Prompts UI
- [ ] Verify UI is intuitive and easy to use
- [ ] Verify all CRUD operations work smoothly
- [ ] Verify scope selector is clear (global vs session)
- [ ] Verify session selector works correctly
- [ ] Verify game_system input is clear
- [ ] Verify prompt list is readable and well-formatted
- [ ] Verify edit/delete actions have confirmation dialogs

### 7.2 Rule File Association UI
- [ ] Verify game_system field is easy to set
- [ ] Verify session association UI is intuitive
- [ ] Verify multiple session selection works
- [ ] Verify associations are clearly displayed
- [ ] Verify filtering by game_system works
- [ ] Verify filtering by session works

### 7.3 Active Prompts Display
- [ ] Verify UI shows which prompts are active for current session
- [ ] Verify UI shows which rule files are active for current session
- [ ] Verify indicators are clear (global vs session-scoped)
- [ ] Verify game_system tags are visible

### 7.4 Responsive Design
- [ ] Test UI on different screen sizes
- [ ] Verify all features are accessible on mobile/tablet
- [ ] Verify modals and dialogs work on small screens

---

## Part 8: API Testing (Optional - for developers)

### 8.1 Rules Engine Prompts API
- [ ] Test POST /prompts (create)
- [ ] Test GET /prompts (list with filters)
- [ ] Test GET /prompts/{prompt_id} (get one)
- [ ] Test PATCH /prompts/{prompt_id} (update)
- [ ] Test DELETE /prompts/{prompt_id} (delete)
- [ ] Verify all endpoints require GM authentication
- [ ] Verify response models match expected schema

### 8.2 Game Master Prompts API
- [ ] Test all CRUD endpoints
- [ ] Verify endpoints are independent from Rules Engine

### 8.3 Rule File Metadata API
- [ ] Test updating game_system field
- [ ] Test updating session_ids array
- [ ] Verify changes persist
- [ ] Verify filtering works in search endpoints

---

## Test Completion Checklist

- [ ] All Part 1 tests passed (Rules Engine prompts)
- [ ] All Part 2 tests passed (Game Master prompts)
- [ ] All Part 3 tests passed (Rule file associations)
- [ ] All Part 4 tests passed (Integration)
- [ ] All Part 5 tests passed (Edge cases)
- [ ] All Part 6 tests passed (Performance)
- [ ] All Part 7 tests passed (UI/UX)
- [ ] Part 8 tests passed (API - if applicable)

## Notes
- Document any bugs or issues found during testing
- Note any performance concerns
- Record any UI/UX improvements needed
- Keep track of which features work well and which need refinement


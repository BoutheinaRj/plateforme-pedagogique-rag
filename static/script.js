// Astro KB Web Interface - JavaScript

const API_BASE = '/api';
let answerConversation = [];

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatMultilineText(value) {
    return escapeHtml(value).replace(/\n/g, '<br>');
}

function renderConversation() {
    const chatDiv = document.getElementById('answer-chat');
    if (!chatDiv) return;

    if (!answerConversation.length) {
        chatDiv.innerHTML = `
            <div class="chat-empty">
                <div class="chat-empty-art" aria-hidden="true">
                    <svg class="sticker chat-empty-owl"><use href="#stk-robot"/></svg>
                    <svg class="sticker chat-empty-cloud"><use href="#stk-cloud"/></svg>
                    <svg class="sticker chat-empty-star"><use href="#stk-star"/></svg>
                </div>
                <strong>Coucou&nbsp;! Prêt à apprendre&nbsp;?</strong>
                <p>Écris ta question en bas ou choisis une idée magique pour commencer.</p>
            </div>
        `;
        return;
    }

    const html = answerConversation.map((turn) => {
        const isUser = turn.role === 'user';
        const roleLabel = isUser ? "Moi" : "DOOBY";
        const isPending = !isUser && turn.content === 'Génération en cours...';
        const textHtml = isPending
            ? '<div class="typing" aria-label="Génération en cours"><em>DOOBY réfléchit</em><span></span><span></span><span></span></div>'
            : formatMultilineText(turn.content);
        const avatarHtml = isUser
            ? '<span class="chat-avatar-emoji">🧒</span>'
            : '<svg class="sticker"><use href="#stk-robot"/></svg>';
        const bubbleClass = isUser ? 'chat-bubble user' : 'chat-bubble assistant';
        const meta = !isUser && turn.meta
            ? `<div class="chat-meta">Mode: ${escapeHtml(turn.meta.mode || 'n/a')} | Version: ${escapeHtml(turn.meta.pedagogical_mode || 'answer')}</div>`
            : '';

        return `
            <div class="chat-row ${isUser ? 'user' : 'assistant'}">
                <div class="chat-avatar" aria-hidden="true">${avatarHtml}</div>
                <div class="${bubbleClass}">
                    <div class="chat-role">${roleLabel}</div>
                    <div class="chat-text">${textHtml}</div>
                    ${meta}
                </div>
            </div>
        `;
    }).join('');

    chatDiv.innerHTML = html;
    chatDiv.scrollTop = chatDiv.scrollHeight;
}

function getLanguageLabel(language) {
    if (language === 'ar') return '🇸🇦 Arabe';
    if (language === 'en') return '🇬🇧 English';
    return '🇫🇷 Français';
}

// Tab Switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        
        // Update active button
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Update active tab
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(tab).classList.add('active');
        
        // Load tab content
        if (tab === 'stats') loadStats();
        if (tab === 'chunks') loadChunks();
    });
});

// Check Health
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        
        const indicator = document.getElementById('status-indicator');
        const text = document.getElementById('status-text');
        
        if (data.status === 'ok') {
            indicator.classList.add('connected');
            indicator.classList.remove('disconnected');
            text.textContent = `Connecté (${data.chunks_count} chunks)`;
            document.getElementById('footer-chunks').textContent = data.chunks_count;
        } else {
            indicator.classList.remove('connected');
            indicator.classList.add('disconnected');
            text.textContent = 'Déconnecté';
        }
    } catch (error) {
        const indicator = document.getElementById('status-indicator');
        indicator.classList.add('disconnected');
        document.getElementById('status-text').textContent = 'Erreur de connexion';
    }
}

// Load Stats
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        
        // Update numbers
        document.getElementById('total-chunks').textContent = data.total_chunks;
        document.getElementById('total-grades').textContent = Object.keys(data.by_grade).length;
        document.getElementById('total-subjects').textContent = Object.keys(data.by_subject).length;
        document.getElementById('total-languages').textContent = Object.keys(data.by_language || {}).length;
        
        // Stats by grade
        const gradeHtml = Object.entries(data.by_grade)
            .sort()
            .map(([grade, count]) => `
                <div class="stat-row">
                    <span class="stat-label-text">Grade ${grade}</span>
                    <span class="stat-value">${count} chunks</span>
                </div>
            `).join('');
        document.getElementById('stats-by-grade').innerHTML = gradeHtml || '<p>Aucune donnée</p>';
        
        // Stats by subject
        const subjectHtml = Object.entries(data.by_subject)
            .sort((a, b) => b[1] - a[1])
            .map(([subject, count]) => `
                <div class="stat-row">
                    <span class="stat-label-text">${subject}</span>
                    <span class="stat-value">${count} chunks</span>
                </div>
            `).join('');
        document.getElementById('stats-by-subject').innerHTML = subjectHtml || '<p>Aucune donnée</p>';
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Perform Search
async function performSearch() {
    const query = document.getElementById('search-query').value;
    const grade = document.getElementById('search-grade').value;
    const language = document.getElementById('search-language').value;
    const limit = document.getElementById('search-limit').value;
    
    if (!query) {
        alert('Veuillez entrer une requête');
        return;
    }
    
    const resultsDiv = document.getElementById('search-results');
    resultsDiv.innerHTML = '<div class="loading"></div> Recherche...';
    
    try {
        const response = await fetch(`${API_BASE}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                query, 
                grade, 
                language, 
                limit,
                mode: 'hybrid'  // Use both semantic and keyword
            })
        });
        
        const data = await response.json();
        
        if (data.results.length === 0) {
            resultsDiv.innerHTML = '<div class="error">❌ Aucun résultat trouvé</div>';
            return;
        }
        
        const html = `
            <div class="result-header">
                <h4>✅ ${data.results_count} résultats trouvés pour "${query}"</h4>
                <small>Mode: ${data.search_mode}</small>
            </div>
            ${data.results.map(result => `
                <div class="result-item">
                    <div class="result-header">
                        <div>
                            <div class="chunk-id">${result.chunk_id}</div>
                            <div class="result-meta">
                                <span class="badge">Grade ${result.grade}</span>
                                <span class="badge">${result.subject}</span>
                                <span class="badge">${getLanguageLabel(result.language)}</span>
                                <span class="badge" style="background: ${result.mode === 'semantic' ? '#10b981' : '#f59e0b'}">
                                    ${result.mode === 'semantic' ? '🧠 Sémantique' : '🔍 Mot-clé'}
                                </span>
                                ${result.score ? `<span class="badge" style="background: #8b5cf6">Score: ${(result.score * 100).toFixed(0)}%</span>` : ''}
                            </div>
                        </div>
                    </div>
                    <div class="result-text">${result.text}</div>
                </div>
            `).join('')}
        `;
        resultsDiv.innerHTML = html;
    } catch (error) {
        resultsDiv.innerHTML = `<div class="error">❌ Erreur: ${error.message}</div>`;
    }
}

// Generate Answer
async function generateAnswer() {
    const question = document.getElementById('question-input').value;
    const grade = document.getElementById('answer-grade').value || null;
    const language = document.getElementById('answer-language').value;
    
    if (!question) {
        alert('Veuillez entrer une question');
        return;
    }
    
    const resultDiv = document.getElementById('answer-result');
    const trimmedQuestion = question.trim();
    answerConversation.push({ role: 'user', content: trimmedQuestion });
    answerConversation.push({ role: 'assistant', content: 'Génération en cours...' });
    renderConversation();
    
    try {
        const response = await fetch(`${API_BASE}/answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: trimmedQuestion,
                grade,
                language,
                conversation: answerConversation
            })
        });
        
        const data = await response.json();

        const formatDisplayChunkId = (source) => {
            let displayId = source.chunk_id || 'chunk inconnu';
            if (source.language === 'ar' && displayId.includes('_fr_')) {
                displayId = displayId.replace('_fr_', '_ar_');
            }
            return displayId;
        };
        
        const sources = Array.isArray(data.sources) ? data.sources : [];
        const sourcesHtml = sources.length > 0 ? `
            <div class="sources">
                <h5>📚 Sources Utilisées:</h5>
                ${sources.map(source => `
                    <div class="source-item">
                        <strong>${escapeHtml(source.subject || 'Cours')} (Grade ${escapeHtml(source.grade)})</strong>
                        <div><small>${escapeHtml(formatDisplayChunkId(source))} | ${escapeHtml(source.source_file || 'fichier inconnu')} | ${escapeHtml(source.source_type || 'source inconnue')}</small></div>
                        <p>${formatMultilineText((source.text || '').substring(0, 200))}...</p>
                    </div>
                `).join('')}
            </div>
        ` : '';

        const promptPreviewHtml = data.prompt_preview ? `
            <div class="sources">
                <h5>🧪 Prompt de démonstration</h5>
                <div class="source-item">
                    <strong>System</strong>
                    <p>${formatMultilineText(data.prompt_preview.system)}</p>
                </div>
                <div class="source-item">
                    <strong>User</strong>
                    <p>${formatMultilineText(data.prompt_preview.user)}</p>
                </div>
            </div>
        ` : '';

        const llmErrorHtml = data.llm_error ? `
            <div class="sources">
                <h5>⚠️ Détail LLM</h5>
                <div class="source-item">
                    <p>${escapeHtml(data.llm_error)}</p>
                </div>
            </div>
        ` : '';

        const pedagogicalLabel = data.pedagogical_mode
            ? `<span class="badge" style="background:#2563eb">Version: ${data.pedagogical_mode}</span>`
            : '';
        
        const html = `
            <details class="answer-box">
                <summary>🔎 Détails de la réponse <small>(Mode: ${escapeHtml(data.mode)}, Recherche: ${escapeHtml(data.retrieval_mode)})</small></summary>
                <div class="answer-box-body">
                    <div class="result-meta" style="margin-bottom: 8px;">${pedagogicalLabel}</div>
                    <div class="answer-text">${formatMultilineText(data.answer)}</div>
                    ${llmErrorHtml}
                    ${sourcesHtml}
                    ${promptPreviewHtml}
                </div>
            </details>
        `;
        resultDiv.innerHTML = html;

        answerConversation.pop();
        answerConversation.push({
            role: 'assistant',
            content: (data.answer || '').trim(),
            meta: {
                mode: data.mode,
                pedagogical_mode: data.pedagogical_mode,
            }
        });
        if (answerConversation.length > 12) {
            answerConversation = answerConversation.slice(-12);
        }
        renderConversation();
        document.getElementById('question-input').value = '';
    } catch (error) {
        answerConversation.pop();
        answerConversation.push({
            role: 'assistant',
            content: `Erreur: ${error.message}`,
            meta: { mode: 'error', pedagogical_mode: 'answer' }
        });
        renderConversation();
        resultDiv.innerHTML = `<div class="error">❌ Erreur: ${error.message}</div>`;
    }
}

function resetAnswerConversation() {
    answerConversation = [];
    document.getElementById('answer-result').innerHTML = '';
    renderConversation();
}

// Load Chunks
async function loadChunks() {
    const grade = document.getElementById('chunks-grade').value;
    const language = document.getElementById('chunks-language').value;
    const limit = document.getElementById('chunks-limit').value;
    
    const chunksList = document.getElementById('chunks-list');
    chunksList.innerHTML = '<div class="loading"></div> Chargement...';
    
    try {
        const url = new URL(`${API_BASE}/chunks`);
        if (grade) url.searchParams.append('grade', grade);
        if (language) url.searchParams.append('language', language);
        url.searchParams.append('limit', limit);
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.chunks.length === 0) {
            chunksList.innerHTML = '<div class="error">❌ Aucun chunk trouvé</div>';
            return;
        }
        
        const html = data.chunks.map(chunk => `
            <div class="chunk-card" onclick="viewChunkDetail('${chunk.chunk_id}')">
                <div class="chunk-id">📄 ${chunk.chunk_id}</div>
                <div class="chunk-meta">
                    <span class="badge">Grade ${chunk.grade}</span>
                    <span class="badge">${chunk.subject}</span>
                    <span class="badge">${getLanguageLabel(chunk.language)}</span>
                </div>
                <div class="chunk-text">${chunk.text}</div>
            </div>
        `).join('');
        
        chunksList.innerHTML = `
            <div class="result-header">
                <h4>📚 ${data.total} chunks disponibles</h4>
            </div>
            ${html}
        `;
    } catch (error) {
        chunksList.innerHTML = `<div class="error">❌ Erreur: ${error.message}</div>`;
    }
}

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    loadStats();
    renderConversation();
    
    // Check health every 10 seconds
    setInterval(checkHealth, 10000);
    
    // Allow Enter key for search
    document.getElementById('search-query').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    
    // Allow Enter key for answer (Ctrl+Enter)
    document.getElementById('question-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) generateAnswer();
    });

    // Voice button: visual demo only (no audio is captured)
    const voiceBtn = document.getElementById('voice-btn');
    if (voiceBtn) {
        const voiceBox = voiceBtn.closest('.composer-input');
        const voiceTime = voiceBox.querySelector('.voice-time');
        let voiceTimer = null;

        const stopListening = () => {
            clearInterval(voiceTimer);
            voiceBox.classList.remove('is-listening');
            voiceBtn.setAttribute('aria-pressed', 'false');
        };

        voiceBtn.addEventListener('click', () => {
            if (voiceBox.classList.contains('is-listening')) {
                stopListening();
                return;
            }
            let seconds = 0;
            voiceTime.textContent = '0:00';
            voiceBox.classList.add('is-listening');
            voiceBtn.setAttribute('aria-pressed', 'true');
            voiceTimer = setInterval(() => {
                seconds += 1;
                voiceTime.textContent = `0:${String(seconds).padStart(2, '0')}`;
                if (seconds >= 15) stopListening();
            }, 1000);
        });
    }

    // Idea chips fill the question box
    document.querySelectorAll('.idea-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const input = document.getElementById('question-input');
            input.value = chip.dataset.q;
            input.focus();
        });
    });
});

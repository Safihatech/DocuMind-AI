const uploadInput = document.getElementById('upload-input');
const uploadButton = document.getElementById('upload-button');
const uploadSidebarButton = document.getElementById('upload-sidebar-button');
const uploadDropbox = document.getElementById('upload-dropbox');
const uploadStatus = document.getElementById('upload-status');
const welcomeScreen = document.getElementById('welcome-screen');
const chatPanel = document.getElementById('chat-panel');
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const sendButton = document.getElementById('send-button');
const newChatButton = document.getElementById('new-chat-btn');
const historyList = document.getElementById('history-list');
const documentsList = document.getElementById('documents-list');
const documentCount = document.getElementById('document-count');
const activeDocumentName = document.getElementById('active-document-name');
const toastContainer = document.getElementById('toast-container');
const modelSelect = document.getElementById('model-select');
if (modelSelect) {
  modelSelect.value = 'mistral-saba-24b';
}
const sectionToggles = document.querySelectorAll('.section-toggle');

let documents = [];
let sessions = [];
let activeSessionId = null;
let activeDocumentId = null;
let uploadedDocument = false;
let documentsCollapsed = false;
let historyCollapsed = false;

function toggleSection(section) {
  if (section === 'documents') {
    documentsCollapsed = !documentsCollapsed;
    document.getElementById('documents-list').classList.toggle('collapsed', documentsCollapsed);
  }
  if (section === 'history') {
    historyCollapsed = !historyCollapsed;
    document.getElementById('history-list').classList.toggle('collapsed', historyCollapsed);
  }
  sectionToggles.forEach((button) => {
    if (button.dataset.section === section) {
      button.classList.toggle('collapsed', section === 'documents' ? documentsCollapsed : historyCollapsed);
    }
  });
}

const STORAGE_KEY = 'documind_state_v1';

function saveState() {
  const state = { documents, sessions, activeSessionId, activeDocumentId };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn('Could not save state:', error);
  }
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const state = JSON.parse(raw);
    if (!state) return;
    documents = Array.isArray(state.documents) ? state.documents : [];
    sessions = Array.isArray(state.sessions) ? state.sessions : [];
    activeSessionId = state.activeSessionId || (sessions[0] && sessions[0].id) || null;
    activeDocumentId = state.activeDocumentId || (documents[0] && documents[0].id) || null;
  } catch (error) {
    console.warn('Could not load state:', error);
  }
}

function formatTimestamp() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  toastContainer.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('visible'));
  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 250);
  }, 3000);
}

function setUploadStatus(text, status) {
  uploadStatus.textContent = text;
  uploadStatus.className = 'upload-status';
  if (status) uploadStatus.classList.add(status);
  uploadStatus.classList.remove('hidden');
}

function clearUploadStatus() {
  uploadStatus.textContent = '';
  uploadStatus.className = 'upload-status hidden';
}

function getSession(id) {
  return sessions.find((session) => session.id === id);
}

function createNewSession(documentId = activeDocumentId, silent = false) {
  const id = `session-${Date.now()}`;
  const title = `Chat ${sessions.length + 1}`;
  const session = { id, documentId, title, messages: [], lastMessage: 'Start chatting' };
  sessions.unshift(session);
  activeSessionId = id;
  if (!silent) {
    renderHistory();
    renderChat();
  }
  saveState();
  return id;
}

function setActiveDocument(docId, preserveSession = false) {
  const doc = documents.find((item) => item.id === docId);
  if (!doc) return;
  activeDocumentId = docId;
  activeDocumentName.textContent = doc.name;
  if (!preserveSession || !activeSessionId || getSession(activeSessionId)?.documentId !== docId) {
    const existingSession = sessions.find((session) => session.documentId === docId);
    if (existingSession) {
      activeSessionId = existingSession.id;
    } else {
      createNewSession(docId, true);
    }
  }
  updateUI();
}

function setActiveSession(sessionId) {
  const session = getSession(sessionId);
  if (!session) return;
  activeSessionId = sessionId;
  if (session.documentId) {
    activeDocumentId = session.documentId;
    activeDocumentName.textContent = documents.find((doc) => doc.id === session.documentId)?.name || '';
  }
  updateUI();
}

function deleteDocument(documentId) {
  documents = documents.filter((doc) => doc.id !== documentId);
  sessions = sessions.filter((session) => session.documentId !== documentId);
  if (activeDocumentId === documentId) {
    activeDocumentId = documents[0]?.id || null;
    activeSessionId = sessions.find((session) => session.documentId === activeDocumentId)?.id || null;
  }
  updateUI();
  showToast('Document removed.', 'warning');
}

function deleteSession(sessionId) {
  sessions = sessions.filter((session) => session.id !== sessionId);
  if (activeSessionId === sessionId) {
    activeSessionId = sessions[0]?.id || null;
    activeDocumentId = sessions.find((session) => session.id === activeSessionId)?.documentId || activeDocumentId;
  }
  updateUI();
  showToast('Chat removed.', 'warning');
}

function renderDocuments() {
  documentsList.innerHTML = '';
  documents.forEach((doc) => {
    const item = document.createElement('div');
    item.className = `document-item${doc.id === activeDocumentId ? ' active' : ''}`;
    const info = document.createElement('div');
    info.className = 'document-info';
    info.innerHTML = `
      <span class="document-name">${doc.name}</span>
      <span class="document-status">${doc.status}</span>
    `;
    const icon = document.createElement('div');
    icon.className = 'document-icon';
    icon.textContent = '📄';
    const actions = document.createElement('div');
    actions.className = 'item-actions';
    const deleteButton = document.createElement('button');
    deleteButton.className = 'list-delete-button';
    deleteButton.type = 'button';
    deleteButton.textContent = '×';
    deleteButton.title = 'Delete document';
    deleteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      deleteDocument(doc.id);
    });
    actions.appendChild(deleteButton);
    item.addEventListener('click', () => setActiveDocument(doc.id));
    item.appendChild(icon);
    item.appendChild(info);
    item.appendChild(actions);
    documentsList.appendChild(item);
  });
  documentCount.textContent = documents.length;
  document.getElementById('documents-list').classList.toggle('collapsed', documentsCollapsed);
}

function renderHistory() {
  historyList.innerHTML = '';
  sessions.forEach((session) => {
    const item = document.createElement('div');
    item.className = `history-item${session.id === activeSessionId ? ' active' : ''}`;
    const text = document.createElement('div');
    text.className = 'history-text';
    text.innerHTML = `<strong>${session.title}</strong><span>${session.lastMessage || 'Start chatting'}</span>`;
    const actions = document.createElement('div');
    actions.className = 'item-actions';
    const deleteButton = document.createElement('button');
    deleteButton.className = 'list-delete-button';
    deleteButton.type = 'button';
    deleteButton.textContent = '×';
    deleteButton.title = 'Delete chat';
    deleteButton.addEventListener('click', (event) => {
      event.stopPropagation();
      deleteSession(session.id);
    });
    actions.appendChild(deleteButton);
    item.addEventListener('click', () => setActiveSession(session.id));
    item.appendChild(text);
    item.appendChild(actions);
    historyList.appendChild(item);
  });
  document.getElementById('history-list').classList.toggle('collapsed', historyCollapsed);
}

function createMessageElement(message) {
  const row = document.createElement('div');
  row.className = `message-row ${message.sender}`;
  if (message.sender === 'assistant') {
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'DM';
    row.appendChild(avatar);
  }
  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';
  if (message.typing) {
    const typing = document.createElement('div');
    typing.className = 'typing-indicator';
    typing.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
    bubble.appendChild(typing);
  } else {
    bubble.textContent = message.text;
  }
  const meta = document.createElement('div');
  meta.className = 'message-meta';
  meta.textContent = formatTimestamp();
  bubble.appendChild(meta);
  row.appendChild(bubble);
  return row;
}

function renderChat() {
  chatMessages.innerHTML = '';
  const session = getSession(activeSessionId);
  if (!session) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = documents.length ? 'Ask a question about your uploaded document.' : 'Upload a document to start chatting.';
    chatMessages.appendChild(empty);
    return;
  }
  if (!session.messages.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = 'Ask a question about your uploaded document.';
    chatMessages.appendChild(empty);
  } else {
    session.messages.forEach((message) => chatMessages.appendChild(createMessageElement(message)));
  }
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showWelcome() {
  welcomeScreen.classList.remove('hidden');
  chatPanel.classList.add('hidden');
}

function showChatPanel() {
  welcomeScreen.classList.add('hidden');
  chatPanel.classList.remove('hidden');
}

function updateUI() {
  renderDocuments();
  renderHistory();
  const hasDocument = documents.length > 0;
  if (hasDocument && activeDocumentId) {
    showChatPanel();
  } else {
    showWelcome();
  }
  chatInput.disabled = !hasDocument;
  sendButton.disabled = !hasDocument;
  if (!hasDocument) {
    activeDocumentName.textContent = '';
  }
  if (!activeSessionId && activeDocumentId) createNewSession(activeDocumentId, true);
  renderChat();
  saveState();
}

function addMessage(session, text, sender, options = {}) {
  const message = { sender, text, timestamp: Date.now(), typing: !!options.typing };
  session.messages.push(message);
  if (sender === 'user') {
    session.lastMessage = text.length > 60 ? `${text.slice(0, 56)}…` : text;
    if (session.title && session.title.startsWith('Chat')) {
      session.title = text.split(' ').slice(0, 7).join(' ') || session.title;
    }
  }
  saveState();
}

function replaceTypingWithAnswer(session, answer) {
  const typingIndex = [...session.messages].reverse().findIndex((message) => message.sender === 'assistant' && message.typing);
  if (typingIndex !== -1) {
    const index = session.messages.length - 1 - typingIndex;
    session.messages[index] = { sender: 'assistant', text: answer, timestamp: Date.now(), typing: false };
  } else {
    addMessage(session, answer, 'assistant');
  }
  saveState();
}

async function uploadDocument(file) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  const formData = new FormData();
  formData.append('file', file);
  let response;
  try {
    response = await fetch('/documents/upload', { method: 'POST', body: formData, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || 'Upload failed. Please try again.');
  }
  return response.json();
}

async function pollDocumentStatus(documentId, onUpdate, timeoutMs = 60000, intervalMs = 2000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(`/documents/status/${documentId}`);
      if (!response.ok) {
        const text = await response.text().catch(() => null);
        onUpdate({ status: 'error', message: text || `Status ${response.status}` });
        return;
      }
      const data = await response.json();
      const status = data?.status?.status || data?.status;
      if (status === 'indexed') {
        onUpdate({ status: 'indexed', chunks: data?.status?.chunks });
        return;
      }
      if (status === 'failed') {
        onUpdate({ status: 'failed', message: data?.status?.message || 'failed' });
        return;
      }
      onUpdate({ status: 'processing' });
    } catch (error) {
      onUpdate({ status: 'error', message: String(error) });
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  onUpdate({ status: 'timeout', message: 'Timeout waiting for document status' });
}

function handleFile(file) {
  if (!file) return;
  const extension = file.name.split('.').pop()?.toLowerCase();
  const allowed = ['txt', 'pdf', 'md'];
  if (!extension || !allowed.includes(extension)) {
    showToast('Only PDF, TXT, and MD files are supported.', 'error');
    return;
  }
  setUploadStatus('Uploading and processing document...', 'loading');
  showToast('Uploading and processing document...', 'info');
  uploadDocument(file)
    .then((data) => {
      const returnedDocumentId = data?.document_id || data?.files?.[0]?.document_id;
      const documentId = returnedDocumentId || Date.now();
      const filename = data?.files?.[0]?.filename || file.name;
      documents.unshift({ id: String(documentId), name: filename, status: 'Processing', fileId: documentId });
      activeDocumentId = String(documentId);
      activeDocumentName.textContent = filename;
      createNewSession(activeDocumentId, true);
      updateUI();
      showToast('Document uploaded successfully!', 'success');
      setUploadStatus(`Uploaded ${filename}. Processing document...`, 'success');
      const session = getSession(activeSessionId);
      addMessage(session, '', 'assistant', { typing: true });
      renderChat();
      if (returnedDocumentId) {
        uploadedDocument = true;
        pollDocumentStatus(returnedDocumentId, (statusUpdate) => {
          const doc = documents.find((item) => item.fileId === returnedDocumentId);
          if (statusUpdate.status === 'processing') {
            setUploadStatus(`Indexing ${filename}...`, 'loading');
          } else if (statusUpdate.status === 'indexed') {
            if (doc) doc.status = 'Ready';
            setUploadStatus('Document uploaded successfully!', 'success');
            replaceTypingWithAnswer(session, `I've read ${filename}. Ask me questions about it.`);
            renderDocuments();
            renderChat();
          } else {
            if (doc) doc.status = 'Failed';
            const message = statusUpdate.message ? `: ${statusUpdate.message}` : '';
            setUploadStatus(`Upload failed${message}`, 'error');
            replaceTypingWithAnswer(session, `Indexing failed for ${filename}${message}. Please try again.`);
            showToast(`Upload failed${message}`, 'error');
            renderDocuments();
            renderChat();
          }
        });
      }
    })
    .catch((error) => {
      setUploadStatus('Upload failed. Please try again.', 'error');
      showToast(error.message || 'Upload failed. Please try again.', 'error');
    });
}

async function fetchAnswer(question) {
  const docId = activeDocumentId ? parseInt(activeDocumentId, 10) : null;
  const payload = { query: question, model: modelSelect.value, top_k: 5, use_hybrid: true, document_id: docId };
  const response = await fetch('/qa/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || data?.message || `Server error: ${response.status}`);
  }
  const data = await response.json();
  console.log('QA response', data);
  return data.answer || 'No answer returned.';
}

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;
  if (!documents.length) {
    showToast('Please upload a document first.', 'warning');
    return;
  }
  chatInput.value = '';
  const session = getSession(activeSessionId) || createNewSession(activeDocumentId, true);
  addMessage(session, question, 'user');
  addMessage(session, '', 'assistant', { typing: true });
  renderChat();
  sendButton.disabled = true;
  try {
    const answer = await fetchAnswer(question);
    replaceTypingWithAnswer(session, answer);
    renderChat();
  } catch (error) {
    replaceTypingWithAnswer(session, error.message || 'Unable to fetch answer.');
    showToast(error.message || 'Unable to fetch answer.', 'error');
    renderChat();
  } finally {
    sendButton.disabled = false;
  }
});

uploadButton.addEventListener('click', () => uploadInput.click());
uploadSidebarButton.addEventListener('click', () => uploadInput.click());
uploadDropbox.addEventListener('click', () => uploadInput.click());

sectionToggles.forEach((button) => {
  button.addEventListener('click', () => toggleSection(button.dataset.section));
});

uploadDropbox.addEventListener('dragover', (event) => {
  event.preventDefault();
  uploadDropbox.classList.add('drag-over');
});
uploadDropbox.addEventListener('dragleave', () => uploadDropbox.classList.remove('drag-over'));
uploadDropbox.addEventListener('drop', (event) => {
  event.preventDefault();
  uploadDropbox.classList.remove('drag-over');
  const file = event.dataTransfer.files[0];
  if (file) handleFile(file);
});

uploadInput.addEventListener('change', () => {
  const file = uploadInput.files && uploadInput.files[0];
  if (file) handleFile(file);
});

newChatButton.addEventListener('click', () => {
  if (documents.length) {
    createNewSession(activeDocumentId);
    showWelcome();
    renderChat();
    renderHistory();
    showToast('New chat started. Ask a fresh question.', 'info');
  } else {
    showWelcome();
    showToast('Upload a document to start a new chat.', 'info');
  }
});

function init() {
  loadState();
  if (documents.length > 0 && !activeDocumentId) activeDocumentId = documents[0].id;
  updateUI();
}

init();

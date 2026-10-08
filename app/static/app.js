'use strict';
const $ = id => document.getElementById(id);
let key = sessionStorage.getItem('rag-key') || '';
let chats = [];
try { chats = JSON.parse(localStorage.getItem('rag-chats') || '[]'); if (!Array.isArray(chats)) chats = []; } catch { chats = []; }
let current = null, mode = 'rag', busy = false, controller = null;
const welcome = $('welcome').cloneNode(true);
let toastTimer;
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 7000); }
function save() { try { localStorage.setItem('rag-chats', JSON.stringify(chats)); } catch { toast('Browser storage is full. Export a chat, then clear older conversations.'); } renderHistory(); }
async function api(path, options = {}) {
 const response = await fetch(path, {...options, headers: {Authorization: 'Bearer ' + key, ...options.headers}});
 if (!response.ok) { let message = 'Request failed (' + response.status + ').'; try { const e = await response.json(); if (typeof e.detail === 'string') message = e.detail; } catch {} if(response.status === 401) $('settings-dialog').showModal(); throw new Error(message); }
 return response;
}
function renderHistory() {
 $('history').replaceChildren();
 if (!chats.length) { const p = document.createElement('p'); p.className = 'empty-history'; p.textContent = 'A fresh start. Ask anything.'; $('history').append(p); }
 for (const chat of [...chats].reverse()) {
  const row = document.createElement('div'); row.className = 'history-item' + (current === chat.id ? ' selected' : '');
  const button = document.createElement('button'); button.className = 'title'; button.textContent = chat.title; button.title = chat.title;
  button.onclick = () => { if (busy) return; current = chat.id; setMode(chat.mode); renderMessages(); renderHistory(); document.body.classList.remove('sidebar-open'); };
  const remove = document.createElement('button'); remove.className = 'remove'; remove.textContent = '×'; remove.setAttribute('aria-label', 'Delete ' + chat.title);
  remove.onclick = () => { if (busy || !confirm('Delete this saved conversation?')) return; chats = chats.filter(c => c.id !== chat.id); if (current === chat.id) current = null; save(); renderMessages(); };
  row.append(button, remove); $('history').append(row);
 }
}
function renderText(node, text) {
 node.replaceChildren();
 // Render fenced code using textContent; never execute model HTML or Markdown links.
 const parts = text.split(/```/g);
 parts.forEach((part, i) => { if (i % 2) { const pre = document.createElement('pre'); const code = document.createElement('code'); code.textContent = part.replace(/^\w+\n/, ''); pre.append(code); node.append(pre); } else { node.append(document.createTextNode(part)); } });
}
function messageElement(message) {
 const article = document.createElement('article'); article.className = 'message ' + message.role;
 if (message.role === 'assistant') { const label = document.createElement('div'); label.className = 'message-label'; label.textContent = message.model || 'Assistant'; article.append(label); }
 const content = document.createElement('div'); content.className = 'message-content'; renderText(content, message.content); article.append(content);
 if (message.sources?.length) {
  const box = document.createElement('div'); box.className = 'sources'; const title = document.createElement('div'); title.className = 'sources-label'; title.textContent = 'RETRIEVED PASSAGES · expand to verify'; box.append(title);
  for (const source of message.sources) { const d = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = `[${source.id}] ${source.source} · chunk ${source.chunk}`; const p = document.createElement('p'); p.textContent = source.text; d.append(summary, p); box.append(d); } article.append(box);
 }
 if (message.role === 'assistant' && message.content) { const actions = document.createElement('div'); actions.className = 'message-actions'; const copy = document.createElement('button'); copy.textContent = 'Copy answer'; copy.onclick = async () => { try { await navigator.clipboard.writeText(message.content); copy.textContent = 'Copied'; } catch { toast('Copy is unavailable. Select the answer text to copy it.'); } }; const exp = document.createElement('button'); exp.textContent = 'Export conversation'; exp.onclick = exportChat; actions.append(copy, exp); article.append(actions); }
 return article;
}
function renderMessages() { $('messages').replaceChildren(); const chat = chats.find(c => c.id === current); if (!chat) { $('messages').append(welcome.cloneNode(true)); bindSuggestions(); return; } for (const message of chat.messages) $('messages').append(messageElement(message)); }
function setMode(value) { mode = value; $('rag-mode').classList.toggle('active', mode === 'rag'); $('chat-mode').classList.toggle('active', mode === 'chat'); $('rag-mode').setAttribute('aria-pressed', String(mode === 'rag')); $('chat-mode').setAttribute('aria-pressed', String(mode === 'chat')); $('question').placeholder = mode === 'rag' ? 'Ask a question about your documents…' : 'Message your local model…'; }
function newChat() { if (busy) return; current = null; renderMessages(); renderHistory(); $('question').focus(); document.body.classList.remove('sidebar-open'); }
function bindSuggestions() { document.querySelectorAll('[data-prompt]').forEach(b => b.onclick = () => { $('question').value = b.dataset.prompt; $('question').focus(); }); }
async function refresh() {
 const data = await (await api('/api/status')).json();
 const old = $('model').value; $('model').replaceChildren();
 for (const model of data.models) { const option = document.createElement('option'); option.value = model; option.textContent = model; $('model').append(option); }
 if (!data.models.length) { const option = document.createElement('option'); option.value = ''; option.textContent = 'Download a chat model first'; $('model').append(option); }
 if (data.models.includes(old)) $('model').value = old; else if (data.models.includes(data.default_model)) $('model').value = data.default_model;
 $('connection-status').textContent = data.models.length ? 'Local model connected' : 'No chat model installed';
 renderDocuments(data.documents);
}
function renderDocuments(docs) {
 $('doc-count').textContent = docs.length; $('document-list').replaceChildren();
 if (!docs.length) { const p = document.createElement('p'); p.textContent = 'No documents indexed yet. Add your files or index the included documents.'; $('document-list').append(p); }
 for (const doc of docs) { const row = document.createElement('div'); row.className = 'doc-row'; const info = document.createElement('div'); info.className = 'doc-info'; info.textContent = doc.name; const small = document.createElement('small'); small.textContent = doc.chunks + ' searchable passages'; info.append(small); const remove = document.createElement('button'); remove.textContent = 'Remove'; remove.onclick = async () => { if (!confirm('Remove ' + doc.name + ' from the index?')) return; try { await api('/api/documents/' + encodeURIComponent(doc.name), {method: 'DELETE'}); await refresh(); } catch(e) { toast(e.message); } }; row.append(info, remove); $('document-list').append(row); }
}
function setBusy(value) { busy = value; $('send-button').hidden = value; $('stop-button').hidden = !value; ['new-chat','rag-mode','chat-mode','model','clear-chats','logout'].forEach(id => $(id).disabled = value); }
$('composer').onsubmit = async event => {
 event.preventDefault(); const question = $('question').value.trim(); if (!question || busy) return;
 if (!key) { $('settings-dialog').showModal(); return; } if (!$('model').value) { toast('Connect Ollama and download a chat model first.'); return; }
 let chat = chats.find(c => c.id === current);
 if (!chat) { chat = {id: crypto.randomUUID(), title: question.slice(0,65), mode, messages: []}; chats.push(chat); current = chat.id; }
 const history = chat.messages.filter(m => !m.failed).slice(-10).map(m => ({role:m.role, content:m.content.slice(-12000)}));
 chat.messages.push({role:'user', content:question}); const answer = {role:'assistant', content:'', sources:[], model:$('model').value}; chat.messages.push(answer);
 $('question').value = ''; setBusy(true); save(); renderMessages(); controller = new AbortController();
 try {
  const response = await api('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, signal:controller.signal, body:JSON.stringify({question, model:answer.model, mode, history, top_k:Number($('top-k').value)})});
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '', doneEvent = false;
  function handle(line) { if (!line.trim()) return; const e = JSON.parse(line); if(e.type === 'sources') answer.sources=e.sources; else if(e.type === 'token') answer.content+=e.text; else if(e.type === 'error') throw new Error(e.message); else if(e.type === 'done') doneEvent=true; }
  while(true) { const {value,done} = await reader.read(); if(done) break; buffer += decoder.decode(value,{stream:true}); let index; while((index=buffer.indexOf('\n'))>=0) { const line=buffer.slice(0,index); buffer=buffer.slice(index+1); handle(line); } const nearBottom = $('messages').scrollHeight - $('messages').scrollTop - $('messages').clientHeight < 200; const last=$('messages').lastElementChild; if(last) last.replaceWith(messageElement(answer)); if(nearBottom) $('messages').scrollTop=$('messages').scrollHeight; }
  buffer+=decoder.decode(); if(buffer.trim()) handle(buffer); if(!doneEvent) throw new Error('The response ended early. Please try again.');
 } catch(e) { answer.failed = true; const message=e.name==='AbortError'?'Response stopped.':e.message; answer.content += (answer.content?'\n\n':'') + message; if(e.name !== 'AbortError') toast(message); }
 finally { setBusy(false); controller=null; save(); renderMessages(); $('messages').scrollTop=$('messages').scrollHeight; }
};
$('question').onkeydown = e => { if(e.key==='Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); $('composer').requestSubmit(); } };
$('stop-button').onclick=()=>controller?.abort();
$('new-chat').onclick=newChat;
$('rag-mode').onclick=()=>{newChat();setMode('rag');}; $('chat-mode').onclick=()=>{newChat();setMode('chat');};
$('menu-button').onclick=()=>document.body.classList.toggle('sidebar-open');
$('settings-button').onclick=()=>{$('api-key').value=key;$('settings-dialog').showModal();};
async function openDocs() { $('knowledge-dialog').showModal(); try { renderDocuments(await (await api('/api/documents')).json()); } catch(e) { toast(e.message); } }
$('documents-button').onclick=openDocs; $('attach-button').onclick=openDocs;
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
$('connect').onclick=async()=>{key=$('api-key').value.trim();$('settings-status').textContent='Connecting…';try{await refresh();sessionStorage.setItem('rag-key',key);$('settings-status').textContent='Connected. Your model is ready.';$('settings-dialog').close();}catch(e){$('settings-status').textContent=e.message;}};
$('index-seed').onclick=async()=>{const b=$('index-seed');b.disabled=true;$('index-status').textContent='Embedding and indexing the included files…';try{const result=await(await api('/api/index-seed',{method:'POST'})).json();const failures=result.documents.filter(d=>d.status==='failed');$('index-status').textContent=failures.length?`${failures.length} files failed. Check that Ollama and all-minilm are ready, then retry.`:`${result.documents.length} documents indexed. You can ask a question now.`;await refresh();}catch(e){$('index-status').textContent=e.message;}finally{b.disabled=false;}};
$('file-upload').onchange=async()=>{const files=[...$('file-upload').files];$('file-upload').disabled=true;let count=0;try{for(const file of files){if(file.size>5*1024*1024)throw new Error(file.name+' exceeds 5 MB.');$('index-status').textContent='Indexing '+file.name+'…';const form=new FormData();form.append('file',file);await api('/api/documents',{method:'POST',body:form});count++;}$('index-status').textContent=`${count} documents indexed.`;}catch(e){$('index-status').textContent=`${count} indexed. ${e.message}`;}finally{$('file-upload').value='';$('file-upload').disabled=false;try{await refresh();}catch(e){toast(e.message);}}};
$('clear-chats').onclick=()=>{if(confirm('Delete all conversations saved in this browser?')){chats=[];current=null;save();renderMessages();}};
$('logout').onclick=()=>{key='';sessionStorage.removeItem('rag-key');$('api-key').value='';$('connection-status').textContent='Locked';$('settings-status').textContent='Access key removed from this browser session. Saved chats remain on this device.';};
function exportChat(){const chat=chats.find(c=>c.id===current);if(!chat)return;const text=chat.messages.map(m=>`## ${m.role}\n\n${m.content}\n`+(m.sources?.length?'\nSources:\n'+m.sources.map(s=>`[${s.id}] ${s.source} (chunk ${s.chunk})\n${s.text}`).join('\n\n'):'')).join('\n\n');const url=URL.createObjectURL(new Blob([text],{type:'text/markdown'}));const a=document.createElement('a');a.href=url;a.download='conversation.md';a.click();URL.revokeObjectURL(url);}
renderHistory();bindSuggestions();
if(key)refresh().catch(e=>{$('connection-status').textContent='Connection needed';toast(e.message);});else{$('settings-dialog').showModal();}

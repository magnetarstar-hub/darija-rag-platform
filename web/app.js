const state = { token: sessionStorage.getItem("rag_token"), user: null, documents: [], messages: [] };

const icons = {
  logo: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v4H9v4h8v4H9v4H5V4Z" fill="currentColor"/></svg>',
  send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 4 16 8-16 8 3-8-3-8Zm3.2 8h7.4L8.8 9.2 7.2 12l1.6 2.8 5.8-2.8H7.2Z" fill="currentColor"/></svg>',
  file: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h8l4 4v14H6V3Zm7 1.8V8h3.2L13 4.8ZM8 12h8v1.5H8V12Zm0 3h8v1.5H8V15Z" fill="currentColor"/></svg>',
  plus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z" fill="currentColor"/></svg>',
  logout: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 4h8v3h-2V6h-4v12h4v-1h2v3h-8V4Zm7.6 4.6L21 12l-3.4 3.4-1.4-1.4 1-1H9v-2h7.2l-1-1 1.4-1.4Z" fill="currentColor"/></svg>'
};

const esc = (value = "") => String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const api = async (path, options = {}) => {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) { logout(); throw new Error("Your session has expired. Please sign in again."); }
  const body = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Something went wrong. Please try again.");
  return body;
};

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message; toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer); showToast.timer = window.setTimeout(() => toast.classList.add("hidden"), 3600);
}

function loginView(error = "") {
  document.querySelector("#app").innerHTML = `<main class="grid min-h-screen lg:grid-cols-[1.05fr_.95fr]">
    <section class="relative hidden overflow-hidden bg-moss p-12 text-white lg:flex lg:flex-col lg:justify-between">
      <div class="absolute -right-28 -top-28 h-80 w-80 rounded-full border-[34px] border-white/10"></div>
      <div class="relative flex items-center gap-3 text-sm font-bold tracking-[.18em] uppercase">${icons.logo}<span>Darija RAG</span></div>
      <div class="relative max-w-xl pb-12"><p class="mb-5 text-sm font-semibold uppercase tracking-[.2em] text-sage">Private knowledge, clearly answered</p><h1 class="font-display text-6xl font-extrabold leading-[1.02] tracking-tight">Ask your documents<br><span class="text-sage">in your language.</span></h1><p class="mt-7 max-w-md text-lg leading-8 text-white/70">A secure workspace for Arabic, Darija, French, and English knowledge.</p></div>
      <p class="relative text-xs text-white/50">Tenant-isolated. Citation-first. Built for teams.</p>
    </section>
    <section class="flex items-center justify-center px-6 py-12 sm:px-10"><div class="w-full max-w-sm">
      <div class="mb-12 flex items-center gap-3 text-sm font-bold tracking-[.18em] text-moss uppercase lg:hidden">${icons.logo}<span>Darija RAG</span></div>
      <p class="mb-3 text-sm font-semibold text-coral">Welcome back</p><h2 class="font-display text-4xl font-extrabold tracking-tight text-ink">Sign in to your workspace</h2><p class="mt-3 text-sm leading-6 text-slate-500">Continue to your private knowledge base.</p>
      ${error ? `<div role="alert" class="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">${esc(error)}</div>` : ""}
      <form id="login-form" class="mt-8 space-y-5"><label class="block text-sm font-semibold">Email<input name="username" type="email" autocomplete="email" required placeholder="you@organization.com" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-3.5 outline-none transition placeholder:text-slate-400 focus:border-moss focus:ring-4 focus:ring-sage" /></label><label class="block text-sm font-semibold">Password<input name="password" type="password" autocomplete="current-password" required placeholder="Enter your password" class="mt-2 w-full rounded-xl border border-slate-200 bg-white px-4 py-3.5 outline-none transition placeholder:text-slate-400 focus:border-moss focus:ring-4 focus:ring-sage" /></label><button class="flex w-full items-center justify-center gap-2 rounded-xl bg-ink px-4 py-3.5 text-sm font-bold text-white transition hover:bg-moss disabled:cursor-wait disabled:opacity-60">Sign in <span aria-hidden="true">&#8594;</span></button></form>
      <p class="mt-8 text-center text-xs text-slate-400">Your access is protected by tenant-level permissions.</p>
    </div></section></main>`;
  document.querySelector("#login-form").addEventListener("submit", handleLogin);
}

async function handleLogin(event) {
  event.preventDefault(); const form = event.currentTarget; const button = form.querySelector("button"); button.disabled = true; button.textContent = "Signing in...";
  try { const data = await api("/auth/login", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams(new FormData(form)) }); state.token = data.access_token; sessionStorage.setItem("rag_token", state.token); await boot(); }
  catch (error) { loginView(error.message); } finally { button.disabled = false; }
}

function shell() {
  document.querySelector("#app").innerHTML = `<div class="flex min-h-screen bg-paper"><aside class="hidden w-64 shrink-0 border-r border-slate-200/80 bg-white px-5 py-6 lg:flex lg:flex-col"><div class="flex items-center gap-3 px-2 text-sm font-bold tracking-[.14em] text-moss uppercase">${icons.logo}<span>Darija RAG</span></div><nav class="mt-14 space-y-2"><button data-view="ask" class="nav-item active flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-semibold"><span class="text-lg">&#8599;</span> Ask knowledge</button><button data-view="documents" class="nav-item flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-semibold text-slate-500"><span class="text-lg">&#9633;</span> Documents</button></nav><div class="mt-auto border-t border-slate-100 pt-5"><div class="flex items-center gap-3 px-2"><div class="grid h-9 w-9 place-items-center rounded-full bg-sage text-xs font-bold text-moss">${esc((state.user.email || "U")[0].toUpperCase())}</div><div class="min-w-0"><p class="truncate text-sm font-bold">${esc(state.user.email)}</p><p class="text-xs capitalize text-slate-400">${esc(state.user.role)}</p></div></div><button id="logout" class="mt-5 flex items-center gap-2 px-2 text-xs font-semibold text-slate-400 transition hover:text-ink">${icons.logout} Sign out</button></div></aside><main class="min-w-0 flex-1"><header class="flex items-center justify-between border-b border-slate-200/80 bg-white/80 px-5 py-4 backdrop-blur sm:px-8 lg:hidden"><div class="flex items-center gap-2 text-sm font-bold tracking-[.12em] text-moss uppercase">${icons.logo} Darija RAG</div><button id="mobile-logout" class="text-slate-400">${icons.logout}</button></header><div id="view" class="mx-auto max-w-6xl px-5 py-8 sm:px-8 lg:px-12 lg:py-12"></div></main></div>`;
  document.querySelectorAll(".nav-item").forEach(item => item.addEventListener("click", () => setView(item.dataset.view)));
  document.querySelector("#logout").addEventListener("click", logout); document.querySelector("#mobile-logout").addEventListener("click", logout); setView("ask");
}

function setView(view) {
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === view));
  if (view === "documents") documentsView(); else askView();
}

function askView() {
  document.querySelector("#view").innerHTML = `<section class="fade-up"><div class="flex flex-wrap items-end justify-between gap-5"><div><p class="text-sm font-semibold text-coral">Knowledge workspace</p><h1 class="font-display mt-2 text-4xl font-extrabold tracking-tight sm:text-5xl">What would you like<br class="hidden sm:block" /> to know?</h1><p class="mt-4 text-sm text-slate-500">Answers are grounded in the documents you can access.</p></div><div class="rounded-full border border-sage bg-white px-3 py-2 text-xs font-bold text-moss"><span class="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500"></span> Secure workspace</div></div><div id="chat" class="mt-10 space-y-6">${state.messages.length ? state.messages.map(message => messageHTML(message)).join("") : `<div class="rounded-2xl border border-dashed border-slate-200 bg-white/60 px-6 py-12 text-center"><div class="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-sage text-2xl text-moss">&#10024;</div><p class="mt-4 text-sm font-bold">Start with a question</p><p class="mt-1 text-sm text-slate-500">Try asking about a policy, deadline, or procedure.</p></div>`}</div><form id="ask-form" class="sticky bottom-5 mt-10 rounded-2xl border border-slate-200 bg-white p-2 shadow-[0_12px_40px_rgba(23,33,27,.08)]"><div class="flex items-end gap-2"><textarea name="question" rows="1" required maxlength="2000" placeholder="Ask in Arabic, Darija, French, or English..." class="max-h-36 min-h-12 flex-1 resize-none bg-transparent px-3 py-3 text-sm outline-none placeholder:text-slate-400"></textarea><button title="Send question" class="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-ink text-white transition hover:bg-moss disabled:cursor-wait disabled:opacity-50">${icons.send}</button></div><div class="flex items-center justify-between px-3 pb-1 pt-1 text-[11px] text-slate-400"><span>Answers include sources from your accessible documents.</span><span id="char-count">0 / 2000</span></div></form></section>`;
  const form = document.querySelector("#ask-form"); const input = form.querySelector("textarea"); input.addEventListener("input", () => document.querySelector("#char-count").textContent = `${input.value.length} / 2000`); form.addEventListener("submit", handleAsk);
}

function messageHTML(message) {
  const isUser = message.role === "user";
  const sources = (message.sources || []).map(source => `<span class="inline-flex items-center gap-1.5 rounded-lg bg-paper px-2.5 py-1.5 text-xs font-semibold text-moss">${icons.file}${esc(source.source)}${source.page ? ` · p.${source.page}` : ""}</span>`).join("");
  const sourceBlock = sources ? `<div class="mt-5 border-t border-slate-100 pt-4"><p class="mb-3 text-[11px] font-bold uppercase tracking-[.14em] text-slate-400">Sources</p><div class="flex flex-wrap gap-2">${sources}</div></div>` : "";
  const content = isUser ? esc(message.text).replace(/\n/g, "<br>") : `<p class="whitespace-pre-wrap">${esc(message.text)}</p>${sourceBlock}`;
  return `<article class="fade-up ${isUser ? "ml-auto max-w-2xl" : "max-w-3xl"}"><div class="mb-2 text-[11px] font-bold uppercase tracking-[.16em] ${isUser ? "text-right text-slate-400" : "text-moss"}">${isUser ? "You" : "Darija RAG"}</div><div class="rounded-2xl ${isUser ? "rounded-tr-sm bg-ink text-white" : "rounded-tl-sm border border-slate-200 bg-white"} px-5 py-4 text-sm leading-7">${content}</div></article>`;
}

async function handleAsk(event) { event.preventDefault(); const form = event.currentTarget; const input = form.querySelector("textarea"); const question = input.value.trim(); if (!question) return; state.messages.push({ role: "user", text: question }); input.value = ""; askView(); const button = document.querySelector("#ask-form button"); button.disabled = true; button.innerHTML = "..."; try { const result = await api("/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) }); state.messages.push({ role: "assistant", text: result.answer, sources: result.sources || [] }); } catch (error) { state.messages.push({ role: "assistant", text: error.message }); } askView(); }

async function documentsView() { document.querySelector("#view").innerHTML = `<section class="fade-up"><div class="flex flex-wrap items-end justify-between gap-5"><div><p class="text-sm font-semibold text-coral">Knowledge base</p><h1 class="font-display mt-2 text-4xl font-extrabold tracking-tight">Documents</h1><p class="mt-3 text-sm text-slate-500">Manage the sources your workspace can search.</p></div>${["admin", "editor"].includes(state.user.role) ? `<button id="upload-trigger" class="flex items-center gap-2 rounded-xl bg-ink px-4 py-3 text-sm font-bold text-white transition hover:bg-moss">${icons.plus} Add document</button>` : ""}</div><div id="documents" class="mt-9">Loading documents...</div></section>`; if (document.querySelector("#upload-trigger")) document.querySelector("#upload-trigger").addEventListener("click", uploadDocument); try { state.documents = await api("/documents"); renderDocuments(); } catch (error) { document.querySelector("#documents").innerHTML = `<p class="rounded-xl bg-red-50 p-4 text-sm text-red-700">${esc(error.message)}</p>`; } }

function renderDocuments() { const target = document.querySelector("#documents"); if (!state.documents.length) { target.innerHTML = `<div class="rounded-2xl border border-dashed border-slate-200 bg-white px-6 py-14 text-center"><div class="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-sage text-moss">${icons.file}</div><p class="mt-4 text-sm font-bold">No documents yet</p><p class="mt-1 text-sm text-slate-500">Upload a PDF, Markdown, or text file to get started.</p></div>`; return; } target.innerHTML = `<div class="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div class="hidden grid-cols-[1fr_130px_130px] gap-4 border-b border-slate-100 bg-paper px-5 py-3 text-[11px] font-bold uppercase tracking-[.14em] text-slate-400 sm:grid"><span>Document</span><span>Status</span><span>Visibility</span></div>${state.documents.map(doc => `<div class="grid gap-3 border-b border-slate-100 px-5 py-4 last:border-0 sm:grid-cols-[1fr_130px_130px] sm:items-center sm:gap-4"><div class="flex min-w-0 items-center gap-3"> <span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-sage text-moss">${icons.file}</span><div class="min-w-0"><p class="truncate text-sm font-bold">${esc(doc.filename)}</p><p class="mt-1 text-xs text-slate-400">${doc.n_chunks || 0} chunks · ${new Date(doc.created_at).toLocaleDateString()}</p></div></div><span class="w-fit rounded-full px-2.5 py-1 text-xs font-bold ${doc.status === "ready" ? "bg-emerald-50 text-emerald-700" : doc.status === "failed" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}">${esc(doc.status)}</span><span class="text-xs font-semibold capitalize text-slate-500">${esc(doc.visibility)}</span></div>`).join("")}</div>`; }

async function uploadDocument() { const input = document.createElement("input"); input.type = "file"; input.accept = ".pdf,.txt,.md"; input.onchange = async () => { const file = input.files?.[0]; if (!file) return; const form = new FormData(); form.append("file", file); try { await api("/documents", { method: "POST", body: form }); showToast("Document uploaded and queued for processing."); documentsView(); } catch (error) { showToast(error.message); } }; input.click(); }

function logout() { state.token = null; state.user = null; state.messages = []; sessionStorage.removeItem("rag_token"); loginView(); }
async function boot() { try { state.user = await api("/me"); shell(); } catch (error) { logout(); } }
if (state.token) boot(); else loginView();

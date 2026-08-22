/**
 * app.js — TJRJ Monitor Frontend
 */

"use strict";

const DATA_BASE = "./data";
const LS_NAME = "tjrj_watch_name";
const LS_WATCH = "tjrj_watch_active";

// ═══════════════════════════════════════════════════════════════
// ESTADO GLOBAL
// ═══════════════════════════════════════════════════════════════
let globalIndex = { tjrj_documents: [], fgv_documents: [], matches: [], last_update: "" };
let watchName = "";
let avisosQuery = "";
let diarioQuery = "";
let demoCards = []; // cards mockados para simulação de teste

// ═══════════════════════════════════════════════════════════════
// DOM
// ═══════════════════════════════════════════════════════════════
const $ = id => document.getElementById(id);

const elTabs = document.querySelectorAll(".tab");
const elTabContents = document.querySelectorAll(".tab-content");

// Aba Avisos
const elAvisosSearch = $("avisos-search");
const elAvisosClear = $("avisos-search-clear");
const elAvisosLoading = $("avisos-loading");
const elAvisosEmpty = $("avisos-empty");
const elTjrjSection = $("tjrj-section");
const elTjrjCards = $("tjrj-cards");
const elFgvSection = $("fgv-section");
const elFgvCards = $("fgv-cards");

// Aba Diário
const elDiarioSearch = $("diario-search");
const elDiarioClear = $("diario-search-clear");
const elDiarioLoading = $("diario-loading");
const elDiarioEmpty = $("diario-empty");
const elDiarioCards = $("diario-cards");

// Aba Config
const elConfigName = $("config-name");
const elBtnSaveName = $("btn-save-name");
const elNameSavedMsg = $("name-saved-msg");
const elBtnClearLocal = $("btn-clear-local");
const elBtnDemoConvocacao = $("btn-demo-convocacao");
const elHeaderBadge = $("header-watch-badge");
const elHeaderName = $("header-watch-name");
const elHeaderSub = $("header-subtitle");

// ═══════════════════════════════════════════════════════════════
// UTILITÁRIOS
// ═══════════════════════════════════════════════════════════════

function escHtml(s) {
  if (!s) return "";
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function hl(text, q) {
  if (!q || !text) return escHtml(text);
  const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")})`, "gi");
  return escHtml(text).replace(re, "<mark>$1</mark>");
}

async function fetchJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${url}`);
  return r.json();
}

function loadLS() {
  watchName = localStorage.getItem(LS_NAME) || "";
  if (elConfigName) elConfigName.value = watchName;
}

// ═══════════════════════════════════════════════════════════════
// TABS NAVIGATION
// ═══════════════════════════════════════════════════════════════

elTabs.forEach(tab => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.tab;
    elTabs.forEach(t => t.classList.remove("active"));
    elTabContents.forEach(c => { c.classList.remove("active"); c.style.display = "none"; });
    
    tab.classList.add("active");
    const content = $(`tab-${target}`);
    if (content) {
      content.classList.add("active");
      content.style.display = "block";
    }
  });
});

// ═══════════════════════════════════════════════════════════════
// CARD RENDERER
// ═══════════════════════════════════════════════════════════════

function renderCard(item, q, type = "document") {
  const titleUpper = item.title.toUpperCase();
  const snippetUpper = (item.snippet || "").toUpperCase();
  const kwsUpper = (item.matched_keywords || []).map(k => k.toUpperCase());
  const allText = titleUpper + " " + snippetUpper + " " + kwsUpper.join(" ");

  const isWatched = watchName && (
    titleUpper.includes(watchName.toUpperCase()) || 
    snippetUpper.includes(watchName.toUpperCase())
  );

  const isCargoConvocacao = (allText.includes("ENGENHEIRO DE DADOS") || allText.includes("ENGENHARIA DE DADOS")) &&
    (allText.includes("CONVOCAÇÃO") || allText.includes("CONVOCACAO") || allText.includes("NOMEAÇÃO") || allText.includes("NOMEACAO") || allText.includes("POSSE"));

  const isDataEng = allText.includes("ENGENHEIRO DE DADOS") || allText.includes("CONVOCAÇÃO") || allText.includes("NOMEAÇÃO");
  
  let cardClass = "card";
  if (isWatched) cardClass = "card highlighted";
  else if (isCargoConvocacao) cardClass = "card cargo-convocacao";

  const classifBadge = isWatched && titleUpper.includes("THIAGO") 
    ? `<span class="card-classif" style="background: var(--gold-dim); color: var(--gold); border: 1px solid rgba(212,175,55,.3); font-size: 0.68rem; font-weight: 800; padding: 3px 10px; border-radius: 999px; margin-left: 5px;">11º</span>` 
    : "";

  const watchBadge = isWatched 
    ? `<span class="card-watch-badge">🎯 Monitorado</span>` 
    : isCargoConvocacao
      ? `<span class="card-watch-badge" style="background: rgba(239,68,68,.15); color: #f87171; border-color: rgba(239,68,68,.35);">🚨 CONVOCAÇÃO ENGENHARIA DE DADOS</span>`
      : isDataEng 
        ? `<span class="card-watch-badge" style="background: rgba(59,130,246,.1); color: var(--blue-light); border-color: rgba(59,130,246,.25);">⚡ Interesse</span>`
        : "";

  let icon = "📄";
  if (type === "djerj") icon = "📰";
  
  const iconSpan = `<span class="card-pref-badge">${icon} ${type.toUpperCase()}</span>`;
  const snippetDiv = item.snippet 
    ? `<div class="card-snippet">${hl(item.snippet, q || watchName)}</div>` 
    : "";
    
  const kwBadge = item.matched_keywords && item.matched_keywords.length
    ? `<div style="margin-top: 8px;"><span class="card-pref-badge" style="border-color: var(--gold); color: var(--gold); font-size: 0.65rem;">Palavra-chave: ${item.matched_keywords.join(", ")}</span></div>`
    : "";

  return `
    <div class="${cardClass}">
      ${iconSpan}${classifBadge}${watchBadge}
      <div class="card-name">
        <a href="${item.url}" target="_blank" rel="noopener">${hl(item.title, q)}</a>
      </div>
      <div class="card-meta">
        <div class="card-meta-item"><span>📅</span> ${item.date || "Atualizado"}</div>
        ${snippetDiv}
        ${kwBadge}
      </div>
    </div>
  `;
}

// ═══════════════════════════════════════════════════════════════
// ABA AVISOS (TJRJ & FGV)
// ═══════════════════════════════════════════════════════════════

function renderAvisos() {
  const q = avisosQuery.trim().toLowerCase();
  
  let tjrjFiltered = globalIndex.tjrj_documents;
  let fgvFiltered = globalIndex.fgv_documents;

  // Insere mock demo se houver e coincidir
  if (demoCards.length) {
    const demoTjrj = demoCards.filter(c => c.type === "tjrj");
    const demoFgv = demoCards.filter(c => c.type === "fgv");
    tjrjFiltered = demoTjrj.concat(tjrjFiltered);
    fgvFiltered = demoFgv.concat(fgvFiltered);
  }

  if (q) {
    tjrjFiltered = tjrjFiltered.filter(d => d.title.toLowerCase().includes(q));
    fgvFiltered = fgvFiltered.filter(d => d.title.toLowerCase().includes(q));
  }

  elAvisosLoading.style.display = "none";
  
  if (tjrjFiltered.length === 0 && fgvFiltered.length === 0) {
    elTjrjSection.style.display = "none";
    elFgvSection.style.display = "none";
    elAvisosEmpty.style.display = "block";
    return;
  }

  elAvisosEmpty.style.display = "none";

  if (tjrjFiltered.length > 0) {
    elTjrjSection.style.display = "block";
    elTjrjCards.innerHTML = tjrjFiltered.map(d => renderCard(d, q, "tjrj")).join("");
  } else {
    elTjrjSection.style.display = "none";
  }

  if (fgvFiltered.length > 0) {
    elFgvSection.style.display = "block";
    elFgvCards.innerHTML = fgvFiltered.map(d => renderCard(d, q, "fgv")).join("");
  } else {
    elFgvSection.style.display = "none";
  }
}

// ═══════════════════════════════════════════════════════════════
// ABA DIÁRIO (DJERJ)
// ═══════════════════════════════════════════════════════════════

function renderDiario() {
  const q = diarioQuery.trim().toLowerCase();
  
  let djerjFiltered = globalIndex.matches.filter(m => m.source === "djerj_search" || m.source === "djerj_portal" || m.source === "djerj");

  if (demoCards.length) {
    const demoDjerj = demoCards.filter(c => c.type === "djerj");
    djerjFiltered = demoDjerj.concat(djerjFiltered);
  }

  if (q) {
    djerjFiltered = djerjFiltered.filter(m => 
      m.title.toLowerCase().includes(q) || 
      (m.snippet && m.snippet.toLowerCase().includes(q))
    );
  }

  elDiarioLoading.style.display = "none";

  if (djerjFiltered.length === 0) {
    elDiarioCards.style.display = "none";
    elDiarioEmpty.style.display = "block";
    return;
  }

  elDiarioEmpty.style.display = "none";
  elDiarioCards.style.display = "grid";
  elDiarioCards.innerHTML = djerjFiltered.map(d => renderCard(d, q, "djerj")).join("");
}

// ═══════════════════════════════════════════════════════════════
// EVENT LISTENERS & CONFIGS
// ═══════════════════════════════════════════════════════════════

elAvisosSearch.addEventListener("input", () => {
  avisosQuery = elAvisosSearch.value;
  elAvisosClear.style.display = avisosQuery ? "block" : "none";
  renderAvisos();
});

elAvisosClear.addEventListener("click", () => {
  elAvisosSearch.value = "";
  avisosQuery = "";
  elAvisosClear.style.display = "none";
  renderAvisos();
  elAvisosSearch.focus();
});

elDiarioSearch.addEventListener("input", () => {
  diarioQuery = elDiarioSearch.value;
  elDiarioClear.style.display = diarioQuery ? "block" : "none";
  renderDiario();
});

elDiarioClear.addEventListener("click", () => {
  elDiarioSearch.value = "";
  diarioQuery = "";
  elDiarioClear.style.display = "none";
  renderDiario();
  elDiarioSearch.focus();
});

elBtnSaveName.addEventListener("click", () => {
  const name = elConfigName.value.trim().toUpperCase();
  if (!name) return;
  watchName = name;
  localStorage.setItem(LS_NAME, name);
  elNameSavedMsg.style.display = "block";
  updateWatchBadge();
  renderAvisos();
  renderDiario();
  setTimeout(() => elNameSavedMsg.style.display = "none", 2500);
});

elBtnClearLocal.addEventListener("click", () => {
  if (!confirm("Apagar nome salvo e simulações? Não é possível desfazer.")) return;
  localStorage.removeItem(LS_NAME);
  watchName = "";
  demoCards = [];
  elConfigName.value = "";
  updateWatchBadge();
  renderAvisos();
  renderDiario();
  alert("Preferências locais apagadas.");
});

function updateWatchBadge() {
  if (watchName) {
    elHeaderBadge.style.display = "block";
    elHeaderName.textContent = watchName;
  } else {
    elHeaderBadge.style.display = "none";
  }
}

// Lógica de Simulação de Convocação
if (elBtnDemoConvocacao) {
  elBtnDemoConvocacao.addEventListener("click", () => {
    const testName = watchName || "THIAGO RIBEIRO DA SILVA";
    if (!watchName) {
      watchName = testName;
      elConfigName.value = testName;
      localStorage.setItem(LS_NAME, testName);
      updateWatchBadge();
    }

    const todayStr = new Date().toLocaleDateString("pt-BR");
    
    // Insere um card mockado na aba Avisos (TJRJ) e um na aba Diário (DJERJ)
    demoCards = [
      {
        title: "Aviso TJ nº 250/2026 - Convocação para Exames e Nomeação - LXII Concurso",
        url: "https://www.tjrj.jus.br",
        date: todayStr,
        snippet: `Convocamos o candidato THIAGO RIBEIRO DA SILVA (Inscrição 397050352) aprovado em 11º lugar na especialidade Engenheiro de Dados para comparecer à perícia médica.`,
        type: "tjrj"
      },
      {
        title: "Nomeação de Analista Judiciário - Caderno I Administrativo (Pág. 12)",
        url: "https://www3.tjrj.jus.br",
        date: todayStr,
        snippet: `O Presidente do TJRJ nomeia THIAGO RIBEIRO DA SILVA no cargo de Analista Judiciário - Especialidade Engenheiro de Dados.`,
        pagina: "12",
        keyword: "THIAGO RIBEIRO DA SILVA",
        type: "djerj"
      }
    ];

    // Alterna para a aba Avisos
    elTabs[0].click();
    renderAvisos();
    renderDiario();

    alert(`Simulação criada! Veja o card destacado para "${watchName}" nas abas de Avisos e Diário da Justiça.`);
  });
}

// ═══════════════════════════════════════════════════════════════
// INICIALIZAÇÃO
// ═══════════════════════════════════════════════════════════════

async function init() {
  loadLS();
  updateWatchBadge();

  try {
    globalIndex = await fetchJSON(`${DATA_BASE}/global-index.json`);
    
    if (globalIndex.last_update) {
      elHeaderSub.textContent = `Acompanhamento Concurso TJRJ · Última Verificação: ${globalIndex.last_update}`;
    }
  } catch (e) {
    log.warning("Falha ao carregar dados do index, usando mock básico: %s", e);
  }

  renderAvisos();
  renderDiario();
}

init();

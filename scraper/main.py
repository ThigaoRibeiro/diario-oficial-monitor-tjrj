"""
main.py — Orquestrador do Monitor TJRJ.
Executa os scrapers do portal do TJRJ, da FGV e do DJERJ, gerando as saídas de dados e logs.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from html import escape

from tjrj_portal import check_tjrj_portal
from fgv_portal import check_fgv_portal
from djerj_scraper import check_djerj

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT       = Path(__file__).parent.parent
DATA_DIR   = ROOT / "data"
CONFIG_DIR = ROOT / "config"

DATA_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)


# ── Configurações e Arquivos de Dados ───────────────────────────

def load_config() -> dict:
    """Carrega as palavras-chave do config/monitorados.json com fallbacks seguros e mescla com a env WATCH_NAMES."""
    config_path = CONFIG_DIR / "monitorados.json"
    default_config = {
        "watched_keywords": [
            "CONVOCAÇÃO", "NOMEAÇÃO", "ENGENHEIRO DE DADOS", 
            "RESULTADO", "HOMOLOGAÇÃO", "AVISO TJ", "AVALIAÇÃO MÉDICA", "POSSE"
        ],
        "djerj_keywords": [
            "397050352", "THIAGO RIBEIRO DA SILVA", "ENGENHEIRO DE DADOS",
            "ANALISTA JUDICIÁRIO - ENGENHEIRO DE DADOS"
        ]
    }

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if "watched_keywords" in data and "djerj_keywords" in data:
                default_config = data
        except Exception as e:
            log.warning("Falha ao carregar config/monitorados.json, usando padrão: %s", e)

    # Cria o arquivo default se não existir
    if not config_path.exists():
        try:
            config_path.write_text(json.dumps(default_config, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("Falha ao salvar config/monitorados.json default: %s", e)

    # Adiciona valores da variável de ambiente WATCH_NAMES (separada por vírgulas)
    env_val = os.environ.get("WATCH_NAMES", "")
    if env_val:
        for val in env_val.split(","):
            val_clean = val.strip()
            if val_clean:
                # Adiciona ao djerj_keywords se não estiver lá
                if val_clean not in default_config["djerj_keywords"]:
                    default_config["djerj_keywords"].append(val_clean)
                # Adiciona ao watched_keywords se não estiver lá
                if val_clean not in default_config["watched_keywords"]:
                    default_config["watched_keywords"].append(val_clean)

    return default_config


def load_json_file(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_json_file(path: Path, data: any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── GitHub Actions Outputs ────────────────────────────────────

def set_output(key: str, value: str) -> None:
    safe_value = " ".join(str(value).replace("\n", " ").split())
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={safe_value}\n")
    log.info("OUTPUT %s=%s", key, safe_value)


# ── Execução do Pipeline ──────────────────────────────────────

def run() -> None:
    log.info("=== Iniciando Monitoramento TJRJ - Engenharia de Dados ===")
    
    config = load_config()
    watched_kws = config["watched_keywords"]
    djerj_kws = config["djerj_keywords"]

    # Carrega índices anteriores
    tjrj_index_path = DATA_DIR / "tjrj_portal_index.json"
    fgv_index_path = DATA_DIR / "fgv_portal_index.json"
    matches_path = DATA_DIR / "matches.json"

    tjrj_prev = load_json_file(tjrj_index_path)
    fgv_prev = load_json_file(fgv_index_path)
    matches_history = load_json_file(matches_path)

    # 1. Scraping Frente 1: Portal TJRJ
    tjrj_new_idx, tjrj_new_docs, tjrj_matches = check_tjrj_portal(tjrj_prev, watched_kws)
    save_json_file(tjrj_index_path, tjrj_new_idx)

    # 2. Scraping Frente 2: Portal FGV
    fgv_new_idx, fgv_new_docs, fgv_matches = check_fgv_portal(fgv_prev, watched_kws)
    save_json_file(fgv_index_path, fgv_new_idx)

    # 3. Scraping Frente 3: DJERJ (Consulta últimos 3 dias)
    djerj_matches = check_djerj(djerj_kws, days_to_check=3)

    # Consolidando Matches
    new_matches = []
    
    # Adiciona matches do TJRJ
    for m in tjrj_matches:
        new_matches.append({
            **m,
            "detected_at": datetime.now().isoformat(),
            "id": f"tjrj_{hash(m['url'])}"
        })

    # Adiciona matches da FGV
    for m in fgv_matches:
        new_matches.append({
            **m,
            "detected_at": datetime.now().isoformat(),
            "id": f"fgv_{hash(m['url'])}"
        })

    # Adiciona matches do DJERJ (deduplica baseando em URL do Diário)
    seen_match_urls = {m["url"] for m in matches_history}
    for m in djerj_matches:
        if m["url"] not in seen_match_urls:
            new_matches.append({
                **m,
                "detected_at": datetime.now().isoformat(),
                "id": f"djerj_{hash(m['url'])}"
            })

    # Se há novos matches de interesse, anexa ao histórico
    if new_matches:
        matches_history.extend(new_matches)
        save_json_file(matches_path, matches_history)
        log.info("Adicionados %d novos matches ao histórico", len(new_matches))

    # Compilar global-index.json para o frontend
    global_index = {
        "tjrj_documents": tjrj_new_idx[:50],  # limita aos 50 mais recentes
        "fgv_documents": fgv_new_idx[:50],
        "matches": matches_history,
        "last_update": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }
    save_json_file(DATA_DIR / "global-index.json", global_index)

    # Geração do sumário e outputs do GitHub Actions
    has_watched_match = len(new_matches) > 0
    matched_names = []
    
    summary_lines = []
    summary_html = []

    # Detalha novos matches no e-mail
    if new_matches:
        summary_lines.append("🚨 OCORRÊNCIA ENCONTRADA:")
        summary_html.append("<h2 style='color: #e53e3e;'>🚨 Ocorrências de interesse encontradas:</h2>")
        
        for m in new_matches:
            src = "Diário Oficial" if m["source"] == "djerj_search" else "Página do Concurso"
            title = m["title"]
            url = m["url"]
            
            # Adiciona ao e-mail
            summary_lines.append(f"  - [{src}] {title} -> {url}")
            
            detail_text = ""
            if "matched_keywords" in m:
                matched_names.extend(m["matched_keywords"])
                detail_text = f" (Palavras-chave: {', '.join(m['matched_keywords'])})"
            elif "keyword" in m:
                matched_names.append(m["keyword"])
                detail_text = f" (Pesquisa: {m['keyword']})"

            snippet_html = f'<br><span style="font-size: 13px; color: #555;">{escape(m["snippet"])}</span>' if 'snippet' in m else ''
            summary_html.append(
                f"<div style='border-left: 4px solid #d4af37; background: #f8f9fa; padding: 12px; margin-bottom: 12px;'>"
                f"<strong>[{src}]</strong> <a href='{url}' style='color: #0e3a9e; font-weight: bold;'>{escape(title)}</a>{escape(detail_text)}"
                f"{snippet_html}"
                f"</div>"
            )
    else:
        summary_lines.append("📭 Nenhuma nova ocorrência de interesse hoje.")
        summary_html.append("<div>📭 Nenhuma nova ocorrência com seu nome, inscrição ou cargo Engenheiro de Dados foi publicada hoje.</div>")

    # Adiciona status geral
    summary_lines.append(f"Resumo geral: TJRJ ({len(tjrj_new_docs)} novos docs), FGV ({len(fgv_new_docs)} novos docs)")
    summary_html.append(
        f"<h3 style='margin-top: 24px; color: #333;'>Resumo da checagem:</h3>"
        f"<ul>"
        f"<li><strong>Página TJRJ:</strong> {len(tjrj_new_docs)} novo(s) documento(s)</li>"
        f"<li><strong>Página FGV:</strong> {len(fgv_new_docs)} novo(s) documento(s)</li>"
        f"<li><strong>DJERJ:</strong> Varredura de palavras-chave concluída</li>"
        f"</ul>"
    )

    # Define outputs da action
    today_str = datetime.now().strftime("%d/%m/%Y")
    unique_matched_names = list(set(matched_names))
    
    set_output("has_watched_match", "true" if has_watched_match else "false")
    set_output("watched_matched_names", ", ".join(unique_matched_names) if unique_matched_names else "Nenhum")
    set_output("edition_date", today_str)
    set_output("email_summary", " | ".join(summary_lines))
    set_output("email_summary_html", "".join(summary_html))

    log.info("=== Processamento Concluído ===")


if __name__ == "__main__":
    run()

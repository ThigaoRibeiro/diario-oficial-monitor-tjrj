"""
main.py — Orquestrador do Monitor TJRJ.
Executa os scrapers do portal do TJRJ, da FGV e do DJERJ, gerando as saídas de dados e logs.
"""

import json
import logging
import os
import sys
import re
import hashlib
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from html import escape, unescape
from urllib.parse import urljoin

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

def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


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


DJERJ_HOST = "https://www3.tjrj.jus.br"

# Gmail recusa mensagens acima de 25 MB; o base64 do anexo infla ~33%, então
# o limite prático de PDF anexável fica em torno de 18 MB.
GMAIL_ATTACH_LIMIT_MB = 18.0


def _extract_djerj_pdf_url(html: str) -> str | None:
    """
    Extrai a URL real de download do PDF a partir do campo oculto hdnPrintUrl,
    renderizado pelo servidor em pdf.aspx com um GUID novo a cada requisição.

    O link antigo (gedcacheweb via App.PanelLoad.load) é JS morto deixado no
    template da SPA ExtJS: aparece sempre com o mesmo GEDID fixo, não importa
    a data/página pedida, e por isso nunca aponta pro diário correto.
    """
    match = re.search(r'id="hdnPrintUrl"\s+value="([^"]+)"', html)
    if not match:
        return None
    return urljoin(DJERJ_HOST, unescape(match.group(1)))


def download_latest_djerj_pdf(dest_dir: Path) -> Path | None:
    """Tenta baixar o PDF mais recente do DJERJ (Caderno I - Administrativo)."""
    today = datetime.now()
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Busca retrospectivamente para cobrir fins de semana, feriados e atrasos.
    for i in range(14):
        check_date = today - timedelta(days=i)

        # O DJERJ normalmente e disponibilizado apenas de segunda a sexta.
        if check_date.weekday() >= 5:
            continue

        date_str = check_date.strftime("%d/%m/%Y")
        iso_date = check_date.strftime("%Y-%m-%d")
        pdf_dest = dest_dir / f"djerj_{iso_date}.pdf"

        if pdf_dest.exists() and pdf_dest.stat().st_size > 1000:
            log.info("PDF do DJERJ de %s já existe localmente: %s", date_str, pdf_dest)
            return pdf_dest

        url = f"{DJERJ_HOST}/consultadje/pdf.aspx"
        params = {
            "dtPub": date_str,
            "caderno": "A",
            "pagina": "-1"
        }

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }

        log.info("Verificando se existe edição do DJERJ para %s...", date_str)
        try:
            with httpx.Client(headers=headers, follow_redirects=True, timeout=60) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()

                pdf_url = _extract_djerj_pdf_url(resp.text)
                if not pdf_url:
                    log.info("Edição do DJERJ de %s não encontrada ou sem PDF disponível.", date_str)
                    continue

                log.info("Edição do DJERJ encontrada para %s. Baixando PDF...", date_str)

                with client.stream("GET", pdf_url) as pdf_resp:
                    pdf_resp.raise_for_status()
                    content_type = pdf_resp.headers.get("content-type", "")
                    with open(pdf_dest, "wb") as f:
                        for chunk in pdf_resp.iter_bytes(chunk_size=8192):
                            f.write(chunk)

                size = pdf_dest.stat().st_size
                with open(pdf_dest, "rb") as f:
                    magic = f.read(5)

                # Validação real: o handler ASP.NET pode devolver uma página de
                # erro HTML (sessão/GUID/variação por IP) com status 200. Sem
                # checar a assinatura %PDF-, esse HTML seria salvo como .pdf e
                # anexado quebrado no e-mail — exatamente o sintoma de "não veio
                # PDF". O Monitor de Nova Iguaçu já faz essa checagem.
                log.info(
                    "Resposta do DJERJ de %s: status=%s content-type=%s tamanho=%.1f KB magic=%r",
                    date_str, pdf_resp.status_code, content_type, size / 1024, magic,
                )

                if magic != b"%PDF-" or size < 1000:
                    pdf_dest.unlink(missing_ok=True)
                    log.warning(
                        "Arquivo do DJERJ de %s descartado: não é um PDF válido (magic=%r, %d bytes).",
                        date_str, magic, size,
                    )
                    continue

                size_mb = size / 1024 / 1024
                if size_mb > GMAIL_ATTACH_LIMIT_MB:
                    # Gmail rejeita mensagens > 25 MB; com o overhead ~33% do
                    # base64, qualquer PDF acima de ~18 MB estoura o limite. A
                    # edição da homologação (ex.: 12/06/2026 = 24 MB) cai aqui.
                    log.warning(
                        "PDF do DJERJ de %s tem %.1f MB e provavelmente excede o limite "
                        "de anexo do Gmail (%.0f MB) — o e-mail deve enviar o link em vez do anexo.",
                        date_str, size_mb, GMAIL_ATTACH_LIMIT_MB,
                    )

                log.info("Download do DJERJ concluído para a data %s: %.1f KB", date_str, size / 1024)
                return pdf_dest
        except Exception as e:
            log.error("Erro ao tentar baixar PDF do DJERJ de %s: %s", date_str, e)

    return None


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

    # 3. Scraping Frente 3: DJERJ (consulta os ultimos 7 dias uteis)
    djerj_matches = check_djerj(djerj_kws, days_to_check=7)

    # Consolidando Matches
    new_matches = []
    
    # Adiciona matches do TJRJ
    for m in tjrj_matches:
        new_matches.append({
            **m,
            "detected_at": datetime.now().isoformat(),
            "id": stable_id("tjrj", m["url"])
        })

    # Adiciona matches da FGV
    for m in fgv_matches:
        new_matches.append({
            **m,
            "detected_at": datetime.now().isoformat(),
            "id": stable_id("fgv", m["url"])
        })

    # Adiciona matches do DJERJ (deduplica baseando em URL do Diário)
    seen_match_urls = {m["url"] for m in matches_history}
    for m in djerj_matches:
        if m["url"] not in seen_match_urls:
            new_matches.append({
                **m,
                "detected_at": datetime.now().isoformat(),
                "id": stable_id("djerj", m["url"])
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

    # Limpa arquivos PDF antigos da pasta tmp e baixa o PDF mais recente do DJERJ
    tmp_dir = ROOT / "tmp"
    if tmp_dir.exists():
        for f in tmp_dir.glob("*.pdf"):
            f.unlink(missing_ok=True)
    else:
        tmp_dir.mkdir(parents=True, exist_ok=True)

    djerj_pdf_path = download_latest_djerj_pdf(tmp_dir)

    # Metadados do PDF para o e-mail. Edições pesadas (ex.: homologação) passam
    # de 20 MB e estouram o limite de anexo do Gmail — nesse caso o workflow
    # manda o link da edição em vez do anexo, garantindo a entrega.
    djerj_pdf_exists = djerj_pdf_path is not None
    djerj_pdf_attachable = False
    djerj_pdf_url = ""
    if djerj_pdf_path is not None:
        size_mb = djerj_pdf_path.stat().st_size / 1024 / 1024
        djerj_pdf_attachable = size_mb <= GMAIL_ATTACH_LIMIT_MB
        # O stem é djerj_YYYY-MM-DD; reconstrói o link do visualizador oficial.
        try:
            iso = djerj_pdf_path.stem.replace("djerj_", "")
            date_br = datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
            djerj_pdf_url = (
                f"{DJERJ_HOST}/consultadje/consultaDJE.aspx"
                f"?dtPub={date_br}&caderno=A&pagina=-1"
            )
        except ValueError:
            djerj_pdf_url = f"{DJERJ_HOST}/consultadje/"

    # Geração do sumário e outputs do GitHub Actions
    matches_for_email = list(new_matches)
    resend_last_matches = os.environ.get("RESEND_LAST_MATCHES", "").strip().lower() in {"1", "true", "yes", "sim"}
    if resend_last_matches and not matches_for_email and matches_history:
        matches_for_email = matches_history[-5:]
        log.info("Reenviando %d matches anteriores por solicitação do workflow.", len(matches_for_email))

    has_watched_match = len(matches_for_email) > 0
    matched_names = []
    
    summary_lines = []
    summary_html = []

    # Detalha matches no e-mail
    if matches_for_email:
        if new_matches:
            summary_lines.append("🚨 OCORRÊNCIA ENCONTRADA:")
            summary_html.append("<h2 style='color: #e53e3e;'>🚨 Ocorrências de interesse encontradas:</h2>")
        else:
            summary_lines.append("🚨 REENVIO DE OCORRÊNCIAS JÁ ENCONTRADAS:")
            summary_html.append("<h2 style='color: #e53e3e;'>🚨 Reenvio das últimas ocorrências encontradas:</h2>")
        
        for m in matches_for_email:
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
    set_output("djerj_pdf_exists", "true" if djerj_pdf_exists else "false")
    set_output("djerj_pdf_attachable", "true" if djerj_pdf_attachable else "false")
    set_output("djerj_pdf_url", djerj_pdf_url)

    log.info("=== Processamento Concluído ===")


if __name__ == "__main__":
    run()

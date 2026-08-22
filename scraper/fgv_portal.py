"""
fgv_portal.py — Scraper para a página do concurso no portal da FGV.
"""

import httpx
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

log = logging.getLogger(__name__)

FGV_URL = "https://conhecimento.fgv.br/concursos/tjrjservidores25/01"
BASE_URL = "https://conhecimento.fgv.br"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def fetch_fgv_documents() -> list[dict]:
    """
    Busca a página da FGV e retorna a lista de documentos (título, link) ordenados (mais recentes no topo).
    """
    log.info("Buscando documentos do portal FGV...")
    
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, verify=False) as client:
            resp = client.get(FGV_URL)
            resp.raise_for_status()
    except Exception as e:
        log.error("Erro ao acessar portal FGV: %s", e)
        raise

    soup = BeautifulSoup(resp.text, "html.parser")
    documents = []
    seen_links = set()

    # No portal da FGV, os arquivos são links que geralmente contêm class="ext"
    # ou apontam para caminhos de arquivos (.pdf, /sites/default/files/...)
    links = soup.find_all("a", class_="ext")
    if not links:
        # Fallback caso a classe mude: busca links com pdf ou contendo arquivos de site
        links = soup.find_all("a", href=re.compile(r"\.pdf|/sites/default/files/"))

    log.info("Total de links de documentos encontrados no HTML da FGV: %d", len(links))

    for a in links:
        href = a.get("href", "").strip()
        if not href:
            continue
            
        full_url = urljoin(BASE_URL, href)
        if full_url in seen_links:
            continue
            
        seen_links.add(full_url)
        
        # Limpa o texto do link
        text = " ".join(a.get_text(separator=" ", strip=True).split())
        
        # Se for vazio, pega o título ou atributo similar
        if not text:
            text = a.get("title", "").strip()
            
        if not text:
            text = href.split("/")[-1].replace("_", " ").replace("-", " ")

        # Na FGV, as informações mais novas estão no topo da página.
        # Ao adicionar em ordem de aparição no DOM, o topo virá primeiro.
        documents.append({
            "title": text,
            "url": full_url
        })

    log.info("Processados %d documentos únicos da FGV", len(documents))
    return documents


def check_fgv_portal(previous_index: list[dict], keywords: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Verifica a página da FGV.
    Retorna: (novo_index, novos_documentos, matches_encontrados)
    """
    try:
        current_docs = fetch_fgv_documents()
    except Exception as e:
        log.error("Falha no check do portal FGV: %s", e)
        return previous_index, [], []

    previous_urls = {doc["url"] for doc in previous_index}
    new_docs = []
    matches = []

    # Regex para buscar as palavras-chave
    keywords_patterns = [re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE) for k in keywords]

    # As atualizações mais recentes estão no topo (início do array)
    for doc in current_docs:
        url = doc["url"]
        title = doc["title"]
        
        # Se é um link novo
        if url not in previous_urls:
            new_docs.append(doc)
            
            # Verifica se contém alguma palavra-chave
            matched_keywords = []
            for kw, pattern in zip(keywords, keywords_patterns):
                if len(kw) >= 5 and kw.upper() in title.upper():
                    matched_keywords.append(kw)
                elif pattern.search(title):
                    matched_keywords.append(kw)
            
            if matched_keywords:
                matches.append({
                    **doc,
                    "matched_keywords": matched_keywords,
                    "source": "fgv_portal"
                })

    new_index = current_docs
    return new_index, new_docs, matches

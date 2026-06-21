"""
tjrj_portal.py — Scraper para a página oficial do concurso TJRJ.
"""

import httpx
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

log = logging.getLogger(__name__)

PORTAL_URL = "https://www.tjrj.jus.br/concurso-de-provimento-efetivo/lxii-analista-judiciario-sem-e-com-especialidade-2025"
BASE_URL = "https://www.tjrj.jus.br"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def fetch_tjrj_documents() -> list[dict]:
    """
    Busca a página do concurso e retorna a lista de documentos (título, link).
    """
    log.info("Buscando documentos do portal TJRJ...")
    
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
            resp = client.get(PORTAL_URL)
            resp.raise_for_status()
    except Exception as e:
        log.error("Erro ao acessar portal TJRJ: %s", e)
        raise

    soup = BeautifulSoup(resp.text, "html.parser")
    documents = []
    seen_links = set()

    # Procura por todos os links contendo "/documents/" no href
    links = soup.find_all("a", href=re.compile(r"/documents/"))
    log.info("Total de links de documentos encontrados no HTML: %d", len(links))

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
        
        # Se o texto for muito curto ou sem sentido, tenta pegar atributos como title
        if len(text) < 4:
            text = a.get("title", "").strip()
            
        if not text:
            # Fallback para o nome do arquivo na URL
            text = href.split("/")[-1].replace("_", " ").replace("-", " ")

        documents.append({
            "title": text,
            "url": full_url
        })

    log.info("Processados %d documentos únicos do TJRJ", len(documents))
    return documents


def check_tjrj_portal(previous_index: list[dict], keywords: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Verifica a página do TJRJ.
    Retorna: (novo_index, novos_documentos, matches_encontrados)
    """
    try:
        current_docs = fetch_tjrj_documents()
    except Exception as e:
        log.error("Falha no check do portal TJRJ: %s", e)
        return previous_index, [], []

    previous_urls = {doc["url"] for doc in previous_index}
    new_docs = []
    matches = []

    # Regex para buscar as palavras-chave
    keywords_patterns = [re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE) for k in keywords]

    # Como as atualizações ficam no topo ou dispersas, checamos cada documento corrente
    for doc in current_docs:
        url = doc["url"]
        title = doc["title"]
        
        # Se é um link novo
        if url not in previous_urls:
            new_docs.append(doc)
            
            # Verifica se contém alguma palavra-chave
            matched_keywords = []
            for kw, pattern in zip(keywords, keywords_patterns):
                # Para termos longos ou compostos, fazemos busca direta
                if len(kw) >= 5 and kw.upper() in title.upper():
                    matched_keywords.append(kw)
                elif pattern.search(title):
                    matched_keywords.append(kw)
            
            if matched_keywords:
                matches.append({
                    **doc,
                    "matched_keywords": matched_keywords,
                    "source": "tjrj_portal"
                })

    # Reconstrói o índice ordenado (mantém a ordem encontrada na página)
    new_index = current_docs
    return new_index, new_docs, matches

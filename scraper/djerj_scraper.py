"""
djerj_scraper.py — Scraper para busca de palavras-chave no Diário da Justiça Eletrônico do RJ (DJERJ).
"""

import httpx
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

SEARCH_URL = "https://www3.tjrj.jus.br/consultadje/Result.aspx"
BASE_URL = "https://www3.tjrj.jus.br/consultadje/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def search_djerj_keyword_date(keyword: str, check_date: datetime) -> list[dict]:
    """
    Pesquisa por uma palavra-chave em uma data específica no Caderno I - Administrativo.
    Retorna uma lista de ocorrências encontradas.
    """
    date_str = check_date.strftime("%d/%m/%Y")
    params = {
        "dtInicio": date_str,
        "dtFim": date_str,
        "txtPesq": keyword,
        "tipoPesq": "CONT",
        "caderPesq": "A"  # Caderno I - Administrativo
    }

    log.info("Buscando no DJERJ [%s] por '%s'...", date_str, keyword)
    
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30) as client:
            resp = client.get(SEARCH_URL, params=params)
            resp.raise_for_status()
    except Exception as e:
        log.error("Erro na requisição ao DJERJ [%s, '%s']: %s", date_str, keyword, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    # Procura por links que apontam para consultaDJE.aspx
    links = soup.find_all("a", href=re.compile(r"consultaDJE\.aspx", re.IGNORECASE))
    
    for a in links:
        href = a.get("href", "").strip()
        if not href:
            continue
            
        full_url = urljoin(BASE_URL, href)
        
        # Limpa o texto da publicação (pode conter trechos do diário ou metadados)
        text = " ".join(a.get_text(separator=" ", strip=True).split())
        
        # Tenta capturar a linha ou bloco pai para dar contexto (snippet)
        snippet = ""
        parent = a.find_parent(["tr", "li", "p"])
        if parent:
            snippet = " ".join(parent.get_text(separator=" ", strip=True).split())
            # Trunca o snippet se for muito longo
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."
        else:
            snippet = text

        # Faz o parse dos parâmetros do link para extrair a página
        parsed_url = urlparse(full_url)
        query_params = parse_qs(parsed_url.query)
        pagina = query_params.get("pagina", [""])[0]

        results.append({
            "title": f"Menção no DJERJ de {date_str} (Pág. {pagina})",
            "url": full_url,
            "snippet": snippet,
            "date": check_date.strftime("%Y-%m-%d"),
            "pagina": pagina,
            "keyword": keyword
        })

    if results:
        log.info("Encontradas %d ocorrências para '%s' no DJERJ de %s", len(results), keyword, date_str)
    return results


def check_djerj(keywords: list[str], days_to_check: int = 3) -> list[dict]:
    """
    Executa a pesquisa no DJERJ para os últimos N dias para todas as palavras-chave.
    Retorna uma lista consolidada de ocorrências únicas encontradas.
    """
    all_results = []
    seen_urls = set()
    today = datetime.now()

    # Só verifica de segunda a sexta (diário administrativo costuma sair em dias úteis)
    # Mas como rodamos em cron, verificamos os últimos N dias calendarizados para cobrir fins de semana/atrasos
    dates_to_check = [today - timedelta(days=i) for i in range(days_to_check)]

    for check_date in dates_to_check:
        # Pula domingos (nenhuma publicação)
        if check_date.weekday() == 6:  # Sunday
            continue
            
        for kw in keywords:
            results = search_djerj_keyword_date(kw, check_date)
            for res in results:
                url = res["url"]
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append({
                        **res,
                        "source": "djerj_search"
                    })

    return all_results

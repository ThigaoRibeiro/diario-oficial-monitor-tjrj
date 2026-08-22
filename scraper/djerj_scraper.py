"""
DJERJ content search scraper.

The official result page is an ASP.NET table with image buttons, not regular
links. We parse each table row and build the public consultaDJE.aspx URL from
the publication date, notebook and page.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

SEARCH_URL = "https://www3.tjrj.jus.br/consultadje/Result.aspx"
VIEWER_URL = "https://www3.tjrj.jus.br/consultadje/consultaDJE.aspx"
BASE_URL = "https://www3.tjrj.jus.br/consultadje/"
DEFAULT_CADERNO = "A"
PERSON_NAME_BLOCKLIST = {
    "analista",
    "avaliacao",
    "aviso",
    "cargo",
    "convocacao",
    "dados",
    "engenheiro",
    "homologacao",
    "judiciario",
    "medica",
    "nomeacao",
    "posse",
    "resultado",
    "tjrj",
}
NAME_CONNECTORS = {"da", "das", "de", "do", "dos", "e"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://www3.tjrj.jus.br/consultadje/",
}


def _clean_text(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "get_text"):
        value = value.get_text(separator=" ", strip=True)
    return " ".join(str(value).split())


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def _caderno_code(label_or_code: str, fallback: str = DEFAULT_CADERNO) -> str:
    value = (label_or_code or "").strip()
    if value in {"A", "S", "C", "I", "E"}:
        return value

    folded = _fold(value)
    if "administrativo" in folded:
        return "A"
    if "2" in folded and "instancia" in folded:
        return "S"
    if "capital" in folded:
        return "C"
    if "interior" in folded:
        return "I"
    if "editais" in folded or "demais publicacoes" in folded:
        return "E"
    return fallback


def _is_probable_person_name(keyword: str) -> bool:
    if not keyword or any(ch.isdigit() for ch in keyword):
        return False
    if '"' in keyword:
        return False

    folded = _fold(re.sub(r"[^A-Za-zÀ-ÿ\s]", " ", keyword))
    tokens = [token for token in folded.split() if token not in NAME_CONNECTORS]
    if len(tokens) < 2:
        return False
    if any(token in PERSON_NAME_BLOCKLIST for token in tokens):
        return False
    return all(token.isalpha() for token in tokens)


def _query_for_keyword(keyword: str) -> str:
    keyword = (keyword or "").strip()
    if _is_probable_person_name(keyword):
        return f'"{keyword}"'
    return keyword


def _iso_date(date_br: str, fallback: datetime) -> str:
    try:
        return datetime.strptime(date_br, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return fallback.strftime("%Y-%m-%d")


def _make_viewer_url(date_br: str, caderno: str, pagina: str) -> str:
    params = {
        "dtPub": date_br,
        "caderno": _caderno_code(caderno),
        "pagina": str(pagina),
    }
    return f"{VIEWER_URL}?{urlencode(params)}"


def _extract_search_info(soup: BeautifulSoup) -> str:
    node = soup.find(id=re.compile(r"searchText$", re.IGNORECASE))
    return _clean_text(node)


def _parse_table_results(
    soup: BeautifulSoup,
    keyword: str,
    check_date: datetime,
    caderno: str = DEFAULT_CADERNO,
) -> list[dict]:
    table = soup.find("table", id=re.compile(r"_grid$", re.IGNORECASE))
    if table is None:
        table = soup.find("table", attrs={"name": "grid"})
    if table is None:
        return []

    results = []
    search_info = _extract_search_info(soup)

    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        date_br = _clean_text(cells[0])
        caderno_label = _clean_text(cells[1])
        pagina = _clean_text(cells[2])

        action = row.find("input", {"type": "image"})
        alt_text = _clean_text(action.get("alt")) if action else ""

        if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", date_br):
            match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", alt_text)
            if match:
                date_br = match.group(1)

        if not pagina:
            match = re.search(r"pagina\s+(\d+)", _fold(alt_text))
            if match:
                pagina = match.group(1)

        if not date_br or not pagina:
            continue

        caderno_code = _caderno_code(caderno_label, fallback=caderno)
        url = _make_viewer_url(date_br, caderno_code, pagina)
        snippet = alt_text or f"{date_br} - {caderno_label} - pagina {pagina}"

        results.append(
            {
                "title": f"Mencao no DJERJ de {date_br} (Pag. {pagina})",
                "url": url,
                "snippet": snippet,
                "date": _iso_date(date_br, check_date),
                "pagina": pagina,
                "caderno": caderno_code,
                "keyword": keyword,
                "matched_keywords": [keyword],
                "search_info": search_info,
            }
        )

    return results


def _parse_anchor_results(
    soup: BeautifulSoup,
    keyword: str,
    check_date: datetime,
) -> list[dict]:
    results = []
    for anchor in soup.find_all("a", href=re.compile(r"consultaDJE\.aspx", re.IGNORECASE)):
        href = anchor.get("href", "").strip()
        if not href:
            continue

        full_url = urljoin(BASE_URL, href)
        parsed_url = urlparse(full_url)
        query_params = parse_qs(parsed_url.query)
        pagina = query_params.get("pagina", [""])[0]
        date_br = query_params.get("dtPub", [check_date.strftime("%d/%m/%Y")])[0]
        text = _clean_text(anchor)

        parent = anchor.find_parent(["tr", "li", "p"])
        snippet = _clean_text(parent) if parent else text
        if len(snippet) > 300:
            snippet = snippet[:297] + "..."

        results.append(
            {
                "title": f"Mencao no DJERJ de {date_br} (Pag. {pagina})",
                "url": full_url,
                "snippet": snippet,
                "date": _iso_date(date_br, check_date),
                "pagina": pagina,
                "caderno": query_params.get("caderno", [DEFAULT_CADERNO])[0],
                "keyword": keyword,
                "matched_keywords": [keyword],
            }
        )
    return results


def parse_djerj_results(
    html: str,
    keyword: str,
    check_date: datetime,
    caderno: str = DEFAULT_CADERNO,
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = _parse_table_results(soup, keyword, check_date, caderno=caderno)
    if not results:
        results = _parse_anchor_results(soup, keyword, check_date)
    return results


def search_djerj_keyword_date(
    keyword: str,
    check_date: datetime,
    caderno: str = DEFAULT_CADERNO,
    client: httpx.Client | None = None,
) -> list[dict]:
    """
    Search one keyword on one publication date.
    """
    date_str = check_date.strftime("%d/%m/%Y")
    query_text = _query_for_keyword(keyword)
    params = {
        "dtInicio": date_str,
        "dtFim": date_str,
        "txtPesq": query_text,
        "tipoPesq": "CONT",
        "caderPesq": caderno,
    }

    if query_text == keyword:
        log.info("Buscando no DJERJ [%s] por '%s'...", date_str, keyword)
    else:
        log.info("Buscando no DJERJ [%s] por '%s' como frase exata...", date_str, keyword)

    close_client = client is None
    if client is None:
        client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, verify=False)

    try:
        resp = client.get(SEARCH_URL, params=params)
        resp.raise_for_status()
    except Exception as exc:
        log.error("Erro na requisicao ao DJERJ [%s, '%s']: %s", date_str, keyword, exc)
        return []
    finally:
        if close_client:
            client.close()

    results = parse_djerj_results(resp.text, keyword, check_date, caderno=caderno)
    if results:
        log.info(
            "Encontradas %d ocorrencias para '%s' no DJERJ de %s",
            len(results),
            keyword,
            date_str,
        )
    return results


def iter_business_dates(
    start_date: datetime | None = None,
    business_days: int = 7,
    max_calendar_days: int = 21,
):
    """
    Yield recent weekdays. DJERJ is normally published Monday-Friday, except
    holidays, so the caller still looks back enough days to cover gaps.
    """
    current = start_date or datetime.now()
    checked = 0
    offset = 0

    while checked < business_days and offset < max_calendar_days:
        check_date = current - timedelta(days=offset)
        offset += 1

        if check_date.weekday() >= 5:
            continue

        checked += 1
        yield check_date


def check_djerj(
    keywords: list[str],
    days_to_check: int = 7,
    start_date: datetime | None = None,
    caderno: str = DEFAULT_CADERNO,
) -> list[dict]:
    """
    Search the latest N business days for all keywords.
    """
    all_results_by_url: dict[str, dict] = {}

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, verify=False) as client:
        for check_date in iter_business_dates(start_date, business_days=days_to_check):
            for keyword in keywords:
                for result in search_djerj_keyword_date(
                    keyword,
                    check_date,
                    caderno=caderno,
                    client=client,
                ):
                    url = result["url"]
                    existing = all_results_by_url.get(url)
                    if existing is None:
                        all_results_by_url[url] = {
                            **result,
                            "source": "djerj_search",
                        }
                        continue

                    for matched in result.get("matched_keywords", [keyword]):
                        if matched not in existing["matched_keywords"]:
                            existing["matched_keywords"].append(matched)

    return list(all_results_by_url.values())

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from djerj_scraper import (
    _query_for_keyword,
    check_djerj,
    iter_business_dates,
    parse_djerj_results,
)


REALISTIC_RESULT_HTML = """
<html>
  <body>
    <span id="ctl00_ContentPlaceHolder1_searchText">
      Voce fez uma busca pelo texto 397050352 no diario publicado em 12/06/2026.
      (total de 1 registros, com mais de uma ocorrencia por registro).
    </span>
    <table name="grid" id="ctl00_ContentPlaceHolder1_grid">
      <tr>
        <th>Data de Publicacao</th><th>Caderno</th><th>Pagina</th><th>Acoes</th>
      </tr>
      <tr>
        <td><span id="ctl00_ContentPlaceHolder1_grid_ctl02_lblDtPub">12/06/2026</span></td>
        <td>I - Administrativo</td>
        <td>46</td>
        <td>
          <input type="image"
                 name="ctl00$ContentPlaceHolder1$grid$ctl02$ImageButton2"
                 alt="dia 12/06/2026, caderno I - Administrativo, pagina 46, nrpagina 1" />
        </td>
      </tr>
    </table>
  </body>
</html>
"""


class DjerjScraperTests(unittest.TestCase):
    def test_parse_real_result_table_builds_viewer_url(self):
        results = parse_djerj_results(
            REALISTIC_RESULT_HTML,
            "397050352",
            datetime(2026, 6, 12),
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["date"], "2026-06-12")
        self.assertEqual(results[0]["pagina"], "46")
        self.assertEqual(results[0]["caderno"], "A")
        self.assertEqual(results[0]["matched_keywords"], ["397050352"])
        self.assertEqual(
            results[0]["url"],
            "https://www3.tjrj.jus.br/consultadje/consultaDJE.aspx?"
            "dtPub=12%2F06%2F2026&caderno=A&pagina=46",
        )

    def test_person_name_uses_exact_phrase_query(self):
        self.assertEqual(
            _query_for_keyword("THIAGO RIBEIRO DA SILVA"),
            '"THIAGO RIBEIRO DA SILVA"',
        )
        self.assertEqual(_query_for_keyword("ENGENHEIRO DE DADOS"), "ENGENHEIRO DE DADOS")
        self.assertEqual(_query_for_keyword("397050352"), "397050352")

    def test_iter_business_dates_skips_weekend(self):
        dates = [
            item.strftime("%Y-%m-%d")
            for item in iter_business_dates(datetime(2026, 6, 21), business_days=4)
        ]

        self.assertEqual(
            dates,
            ["2026-06-19", "2026-06-18", "2026-06-17", "2026-06-16"],
        )

    def test_check_djerj_deduplicates_url_and_merges_keywords(self):
        def fake_search(keyword, check_date, caderno="A", client=None):
            return [
                {
                    "title": "Mencao no DJERJ de 12/06/2026 (Pag. 46)",
                    "url": "https://www3.tjrj.jus.br/consultadje/consultaDJE.aspx?dtPub=12%2F06%2F2026&caderno=A&pagina=46",
                    "snippet": "dia 12/06/2026, caderno I - Administrativo, pagina 46",
                    "date": "2026-06-12",
                    "pagina": "46",
                    "caderno": "A",
                    "keyword": keyword,
                    "matched_keywords": [keyword],
                }
            ]

        with patch("djerj_scraper.search_djerj_keyword_date", side_effect=fake_search):
            results = check_djerj(
                ["397050352", "ENGENHEIRO DE DADOS"],
                days_to_check=1,
                start_date=datetime(2026, 6, 19),
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "djerj_search")
        self.assertEqual(
            results[0]["matched_keywords"],
            ["397050352", "ENGENHEIRO DE DADOS"],
        )


if __name__ == "__main__":
    unittest.main()

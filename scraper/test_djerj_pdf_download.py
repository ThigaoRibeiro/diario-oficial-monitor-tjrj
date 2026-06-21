import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import _extract_djerj_pdf_url


class ExtractDjerjPdfUrlTests(unittest.TestCase):
    def test_extracts_and_resolves_hdn_print_url(self):
        html = (
            '<input type="hidden" name="hdnPrintUrl" id="hdnPrintUrl" '
            'value="/CONSULTADJE/Handlers/DownloadPdf.ashx?guid=257bba86-7758-4c6a-8560-b69a0e106bc4.pdf'
            '&amp;dtPub=2026-06-12&amp;caderno=A&amp;pagina=46" />'
        )

        url = _extract_djerj_pdf_url(html)

        self.assertEqual(
            url,
            "https://www3.tjrj.jus.br/CONSULTADJE/Handlers/DownloadPdf.ashx?"
            "guid=257bba86-7758-4c6a-8560-b69a0e106bc4.pdf&dtPub=2026-06-12&caderno=A&pagina=46",
        )

    def test_returns_none_when_edition_does_not_exist(self):
        # Resposta real do pdf.aspx para uma data sem edição (ex: fim de semana/feriado):
        # a pagina e renderizada sem o campo hdnPrintUrl.
        html = "<html><body><p>Nao ha publicacao para a data informada.</p></body></html>"

        self.assertIsNone(_extract_djerj_pdf_url(html))

    def test_ignores_stale_gedcacheweb_link_left_in_page_template(self):
        # Esse link estatico (App.PanelLoad.load / gedcacheweb) e JS morto que aparece
        # em toda resposta de consultaDJE.aspx com o mesmo GEDID fixo, nao importa a
        # data/pagina pedida. Nao deve mais ser usado como fonte do PDF.
        html = (
            "<script>App.PanelLoad.load({ url: "
            "'http://www1.tjrj.jus.br/gedcacheweb/default.aspx?GEDID=000499BA48226A287661D89D19E7F3454ADEC5045454534D' "
            "});</script>"
        )

        self.assertIsNone(_extract_djerj_pdf_url(html))


if __name__ == "__main__":
    unittest.main()

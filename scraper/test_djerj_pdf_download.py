import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from main import _extract_djerj_pdf_url, download_latest_djerj_pdf


PDF_ASPX_HTML = (
    '<input type="hidden" id="hdnPrintUrl" '
    'value="/CONSULTADJE/Handlers/DownloadPdf.ashx?guid=abc.pdf'
    '&amp;dtPub=2026-06-19&amp;caderno=A&amp;pagina=-1" />'
)


def _mock_get(url, *args, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    resp.text = PDF_ASPX_HTML
    resp.raise_for_status = lambda: None
    return resp


class _MockStream:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.headers = {"content-type": "application/pdf"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def raise_for_status(self):
        pass

    def iter_bytes(self, chunk_size=8192):
        yield self._payload


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


class DownloadValidationTests(unittest.TestCase):
    def test_accepts_valid_pdf(self):
        payload = b"%PDF-1.4 conteudo real" + b"0" * 2000
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            with patch("httpx.Client.get", side_effect=_mock_get), \
                 patch("httpx.Client.stream", return_value=_MockStream(payload)):
                result = download_latest_djerj_pdf(dest)

            self.assertIsNotNone(result)
            self.assertTrue(result.exists())
            self.assertEqual(result.read_bytes()[:5], b"%PDF-")

    def test_rejects_html_error_page_saved_as_pdf(self):
        # O handler ASP.NET as vezes devolve uma pagina de erro HTML com status
        # 200. Sem validar a assinatura, ela seria anexada como .pdf quebrado.
        payload = b"<html><body>Sessao expirada</body></html>" + b" " * 2000
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            with patch("httpx.Client.get", side_effect=_mock_get), \
                 patch("httpx.Client.stream", return_value=_MockStream(payload)):
                result = download_latest_djerj_pdf(dest)

            self.assertIsNone(result, "HTML disfarçado de PDF deveria ser rejeitado")
            self.assertEqual(list(dest.glob("*.pdf")), [], "Nenhum .pdf deveria sobrar no destino")


if __name__ == "__main__":
    unittest.main()

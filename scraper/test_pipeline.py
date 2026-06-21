"""
test_pipeline.py — Testa localmente o monitor TJRJ com requisições mockadas.
"""

import json
import logging
import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Adiciona o diretório do scraper ao path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("test")

# Mock HTML para o portal TJRJ
MOCK_TJRJ_HTML = """
<html>
  <body>
    <h1>LXII Concurso Público para Analista Judiciário</h1>
    <ul>
      <li><a href="/documents/d/guest/aviso_tj_n-_198_-2026_-_resultado_final_do_lxii_cp_e_homologacao">Aviso TJ nº 198/2026 - Resultado Final do LXII CP e Homologação</a></li>
      <li><a href="/documents/d/guest/edital_de_abertura_concurso_tjrj">Edital de Abertura do Concurso</a></li>
      <li><a href="/documents/d/guest/aviso_tj_n-_202_-2026_-_convocacao_engenheiro_de_dados_thiago">Aviso TJ nº 202/2026 - Convocação de TI (Engenheiro de Dados)</a></li>
    </ul>
  </body>
</html>
"""

# Mock HTML para o portal FGV
MOCK_FGV_HTML = """
<html>
  <body>
    <h2>Arquivos do concurso TJRJ</h2>
    <div class="arquivo">
      <span class="data">12/06/2026</span>
      <a class="ext" href="/sites/default/files/concursos/tjrjservidores25/aviso_198_homologacao.pdf">Aviso 198 - Homologação do Concurso</a>
    </div>
    <div class="arquivo">
      <span class="data">21/06/2026</span>
      <a class="ext" href="/sites/default/files/concursos/tjrjservidores25/aviso_tjrj_nomeacao_thiago.pdf">Aviso 250 - Nomeação do Candidato Thiago Ribeiro da Silva</a>
    </div>
  </body>
</html>
"""

# Mock HTML para o DJERJ
MOCK_DJERJ_HTML = """
<html>
  <body>
    <h3>Resultados da Pesquisa</h3>
    <table>
      <tr>
        <td>21/06/2026</td>
        <td>Caderno I - Administrativo</td>
        <td>
          <a href="consultaDJE.aspx?dtPub=21/06/2026&caderno=A&pagina=12&pesquisa=397050352">
            PRESIDÊNCIA: Nomeação de THIAGO RIBEIRO DA SILVA no cargo de Analista Judiciário - Engenheiro de Dados.
          </a>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


class MockStream:
    def __init__(self, *args, **kwargs):
        self.status_code = 200
        self.headers = {"content-type": "application/pdf"}
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    def raise_for_status(self):
        pass
    def iter_bytes(self, chunk_size=8192):
        # Precisa passar dos 1000 bytes: main.py descarta downloads menores
        # que isso por considerá-los uma resposta inválida/incompleta.
        yield b"%PDF-1.4 Mocked PDF content" + b"0" * 1000


def mock_get(url, *args, **kwargs):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    
    url_str = str(url)
    if "concurso-de-provimento-efetivo" in url_str:
        mock_resp.text = MOCK_TJRJ_HTML
    elif "concursos/tjrjservidores25" in url_str:
        mock_resp.text = MOCK_FGV_HTML
    elif "consultadje/Result.aspx" in url_str:
        mock_resp.text = MOCK_DJERJ_HTML
    elif "pdf.aspx" in url_str:
        mock_resp.text = (
            '<html><body><input type="hidden" id="hdnPrintUrl" '
            'value="/CONSULTADJE/Handlers/DownloadPdf.ashx?guid=mock-guid.pdf'
            '&amp;dtPub=2026-06-21&amp;caderno=A&amp;pagina=-1" /></body></html>'
        )
    else:
        mock_resp.text = "<html></html>"
        
    return mock_resp


class FullPipelineTests(unittest.TestCase):
    # NOTA: precisa estar dentro de uma unittest.TestCase para que
    # `python -m unittest discover` (usado no workflow do CI) realmente
    # execute este teste. Como função solta no módulo, ela é silenciosamente
    # ignorada pelo discovery — o CI reportava sucesso sem nunca rodá-la.
    @patch("httpx.Client.stream", return_value=MockStream())
    @patch("httpx.Client.get", side_effect=mock_get)
    def test_full_pipeline(self, mock_get_call, mock_stream_call):
        log.info("Iniciando simulação de teste local...")

        import main

        # Guarda os caminhos reais do projeto pra restaurar depois — o teste
        # roda o pipeline de verdade (main.run()) e NÃO pode escrever em
        # data/config/tmp reais, ou apaga/sobrescreve histórico de produção
        # (matches.json é append-only; um teste rodando ali destrói dados reais).
        original_root, original_config_dir, original_data_dir = main.ROOT, main.CONFIG_DIR, main.DATA_DIR

        os.environ["GITHUB_OUTPUT"] = "output_test.txt"
        Path("output_test.txt").unlink(missing_ok=True)

        try:
            with tempfile.TemporaryDirectory() as tmp_root:
                tmp_root = Path(tmp_root)
                main.ROOT = tmp_root
                main.CONFIG_DIR = tmp_root / "config"
                main.DATA_DIR = tmp_root / "data"

                # Roda o orquestrador num diretório isolado e descartável
                main.run()

                data_dir = main.DATA_DIR
                tjrj_idx = data_dir / "tjrj_portal_index.json"
                fgv_idx = data_dir / "fgv_portal_index.json"
                matches = data_dir / "matches.json"
                global_idx = data_dir / "global-index.json"

                self.assertTrue(tjrj_idx.exists(), "tjrj_portal_index.json não foi criado")
                self.assertTrue(fgv_idx.exists(), "fgv_portal_index.json não foi criado")
                self.assertTrue(matches.exists(), "matches.json não foi criado")
                self.assertTrue(global_idx.exists(), "global-index.json não foi criado")

                log.info("✅ Todos os arquivos JSON foram criados com sucesso!")

                # Verifica matches encontrados
                match_data = json.loads(matches.read_text(encoding="utf-8"))
                log.info("Matches carregados no histórico: %d", len(match_data))
                for m in match_data:
                    log.info("  → Match [%s]: %s", m["source"], m["title"])

                self.assertGreaterEqual(len(match_data), 3, "Deveria ter extraído pelo menos 3 matches nos mocks")

                # Valida que o GITHUB_OUTPUT foi escrito
                output_content = Path("output_test.txt").read_text(encoding="utf-8")
                log.info("\n── Outputs simulados para o GitHub ──\n%s", output_content)

                self.assertIn("has_watched_match=true", output_content, "Deveria acusar match de interesse")
                self.assertIn(
                    "djerj_pdf_exists=true", output_content,
                    "Deveria ter baixado o PDF do DJERJ via pdf.aspx/hdnPrintUrl",
                )

                tmp_pdfs = list((tmp_root / "tmp").glob("*.pdf"))
                self.assertTrue(tmp_pdfs, "Nenhum PDF foi salvo em tmp/")
                self.assertEqual(tmp_pdfs[0].read_bytes(), b"%PDF-1.4 Mocked PDF content" + b"0" * 1000)

                log.info("✅ Pipeline completo validado com sucesso!")

        finally:
            main.ROOT, main.CONFIG_DIR, main.DATA_DIR = original_root, original_config_dir, original_data_dir
            Path("output_test.txt").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

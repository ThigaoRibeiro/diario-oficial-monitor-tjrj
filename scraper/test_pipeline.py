"""
test_pipeline.py — Testa localmente o monitor TJRJ com requisições mockadas.
"""

import json
import logging
import sys
import os
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
    else:
        mock_resp.text = "<html></html>"
        
    return mock_resp


@patch("httpx.Client.get", side_effect=mock_get)
def test_full_pipeline(mock_get_call):
    log.info("Iniciando simulação de teste local...")
    
    # Define outputs fakes do GITHUB_OUTPUT
    os.environ["GITHUB_OUTPUT"] = "output_test.txt"
    Path("output_test.txt").unlink(missing_ok=True)
    
    try:
        import main
        # Força o carregamento de configurações limpas
        main.CONFIG_DIR = Path(__file__).parent.parent / "config"
        main.DATA_DIR = Path(__file__).parent.parent / "data"
        
        # Roda o orquestrador
        main.run()
        
        # Valida que os arquivos foram gerados
        data_dir = main.DATA_DIR
        tjrj_idx = data_dir / "tjrj_portal_index.json"
        fgv_idx = data_dir / "fgv_portal_index.json"
        matches = data_dir / "matches.json"
        global_idx = data_dir / "global-index.json"
        
        assert tjrj_idx.exists(), "tjrj_portal_index.json não foi criado"
        assert fgv_idx.exists(), "fgv_portal_index.json não foi criado"
        assert matches.exists(), "matches.json não foi criado"
        assert global_idx.exists(), "global-index.json não foi criado"
        
        log.info("✅ Todos os arquivos JSON foram criados com sucesso!")
        
        # Verifica matches encontrados
        match_data = json.loads(matches.read_text(encoding="utf-8"))
        log.info("Matches carregados no histórico: %d", len(match_data))
        for m in match_data:
            log.info("  → Match [%s]: %s", m["source"], m["title"])
            
        assert len(match_data) >= 3, "Deveria ter extraído pelo menos 3 matches nos mocks"
        
        # Valida que o GITHUB_OUTPUT foi escrito
        output_content = Path("output_test.txt").read_text(encoding="utf-8")
        log.info("\n── Outputs simulados para o GitHub ──\n%s", output_content)
        
        assert "has_watched_match=true" in output_content, "Deveria acusar match de interesse"
        
        log.info("✅ Pipeline completo validado com sucesso!")
        
    finally:
        # Limpa arquivo temporário
        Path("output_test.txt").unlink(missing_ok=True)


if __name__ == "__main__":
    test_full_pipeline()

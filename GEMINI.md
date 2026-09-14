# Regras e Memória do Projeto - Monitor Diário Oficial

Este arquivo define o contexto, regras de negócio e memória técnica para o assistente AI (Gemini) durante a manutenção deste repositório.

## 1. Regras de Web Scraping e Downloads de PDF

### SSL e Conectividade (DJERJ e TJRJ)
- **Desativação de verificação SSL necessária**: Os portais do DJERJ e TJRJ frequentemente apresentam certificados intermediários inconsistentes ou cabeçalhos HTTP legados (`Transfer-Encoding` duplicado).
- **HTTPX**: Sempre utilizar `verify=False` ao instanciar `httpx.Client` ou `httpx.AsyncClient` em [`scraper/djerj_scraper.py`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/scraper/djerj_scraper.py) e [`scraper/main.py`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/scraper/main.py).
- **Urllib**: Sempre usar `ssl._create_unverified_context()` no parâmetro `context` do `urllib.request.urlopen` em [`scraper/tjrj_portal.py`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/scraper/tjrj_portal.py).

### Baixando Edições e PDFs
- O download dos PDFs do DJERJ (`download_latest_djerj_pdf`) garante que o diário oficial seja armazenado localmente e indexado.
- Nunca remover o bypass de SSL durante refatorações dos scrapers, pois isso causa falhas de timeout e recusa de conexão nas rotinas automatizadas do GitHub Actions ([`.github/workflows/daily-scrape.yml`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/.github/workflows/daily-scrape.yml)).

---

## 2. Matchers e Notificações

- **`is_personal_match(match)`**: Filtra ocorrências específicas para os nomes de interesse configurados em `config/monitorados.json` ou via variável de ambiente `WATCH_NAMES`.
- **`is_cargo_convocacao_match(match)`**: Identifica convocações, nomeações, exames médicos ou posse relacionados ao cargo de **Engenheiro de Dados**, aplicando destaque visual no e-mail de alerta.

---

## 3. Estrutura do Projeto

- `scraper/`: Scripts de coleta e análise (`main.py`, `djerj_scraper.py`, `tjrj_portal.py`, `fgv_portal.py`).
- `config/monitorados.json`: Palavras-chave e nomes sob monitoramento.
- `data/`: Índices de busca e histórico de correspondências em formato JSON.
- `web/`: Interface estática para visualização dos resultados.

---

## 4. Status Atual do Concurso (Últimas Movimentações)

- **Documento Central de Acompanhamento**: [`DIARIO_DE_BORDO.md`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/DIARIO_DE_BORDO.md).
- **Última convocação relevante**: Publicada no **DJERJ nº 233/2026 de 21/08/2026** (Caderno I - Administrativo, Pág. 6 e Pág. 23).
- **Engenheiro de Dados (1ª Região - Ampla Concorrência)**:
  - 1º lugar: Gabriel Oliveira Silva Luz (Convocado para exames em 28/08/2026 e requisitos em 02/09/2026).
  - 2º lugar: Bruno Tourinho Tomas (Convocado para exames em 28/08/2026 e requisitos em 02/09/2026).
- **Candidato Monitorado**: Thiago Ribeiro da Silva (11º lugar - Ampla Concorrência, Inscrição: 397050352). Faltam 9 convocações para alcançá-lo.

---

## 5. Protocolo Obrigatório para Agentes AI (Diário de Bordo)

Sempre que o usuário solicitar informações, status do concurso ou perguntar se foi chamado:
1. **Ler o arquivo [`DIARIO_DE_BORDO.md`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/DIARIO_DE_BORDO.md)** antes de responder.
2. **Atualizar os dados locais** executando `git pull origin main` no repositório `diario-oficial-monitor` para obter as publicações coletadas pelo GitHub Actions.
3. **Verificar os dados mais recentes** em `data/matches.json` e `data/global-index.json` por ocorrências de `THIAGO RIBEIRO DA SILVA`, `397050352` e `ENGENHEIRO DE DADOS`.
4. **Registrar a checagem no [`DIARIO_DE_BORDO.md`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/DIARIO_DE_BORDO.md)** adicionando uma nova linha à tabela do "Histórico de Checagens e Interações".
5. **Responder ao usuário** informando claramente se houve novas convocações, qual o último colocado chamado e a distância atual para o Thiago.


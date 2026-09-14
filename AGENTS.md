# Instruções de Projeto - Monitor Concurso TJRJ

## 🎯 Objetivo do Projeto
Monitorar publicações do Diário da Justiça Eletrônico do Rio de Janeiro (DJERJ), portal do TJRJ e FGV para acompanhar as convocações e nomeações do concurso TJRJ, especialmente para o cargo de **Analista Judiciário - Engenheiro de Dados** (1ª Região - Ampla Concorrência).

---

## 👤 Candidato de Interesse
- **Nome:** THIAGO RIBEIRO DA SILVA
- **Inscrição:** `397050352`
- **Classificação:** **11º lugar** (Ampla Concorrência)
- **Status Atual da Fila:** 2 convocados até agora (1º Gabriel Oliveira Silva Luz e 2º Bruno Tourinho Tomas). Faltam 9 posições para o Thiago.

---

## 📋 Protocolo Obrigatório para Agentes (Diário de Bordo)
Toda vez que o usuário interagir neste workspace ou perguntar sobre o concurso / convocações:

1. **Consultar o Diário de Bordo:** Leia [`DIARIO_DE_BORDO.md`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/DIARIO_DE_BORDO.md).
2. **Sincronizar dados mais recentes:** Execute `git pull origin main` no diretório do projeto para obter as últimas atualizações gravadas pelo GitHub Actions.
3. **Realizar a busca ativa:**
   - Procure por `THIAGO RIBEIRO DA SILVA` e `397050352` nos arquivos `data/matches.json` e `data/global-index.json`.
   - Verifique novos matches com o termo `ENGENHEIRO DE DADOS` ou convocações publicadas.
4. **Registrar no Diário de Bordo:** Adicione uma nova linha no arquivo [`DIARIO_DE_BORDO.md`](file:///c:/Users/LENOVO/Documents/Projects/Monitor_Thiago/diario-oficial-monitor/DIARIO_DE_BORDO.md) na tabela `Histórico de Checagens e Interações`, detalhando data/hora, resultado da checagem e fila atual.
5. **Salvar a documentação no Git:** Comite as alterações do `DIARIO_DE_BORDO.md` (`git add DIARIO_DE_BORDO.md; git commit -m "docs: atualiza diario de bordo com checagem de DD/MM/AAAA"`) e faça `git push origin main`.
6. **Reportar ao usuário:** Apresente os resultados de forma clara, amigável e objetiva.

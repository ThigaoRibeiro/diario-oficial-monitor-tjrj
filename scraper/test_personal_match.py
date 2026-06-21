import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import is_personal_match


class IsPersonalMatchTests(unittest.TestCase):
    def test_inscription_number_is_personal(self):
        self.assertTrue(is_personal_match({"matched_keywords": ["397050352"]}))

    def test_full_name_is_personal(self):
        self.assertTrue(is_personal_match({"matched_keywords": ["THIAGO RIBEIRO DA SILVA"]}))

    def test_djerj_keyword_field_is_supported(self):
        # matches do djerj_search usam "keyword" em vez de "matched_keywords"
        self.assertTrue(is_personal_match({"keyword": "397050352"}))

    def test_generic_concurso_keywords_are_not_personal(self):
        for kw in ["RESULTADO", "AVISO TJ", "HOMOLOGAÇÃO", "CONVOCAÇÃO",
                   "ENGENHEIRO DE DADOS", "ANALISTA JUDICIÁRIO - ENGENHEIRO DE DADOS"]:
            self.assertFalse(
                is_personal_match({"matched_keywords": [kw]}),
                f"'{kw}' não deveria contar como match pessoal",
            )

    def test_mixed_keywords_personal_wins(self):
        # se o nome aparece junto de palavras genéricas, ainda é pessoal
        self.assertTrue(
            is_personal_match({"matched_keywords": ["RESULTADO", "THIAGO RIBEIRO DA SILVA"]})
        )

    def test_no_keywords_is_not_personal(self):
        self.assertFalse(is_personal_match({"title": "algo", "url": "x"}))


if __name__ == "__main__":
    unittest.main()

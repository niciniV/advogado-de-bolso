from __future__ import annotations

from datetime import date, timedelta

from advogado_de_bolso.tools.calculos import (
    calcular_prazo_arrependimento,
    calcular_prazo_reclamacao_vicio,
)


class TestCalcularPrazoReclamacaoVicio:
    def test_produto_nao_duravel_30_dias(self):
        result = calcular_prazo_reclamacao_vicio("nao_duravel", "2025-01-15")
        assert "30 dias" in result
        assert "2025-02-14" in result

    def test_produto_duravel_90_dias(self):
        result = calcular_prazo_reclamacao_vicio("duravel", "2025-01-15")
        assert "90 dias" in result
        assert "2025-04-15" in result

    def test_servico_30_dias(self):
        result = calcular_prazo_reclamacao_vicio("servico", "2025-01-15")
        assert "30 dias" in result
        assert "2025-02-14" in result

    def test_tipo_invalido_retorna_erro(self):
        result = calcular_prazo_reclamacao_vicio("invalido", "2025-01-15")
        assert "invalido" in result.lower()

    def test_data_invalida_retorna_erro(self):
        result = calcular_prazo_reclamacao_vicio("duravel", "data-ruim")
        assert "invalida" in result.lower() or "formato" in result.lower()

    def test_prazo_expirado_contem_aviso(self):
        data_passada = (date.today() - timedelta(days=365)).isoformat()
        result = calcular_prazo_reclamacao_vicio("duravel", data_passada)
        assert "EXPIRADO" in result

    def test_prazo_valido_dentro_do_prazo(self):
        data_futura = date.today().isoformat()
        result = calcular_prazo_reclamacao_vicio("duravel", data_futura)
        assert "dentro do prazo" in result


class TestCalcularPrazoArrependimento:
    def test_prazo_7_dias_corridos(self):
        result = calcular_prazo_arrependimento("2025-06-01")
        assert "7 dias" in result
        assert "2025-06-08" in result

    def test_data_invalida_retorna_erro(self):
        result = calcular_prazo_arrependimento("nao-e-data")
        assert "invalida" in result.lower() or "formato" in result.lower()

    def test_contain_artigo_49(self):
        result = calcular_prazo_arrependimento("2025-06-01")
        assert "art. 49" in result.lower() or "artigo 49" in result.lower()

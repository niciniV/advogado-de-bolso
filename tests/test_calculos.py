from __future__ import annotations

from datetime import date

from advogado_de_bolso.contracts import DeadlineResult
from advogado_de_bolso.tools.calculos import calcular_prazo_consumidor


class TestReclamacaoVicio:
    def test_produto_duravel_90_dias(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-01-15",
            tipo_item="produto_duravel",
        )
        assert isinstance(result, DeadlineResult)
        assert result.tipo_prazo == "reclamacao_vicio"
        assert result.dias == 90
        assert result.data_inicio == date(2025, 1, 15)
        assert result.data_limite == date(2025, 4, 15)
        assert result.base_legal == "CDC art. 26"
        assert result.item_label == "produto_duravel"
        assert result.vicio_oculto is False

    def test_produto_nao_duravel_30_dias(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-01-15",
            tipo_item="produto_nao_duravel",
        )
        assert isinstance(result, DeadlineResult)
        assert result.tipo_prazo == "reclamacao_vicio"
        assert result.dias == 30
        assert result.data_inicio == date(2025, 1, 15)
        assert result.data_limite == date(2025, 2, 14)
        assert result.base_legal == "CDC art. 26"
        assert result.item_label == "produto_nao_duravel"
        assert result.vicio_oculto is False

    def test_servico_duravel_90_dias(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-03-01",
            tipo_item="servico_duravel",
        )
        assert isinstance(result, DeadlineResult)
        assert result.tipo_prazo == "reclamacao_vicio"
        assert result.dias == 90
        assert result.data_inicio == date(2025, 3, 1)
        assert result.data_limite == date(2025, 5, 30)
        assert result.base_legal == "CDC art. 26"
        assert result.item_label == "servico_duravel"

    def test_servico_nao_duravel_30_dias(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-03-01",
            tipo_item="servico_nao_duravel",
        )
        assert isinstance(result, DeadlineResult)
        assert result.tipo_prazo == "reclamacao_vicio"
        assert result.dias == 30
        assert result.data_inicio == date(2025, 3, 1)
        assert result.data_limite == date(2025, 3, 31)
        assert result.base_legal == "CDC art. 26"
        assert result.item_label == "servico_nao_duravel"

    def test_vicio_oculto_flag_true_uses_evidente_nota(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-06-01",
            tipo_item="produto_duravel",
            vicio_oculto=True,
        )
        assert isinstance(result, DeadlineResult)
        assert result.vicio_oculto is True
        assert "evidente" in result.nota.lower()

    def test_vicio_aparente_flag_false_uses_entrega_nota(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-06-01",
            tipo_item="produto_duravel",
            vicio_oculto=False,
        )
        assert isinstance(result, DeadlineResult)
        assert result.vicio_oculto is False
        assert "entrega" in result.nota.lower() or "conclusao" in result.nota.lower()

    def test_sem_tipo_item_retorna_erro_string(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-01-15",
        )
        assert isinstance(result, str)
        assert "necessario" in result.lower() or "tipo" in result.lower()


class TestArrependimento:
    def test_7_dias_corridos(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="arrependimento",
            data_inicio_prazo="2025-06-01",
        )
        assert isinstance(result, DeadlineResult)
        assert result.tipo_prazo == "arrependimento"
        assert result.dias == 7
        assert result.data_inicio == date(2025, 6, 1)
        assert result.data_limite == date(2025, 6, 8)
        assert result.base_legal == "CDC art. 49"
        assert result.item_label is None
        assert result.vicio_oculto is False

    def test_nota_menciona_recebimento_ou_contratacao(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="arrependimento",
            data_inicio_prazo="2025-06-01",
        )
        assert isinstance(result, DeadlineResult)
        assert "recebimento" in result.nota.lower() or "contratacao" in result.nota.lower()


class TestEntradaInvalida:
    def test_data_invalida_retorna_erro(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="data-ruim",
            tipo_item="produto_duravel",
        )
        assert isinstance(result, str)
        assert "invalida" in result.lower()

    def test_tipo_prazo_invalido_retorna_erro(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="invalido",  # type: ignore[arg-type]
            data_inicio_prazo="2025-01-15",
        )
        assert isinstance(result, str)
        assert "invalido" in result.lower()


def test_calculos_does_not_emit_prose_string_on_success():
    """Hard guard: success path must never return a plain string."""
    result = calcular_prazo_consumidor(
        tipo_prazo="arrependimento",
        data_inicio_prazo="2025-06-01",
    )
    assert not isinstance(result, str)
    assert isinstance(result, DeadlineResult)

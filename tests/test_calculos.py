from __future__ import annotations

from advogado_de_bolso.tools.calculos import calcular_prazo_consumidor


class TestReclamacaoVicio:
    def test_produto_duravel_90_dias(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-01-15",
            tipo_item="produto_duravel",
        )
        assert "90 dias" in result
        assert "2025-04-15" in result
        assert "art. 26" in result.lower()

    def test_produto_nao_duravel_30_dias(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-01-15",
            tipo_item="produto_nao_duravel",
        )
        assert "30 dias" in result
        assert "2025-02-14" in result
        assert "art. 26" in result.lower()

    def test_servico_duravel_90_dias(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-03-01",
            tipo_item="servico_duravel",
        )
        assert "90 dias" in result
        assert "2025-05-30" in result
        assert "art. 26" in result.lower()

    def test_servico_nao_duravel_30_dias(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-03-01",
            tipo_item="servico_nao_duravel",
        )
        assert "30 dias" in result
        assert "2025-03-31" in result
        assert "art. 26" in result.lower()

    def test_vicio_oculto_menciona_data_evidente(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-06-01",
            tipo_item="produto_duravel",
            vicio_oculto=True,
        )
        assert "ficou evidente" in result

    def test_vicio_aparente_menciona_entrega(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-06-01",
            tipo_item="produto_duravel",
            vicio_oculto=False,
        )
        assert "entrega" in result or "conclusao" in result

    def test_sem_tipo_item_retorna_erro(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="2025-01-15",
        )
        assert "necessario" in result.lower() or "tipo" in result.lower()


class TestArrependimento:
    def test_7_dias_corridos(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="arrependimento",
            data_inicio_prazo="2025-06-01",
        )
        assert "7 dias" in result
        assert "2025-06-08" in result
        assert "art. 49" in result.lower()

    def test_menciona_recebimento_ou_contratacao(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="arrependimento",
            data_inicio_prazo="2025-06-01",
        )
        assert "recebimento" in result or "contratacao" in result


class TestEntradaInvalida:
    def test_data_invalida_retorna_erro(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="reclamacao_vicio",
            data_inicio_prazo="data-ruim",
            tipo_item="produto_duravel",
        )
        assert "invalida" in result.lower()

    def test_tipo_prazo_invalido_retorna_erro(self):
        result = calcular_prazo_consumidor(
            tipo_prazo="invalido",  # type: ignore[arg-type]
            data_inicio_prazo="2025-01-15",
        )
        assert "invalido" in result.lower()

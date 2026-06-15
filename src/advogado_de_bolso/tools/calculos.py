"""Tools de calculo de prazos previstos no CDC."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from advogado_de_bolso.contracts import DeadlineResult, TipoPrazo

TipoItem = Literal[
    "produto_duravel",
    "produto_nao_duravel",
    "servico_duravel",
    "servico_nao_duravel",
]

_PRAZOS_VICIO: dict[str, int] = {
    "produto_nao_duravel": 30,
    "servico_nao_duravel": 30,
    "produto_duravel": 90,
    "servico_duravel": 90,
}

_TIPOS_VALIDOS = ", ".join(f"'{t}'" for t in _PRAZOS_VICIO)


def _parse_data(data_str: str) -> date | str:
    try:
        return date.fromisoformat(data_str)
    except (ValueError, TypeError):
        return (
            f"Data invalida: '{data_str}'. Use o formato ISO AAAA-MM-DD "
            "(exemplo: 2025-01-15)."
        )


def _calcular_reclamacao_vicio(
    data_inicio: date,
    tipo_item: TipoItem | None,
    vicio_oculto: bool,
) -> DeadlineResult:
    if tipo_item is None:
        raise ValueError(
            "Para calcular o prazo de reclamacao por vicio (CDC art. 26), "
            "e necessario informar o tipo do item. "
            f"Use um dos seguintes valores: {_TIPOS_VALIDOS}."
        )

    if tipo_item not in _PRAZOS_VICIO:
        raise ValueError(
            f"Tipo de item invalido: '{tipo_item}'. "
            f"Use um dos seguintes valores: {_TIPOS_VALIDOS}."
        )

    dias = _PRAZOS_VICIO[tipo_item]
    limite = data_inicio + timedelta(days=dias)

    if vicio_oculto:
        nota = "a data em que o vicio oculto ficou evidente ao consumidor"
    else:
        nota = "a data de entrega do produto ou de conclusao do servico"

    return DeadlineResult(
        tipo_prazo="reclamacao_vicio",
        data_inicio=data_inicio,
        data_limite=limite,
        dias=dias,
        base_legal="CDC art. 26",
        item_label=tipo_item,
        vicio_oculto=vicio_oculto,
        nota=nota,
    )


def _calcular_arrependimento(data_inicio: date) -> DeadlineResult:
    limite = data_inicio + timedelta(days=7)
    return DeadlineResult(
        tipo_prazo="arrependimento",
        data_inicio=data_inicio,
        data_limite=limite,
        dias=7,
        base_legal="CDC art. 49",
        item_label=None,
        vicio_oculto=False,
        nota=(
            "Use a data de recebimento do produto ou da contratacao do servico, "
            "nao necessariamente a data do pagamento. Confirme os fatos "
            "concretos antes de concluir."
        ),
    )


def calcular_prazo_consumidor(
    tipo_prazo: TipoPrazo,
    data_inicio_prazo: str,
    tipo_item: TipoItem | None = None,
    vicio_oculto: bool = False,
) -> DeadlineResult | str:
    """Calcula prazos do CDC para reclamacao por vicio ou direito de arrependimento.

    Base legal:
        - CDC art. 26: prazo para reclamar de vicio (defeito) em produto ou servico.
        - CDC art. 49: prazo de arrependimento para compras fora do estabelecimento.

    Args:
        tipo_prazo: 'reclamacao_vicio' ou 'arrependimento'.
        data_inicio_prazo: Data inicial juridicamente relevante em formato ISO AAAA-MM-DD.
            Para vicio aparente: data de entrega do produto ou conclusao do servico.
            Para vicio oculto: data em que o defeito ficou evidente.
            Para arrependimento: data de recebimento do produto ou contratacao do servico.
        tipo_item: Obrigatorio apenas para reclamacao_vicio. Um de:
            'produto_duravel', 'produto_nao_duravel',
            'servico_duravel', 'servico_nao_duravel'.
        vicio_oculto: Se True, indica que o vicio e oculto (nao aparente).
            Relevante apenas para reclamacao_vicio.

    Returns:
        Em caso de sucesso: `DeadlineResult` com a data limite estimada, o
        artigo do CDC aplicavel e a data inicial correta. Em caso de erro
        (data invalida, tipo de item ausente/invalido, tipo de prazo
        desconhecido): uma string para o LLM retransmitir ao usuario.
    """
    parsed = _parse_data(data_inicio_prazo)
    if isinstance(parsed, str):
        return parsed

    if tipo_prazo == "reclamacao_vicio":
        try:
            return _calcular_reclamacao_vicio(parsed, tipo_item, vicio_oculto)
        except ValueError as exc:
            return str(exc)

    if tipo_prazo == "arrependimento":
        return _calcular_arrependimento(parsed)

    return (
        f"Tipo de prazo invalido: '{tipo_prazo}'. "
        "Use 'reclamacao_vicio' ou 'arrependimento'."
    )

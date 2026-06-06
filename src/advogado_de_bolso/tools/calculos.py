"""Tools de calculo de prazos previstos no CDC."""

from __future__ import annotations

from datetime import date, timedelta


def calcular_prazo_reclamacao_vicio(
    tipo_produto: str,
    data_aquisicao: str,
) -> str:
    """Calcula o prazo para reclamacao por vicio (defeito) em produto ou servico.

    Base legal: CDC art. 26.
        - Produtos NAO duraveis: 30 dias
        - Produtos duraveis: 90 dias
        - Servicos: 30 dias

    Args:
        tipo_produto: 'duravel', 'nao_duravel' ou 'servico'.
        data_aquisicao: Data em formato ISO AAAA-MM-DD.

    Returns:
        Texto indicando a data limite ou mensagem de erro.
    """
    prazos = {
        "nao_duravel": 30,
        "duravel": 90,
        "servico": 30,
    }

    if tipo_produto not in prazos:
        return (
            f"Tipo de produto invalido: '{tipo_produto}'. "
            "Use 'duravel', 'nao_duravel' ou 'servico'."
        )

    try:
        data = date.fromisoformat(data_aquisicao)
    except ValueError:
        return f"Data invalida: '{data_aquisicao}'. Use o formato ISO AAAA-MM-DD."

    dias = prazos[tipo_produto]
    limite = data + timedelta(days=dias)
    hoje = date.today()
    status = " (PRAZO EXPIRADO)" if limite < hoje else " (dentro do prazo)"
    return (
        f"Prazo de {dias} dias para reclamacao por vicio (CDC art. 26){status}. "
        f"Data limite: {limite.isoformat()} (a partir de {data.isoformat()}). "
        f"Hoje: {hoje.isoformat()}."
    )


def calcular_prazo_arrependimento(data_compra: str) -> str:
    """Calcula o prazo de arrependimento para compras fora do estabelecimento.

    Base legal: CDC art. 49 - 7 dias corridos a partir da entrega do produto
    ou da contratacao do servico.

    Args:
        data_compra: Data da compra ou entrega em formato ISO AAAA-MM-DD.

    Returns:
        Texto indicando a data limite do direito de arrependimento.
    """
    try:
        data = date.fromisoformat(data_compra)
    except ValueError:
        return f"Data invalida: '{data_compra}'. Use o formato ISO AAAA-MM-DD."

    limite = data + timedelta(days=7)
    return (
        f"Prazo de arrependimento (CDC art. 49) ate {limite.isoformat()} "
        f"(7 dias corridos a partir de {data.isoformat()})."
    )

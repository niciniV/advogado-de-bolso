import express from "express";
import path from "path";
import fs from "fs";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI, Type } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const app = express();
app.use(express.json());

const PORT = 3000;

// Lazy initialization of Gemini
let aiClient: GoogleGenAI | null = null;
function getAiClient(): GoogleGenAI | null {
  const key = process.env.GEMINI_API_KEY;
  if (!key || key === "MY_GEMINI_API_KEY") {
    console.warn("GEMINI_API_KEY is not configured or using placeholder. Fallback simulator will be used.");
    return null;
  }
  if (!aiClient) {
    aiClient = new GoogleGenAI({
      apiKey: key,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build',
        }
      }
    });
  }
  return aiClient;
}

// Brazilian Consumer Law simulated database & calculator fallback
const simulatedResponses = [
  {
    keywords: ["celular", "online", "arrependi", "devolu", "internet", "aplicativo", "loja disse que não aceita"],
    data: {
      stepTitle: "Entendi o caso (Simulação)",
      stepContent: "Você realizou uma compra de um produto (celular) fora do estabelecimento comercial (online) e deseja exercer o direito de arrependimento logo após o recebimento, mas enfrentou recusa da loja.",
      relevantTitle: "O que pode ser relevante",
      relevantContent: "O Código de Defesa do Consumidor (CDC), em seu artigo 49, garante o direito de arrependimento em até 7 dias corridos para compras feitas fora do estabelecimento comercial (internet, app, telefone), independentemente do motivo. O cancelamento gera direito a reembolso integral dos valores pagos, incluindo frete.",
      calcPerformed: true,
      deadline: {
        title: "Prazo calculado de arrependimento",
        type: "Direito de Desistência - Art. 49 CDC",
        startDate: "13/06/2026 (Hoje)",
        endDate: "20/06/2026",
        base: "CDC Artigo 49 (7 dias corridos no total)",
        note: "O prazo se inicia no dia seguinte ao recebimento do produto."
      },
      questions: [
        "A compra foi feita pela internet, telefone ou aplicativo?",
        "Você recebeu o produto em qual data exata?",
        "O produto está completo, com embalagem e acessórios originais?"
      ],
      suggestiveText: "Com base nisso, posso preparar uma mensagem formal para a loja pedindo o cancelamento e reembolso.",
      quickReplies: ["Preparar mensagem", "Continuar orientação", "Fazer outra pergunta"],
      templateLetter: `À [Nome da Loja/Plataforma]
Assunto: Exercício do Direito de Arrependimento (Art. 49 do CDC) - Compra [ID do Pedido]

Prezados,

Por meio deste documento, formalizo o pedido de cancelamento da compra do produto Celular adquirido de forma online através de sua plataforma de e-commerce.

Considerando que recebi o produto em [Data de Recebimento] e o prazo legal de 7 (sete) dias corridos estabelecido pelo Artigo 49 do Código de Defesa do Consumidor ainda está em vigor, solicito o cancelamento imediato da transação e a restituição integral das quantias pagas, nos termos da lei.

Aguardo orientações para a devolução/coleta do aparelho celular sem custos.

Atenciosamente,
[Seu Nome completo]`
    }
  },
  {
    keywords: ["cobrança", "duplicada", "indevida", "cartão", "pagamento", "valor", "banco"],
    data: {
      stepTitle: "Entendi o caso de Cobrança Indevida",
      stepContent: "Você identificou uma cobrança em duplicidade ou valor indevido na sua conta ou fatura de cartão e necessita reaver esse valor.",
      relevantTitle: "O que diz a Lei (CDC Art. 42)",
      relevantContent: "Conforme o Parágrafo Único do Artigo 42 do Código de Defesa do Consumidor, o consumidor cobrado em quantia indevida tem direito à repetição do indébito, por valor igual ao dobro do que pagou em excesso, acrescido de correção monetária e juros legais, salvo hipótese de engano justificável.",
      calcPerformed: true,
      deadline: {
        title: "Prazo para reclamação",
        type: "Cobrança Indevida - Restituição",
        startDate: "13/06/2026 (Hoje)",
        endDate: "13/06/2031",
        base: "Art. 27 CDC (Prazo prescricional)",
        note: "Você tem até 5 anos para exigir judicialmente a restituição de cobrança indevida."
      },
      questions: [
        "A instituição já foi informada sobre o erro de cobrança?",
        "Você já efetuou o pagamento do valor cobrado em duplicidade?",
        "Possui o comprovante de pagamento e a fatura com as duas cobranças?"
      ],
      suggestiveText: "Podemos preparar uma notificação formal para contestar a cobrança e solicitar a devolução em dobro do montante indébito.",
      quickReplies: ["Preparar contestação", "Continuar orientação", "Fazer outra pergunta"],
      templateLetter: `À [Nome da Instituição Financeira / Empresa]
Assunto: Contestação de Cobrança Duplicada e Repetição de Indébito (Art. 42, Parágrafo Único CDC)

Prezados,

Identifiquei em minha fatura/extrato datado de [Data] uma cobrança em duplicidade no valor de [Valor], referente ao serviço/produto [Descrição].

Tendo em vista que paguei o valor em duplicidade indevidamente, solicito a imediata devolução da quantia em excesso calculada em dobro, correspondendo a [Valor Dobrado], conforme o artigo 42, parágrafo único do CDC brasileiro.

Anexo a esta notificação os comprovantes de transação correspondentes.

Atenciosamente,
[Seu Nome completo]`
    }
  },
  {
    keywords: ["atraso", "entrega", "não chegou", "atrasado", "prazo", "transportadora"],
    data: {
      stepTitle: "Entendi o caso de Atraso na Entrega",
      stepContent: "O prazo estipulado pela empresa para a entrega do seu pedido não foi cumprido e você ainda não recebeu o produto ou deseja cancelar.",
      relevantTitle: "Seus Direitos (CDC Art. 35)",
      relevantContent: "O atraso na entrega caracteriza descumprimento de oferta por parte do fornecedor. O Código de Defesa do Consumidor, no art. 35, confere três opções alternativas gratuitas ao consumidor: exigir a entrega imediata forcada, aceitar outro produto equivalente, ou cancelar a compra com devolução integral corrigida monetariamente dos valores já pagos.",
      calcPerformed: true,
      deadline: {
        title: "Resolução do atraso",
        type: "Cumprimento de Oferta - Art. 35 CDC",
        startDate: "13/06/2026 (Hoje)",
        endDate: "Imediata",
        base: "CDC Artigo 35",
        note: "A empresa deve resolver as opções apresentadas de forma célere ou imediata caso solicitado."
      },
      questions: [
        "Qual era o prazo original limite da entrega do produto?",
        "Qual é o produto e qual das três opções você prefere exercer?",
        "A empresa forneceu alguma justificativa ou nova data?"
      ],
      suggestiveText: "Deseja que preparemos uma notificação notificando formalmente o fornecedor para entrega sob as penas de cancelamento?",
      quickReplies: ["Preparar notificação", "Continuar orientação", "Fazer outra pergunta"],
      templateLetter: `Ao [Nome do Estabelecimento / E-commerce]
Assunto: Notificação por Descumprimento de Prazo de Entrega (Art. 35 do CDC)

Prezados,

Efetuei a compra do produto [Nome do Produto], sob o pedido nº [ID do Pedido], com promessa de entrega limite para a data de [Prazo de Entrega].

Ocorre que até o presente momento o item não foi entregue, incorrendo em mora contratual e inadimplemento da oferta divulgada.

Com fulcro no Artigo 35 do Código de Defesa do Consumidor brasileiro, exijo o [Selecione: cancelamento da compra com estorno imediato / entrega forçada imediata do produto no prazo máximo de 48 horas].

No aguardo de breve resposta sob pena de adoção de medidas junto aos órgãos de proteção ao consumidor.

Atenciosamente,
[Seu Nome completo]`
    }
  }
];

// POST /api/chat
app.post("/api/chat", async (req, res) => {
  const { message, history, responseStyle } = req.body;

  if (!message) {
    return res.status(400).json({ error: "Mensagem é obrigatória." });
  }

  // Check if Gemini AI client is available
  const ai = getAiClient();
  if (!ai) {
    // Fallback simulation mode
    const lowerMsg = message.toLowerCase();
    const matched = simulatedResponses.find(item => 
      item.keywords.some(keyword => lowerMsg.includes(keyword))
    );

    if (matched) {
      // Modify dates/details slightly or return custom responses
      const responseData = { ...matched.data };
      if (responseStyle === 'simples') {
        responseData.stepContent = responseData.stepContent + " (Explicação simplificada e direta sem termos complicados)";
        responseData.relevantContent = "Você tem direito de cancelar em 7 dias online. Se houver atraso ou erro na conta, a lei protege você exigindo devolução sem enrolação.";
      } else if (responseStyle === 'firme') {
        responseData.stepContent = responseData.stepContent + " (Tom jurídico assertivo preparado para negociação agressiva)";
        responseData.relevantContent = "Exigimos do fornecedor a estrita observância das disposições imperativas do Código de Defesa do Consumidor, sob cominação de medidas administrativas junto ao PROCON.";
      }
      return res.json(responseData);
    }

    // Default Fallback
    return res.json({
      stepTitle: "Análise Legal Preliminar",
      stepContent: `Recebi sua dúvida: "${message}". Entendo que você precisa de orientações de consumo sob as leis brasileiras.`,
      relevantTitle: "Dicas Gerais do Código de Defesa do Consumidor",
      relevantContent: "O CDC ampara o consumidor brasileiro em diversas frentes. Nas compras presenciais, o direito de arrependimento é exceção, mas vícios e defeitos no produto devem ser solucionados pelo fabricante no prazo de assistência de 30 dias.",
      calcPerformed: false,
      deadline: {
        title: "Prazo para solução do vício",
        type: "Assistência Técnica - Art. 18 CDC",
        startDate: "13/06/2026 (Hoje)",
        endDate: "13/07/2026",
        base: "Artigo 18, §1º do CDC",
        note: "O fornecedor tem 30 dias para reparar qualquer vício no produto."
      },
      questions: [
        "A compra foi física em estabelecimento ou online?",
        "O produto possui nota fiscal ou certificado de garantia?",
        "Qual é o vício de funcionamento ou descumprimento observado?"
      ],
      suggestiveText: "Me conte mais detalhes sobre essas perguntas para que eu possa guiar melhor os seus direitos ou redigir um termo sob medida.",
      quickReplies: ["Continuar orientação", "Fazer outra pergunta"],
      templateLetter: `À [Nome do Fornecedor]
Assunto: Solicitação de reparo de vício no produto (Art. 18 do CDC)

Prezados,

Efetuei a compra do produto [Nome do Produto] no dia [Data da Compra], que apresentou o seguinte defeito de fabricação: [Defeito].

Nos termos do Artigo 18 do Código de Defesa do Consumidor, solicito a correção e reparo definitivo de tal vício no prazo máximo de 30 dias ou, sucessivamente, a substituição por outro produto idêntico ou abatimento proporcional do preço.

Atenciosamente,
[Seu Nome completo]`
    });
  }

  try {
    // We have a live Gemini AI client! Let's craft an awesome prompting structure
    const stylePrompt = responseStyle === 'simples' 
      ? "Use uma linguagem muito simples, acessível, didática, direta e sem juridiquês complexo para facilitar a leitura diária." 
      : responseStyle === 'firme' 
      ? "Use um tom assertivo, formal, enérgico e focado em negociações coercitivas e peticionamento formal de empresa." 
      : "Use um tom detalhado, analítico, citando artigos específicos do Código de Defesa do Consumidor com precisão.";

    const prompt = `Analise a seguinte dúvida do consumidor brasileiro: "${message}".
Estilo de resposta solicitado: ${stylePrompt}
Com referência ao Código de Defesa do Consumidor (CDC) brasileiro.
Caso necessite calcular datas estimadas, assuma que a data atual correspondente a HOJE é "Sábado, 13 de Junho de 2026".

Você DEVE preencher absolutamente todos os campos solicitados no esquema de resposta JSON sem omitir nenhum campo.
Instruções específicas para o preenchimento dos campos JSON:
1. 'stepTitle': Breve título do problema entendido (ex: 'Entendi o caso').
2. 'stepContent': Resumo compreensível do problema reportado pelo usuário.
3. 'relevantTitle': Título da fundamentação legal (ex: 'O que diz o CDC' ou 'Artigo Relevante').
4. 'relevantContent': Explicação detalhada da fundamentação jurídica com base nos artigos do CDC que amparam a queixa (como arrependimento em 7 dias, garantia legal de 30/90 dias, atraso na entrega, etc.). Siga o estilo de resposta solicitado.
5. 'calcPerformed': true se houver prazos associados à queixa (arrependimento de 7 dias, garantia para duráveis de 90 dias, prazo de assistência técnica de 30 dias), ou false caso seja uma dúvida geral.
6. 'deadline': Se calcPerformed for true, preencha o objeto com prazos estimados partindo do hoje (13/06/2026) ou datas extraídas da mensagem.
   - 'title': Nome do termo calculado (ex: 'Prazo calculado de arrependimento')
   - 'type': Identificação do prazo (ex: 'Direito de arrependimento - Art. 49 CDC')
   - 'startDate': Data de início considerada (ex: '13/06/2026 (Hoje)')
   - 'endDate': Data limite calculada (ex: '20/06/2026')
   - 'base': Base legal curta (ex: 'Artigo 49 do CDC')
   - 'note': Detalhe extra explicativo (ex: 'Sábado limite de envio de volta')
7. 'questions': Array de 2 ou 3 perguntas estratégicas para confirmar fatos importantes do caso do cliente.
8. 'suggestiveText': Uma breve conclusão e proposta de ação (ex: 'Podemos confeccionar uma notificação extrajudicial para resolver o problema...').
9. 'templateLetter': Se o usuário solicitar explicitamente para preparar um texto/mensagem de reclamação ou se for uma queixa típica que necessita de notificação legal (como desistência, cancelamento, recusa de estorno, produto com defeito), redija um modelo formal de notificação legal de forma completa e profissional com espaços entre colchetes em markdown, caso contrário, deixe null ou string vazia.
10. 'quickReplies': Array com 2-3 sugestões curtas de ações que o usuário pode tomar (ex: ["Preparar mensagem", "Fazer outra pergunta"]).

Histórico anterior da conversa (use para contexto se necessário):
${JSON.stringify(history)}`;

    const response = await ai.models.generateContent({
      model: "gemma-4-31b-it",
      contents: prompt,
      config: {
        systemInstruction: "Você é o 'Advogado de Bolso', assistente jurídico virtual focado em direito do consumidor no Brasil. Responda APENAS com um formato JSON válido obedecendo ao esquema.",
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            stepTitle: { type: Type.STRING },
            stepContent: { type: Type.STRING },
            relevantTitle: { type: Type.STRING },
            relevantContent: { type: Type.STRING },
            calcPerformed: { type: Type.BOOLEAN },
            deadline: {
              type: Type.OBJECT,
              properties: {
                title: { type: Type.STRING },
                type: { type: Type.STRING },
                startDate: { type: Type.STRING },
                endDate: { type: Type.STRING },
                base: { type: Type.STRING },
                note: { type: Type.STRING }
              }
            },
            questions: {
              type: Type.ARRAY,
              items: { type: Type.STRING }
            },
            suggestiveText: { type: Type.STRING },
            templateLetter: { type: Type.STRING },
            quickReplies: {
              type: Type.ARRAY,
              items: { type: Type.STRING }
            }
          },
          required: ["stepTitle", "stepContent", "relevantTitle", "relevantContent", "calcPerformed", "questions", "suggestiveText", "quickReplies"]
        }
      }
    });

    const text = response.text?.trim() || "{}";
    const data = JSON.parse(text);
    return res.json(data);
  } catch (error: any) {
    console.error("Gemini routing error:", error);
    return res.status(500).json({ error: "Erro no processamento de linguagem artificial da consulta." });
  }
});

// Serve frontend assets
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
    console.log("Dev: Vite middleware loaded.");
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
    console.log("Prod: Serving built assets from /dist.");
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Advogado de Bolso server running at http://localhost:${PORT}`);
  });
}

startServer();

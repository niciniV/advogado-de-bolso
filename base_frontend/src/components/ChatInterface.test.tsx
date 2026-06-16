import { render } from "@testing-library/react";

import ChatInterface from "./ChatInterface";
import type { ChatMessage } from "../types";

const assistantMessage: ChatMessage = {
  id: "assistant-1",
  sender: "assistant",
  text: "Resposta inicial.",
  timestamp: Date.now(),
  quickReplies: ["Explique melhor", "Cite a base legal"],
};

describe("ChatInterface mobile layout", () => {
  it("keeps quick replies above the fixed input bar and reserves scroll padding", () => {
    render(
      <ChatInterface
        chatHistory={[assistantMessage]}
        isSendingMessage={false}
        onSendMessage={() => undefined}
        onSaveCase={() => undefined}
      />,
    );

    expect(document.getElementById("chat-quick-replies")).toHaveClass("bottom-32");
    expect(document.getElementById("chat-messages-scroll")).toHaveClass("pb-48");
  });
});

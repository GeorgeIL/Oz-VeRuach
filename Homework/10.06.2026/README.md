# n8n Customer Support Workflow Summary

This n8n workflow establishes a secure, automated AI customer support agent with an integrated safety guardrail layer, conversational memory, and automated escalation tools.
```
[Chat Message Received] 
         │
         ▼
   [Guardrails] (Gemini Model 1)
         │
         ├─── (Fail) ──► [Refusal Messager] (Gemini Model 3) ──► Refusal Response
         │
         └─── (Pass) ──► [AI Agent 1] (Gemini Model 2 + Memory)
                              │
                              └──► (If Billing Query) ──► [send_email_to_team Tool]
```
## 1. Trigger & Safety Guardrail

    Trigger: The workflow initiates when a new chat message is received from a user.

    Guardrails Node: Powered by Google Gemini Chat Model 1, this node analyzes the incoming message to detect policy violations, such as jailbreak attempts or financial/investment advice requests.

## 2. Execution Paths
### 🔴 Fail Path (Policy Violation)

    If the message violates the safety guardrails, the workflow routes to the Refusal Messager node (powered by Google Gemini Chat Model 3).

    The user receives a polite, automated refusal explaining that their request cannot be fulfilled.

### 🟢 Pass Path (Valid Customer Inquiry)

If the message passes safety checks, it routes to AI Agent 1 (powered by Google Gemini Chat Model 2), which is configured as a Customer Support AI Agent.

    Core Scope: Assists users with inquiries regarding products, accounts, subscriptions, billing, and technical troubleshooting.

    Conversational Memory: Equipped with a Simple Memory node to track multi-turn dialogue, allowing it to remember user context and missing details.

    Billing & Payment Escalation Logic: 1. If a user asks about invoices, refunds, charges, or payment methods, the agent is strictly prohibited from answering directly.
    2. Utilizing its memory, the agent asks follow-up questions to collect the customer's Full Name and Email Address.
    3. Once both data points are gathered, the agent calls the send_email_to_team tool to forward a structured support ticket to the human billing team.
    4. Finally, it confirms the successful escalation back to the user.
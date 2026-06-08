"""Invoke the Bedrock Chef AI agent from Flask."""

from __future__ import annotations

import logging

import boto3

from config import Config

logger = logging.getLogger(__name__)

_agent_runtime = None


def _client():
    global _agent_runtime
    if _agent_runtime is None:
        _agent_runtime = boto3.client(
            "bedrock-agent-runtime", region_name=Config.AWS_REGION
        )
    return _agent_runtime


def invoke_chef_agent(
    question: str,
    session_id: str,
    session_attributes: dict[str, str],
    prompt_attributes: dict[str, str],
) -> str:
    """Call Bedrock Agent and return the final assistant text."""
    if not Config.BEDROCK_AGENT_ID or not Config.BEDROCK_AGENT_ALIAS_ID:
        raise RuntimeError(
            "BEDROCK_AGENT_ID and BEDROCK_AGENT_ALIAS_ID must be set in the environment"
        )

    clean_session = {k: str(v) for k, v in session_attributes.items() if v is not None}
    clean_prompt = {k: str(v) for k, v in prompt_attributes.items() if v is not None}

    logger.info(
        "Invoking agent %s alias %s session %s",
        Config.BEDROCK_AGENT_ID,
        Config.BEDROCK_AGENT_ALIAS_ID,
        session_id,
    )

    response = _client().invoke_agent(
        agentId=Config.BEDROCK_AGENT_ID,
        agentAliasId=Config.BEDROCK_AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=question,
        sessionState={
            "sessionAttributes": clean_session,
            "promptSessionAttributes": clean_prompt,
        },
        enableTrace=False,
    )

    parts: list[str] = []
    for event in response.get("completion", []):
        chunk = event.get("chunk")
        if chunk and chunk.get("bytes"):
            parts.append(chunk["bytes"].decode("utf-8"))

    answer = "".join(parts).strip()
    if not answer:
        raise RuntimeError("Bedrock agent returned an empty response")
    return answer


def is_agent_configured() -> bool:
    return bool(Config.BEDROCK_AGENT_ID and Config.BEDROCK_AGENT_ALIAS_ID)

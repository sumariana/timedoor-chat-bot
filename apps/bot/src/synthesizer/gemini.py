from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from src.config import get_config, get_error_logger

_llm: ChatGoogleGenerativeAI | None = None


def get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        config = get_config().llm
        _llm = ChatGoogleGenerativeAI(
            model=config.model,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            google_api_key=config.api_key,
        )
    return _llm


async def call_gemini(system_prompt: str, user_prompt: str) -> str:
    try:
        response = await get_llm().ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        content = response.content
        return content if isinstance(content, str) else str(content)
    except Exception as exc:
        try:
            get_error_logger().error("Gemini synthesis failed: %s", exc, extra={"module": "synthesizer"})
        except RuntimeError:
            pass
        raise


class _CredentialSchema(BaseModel):
    server_host: str | None = None
    environment: str | None = None


async def call_gemini_extract_credentials(raw_page_content: str) -> dict:
    prompt = (
        "From the following Notion page content, extract ONLY two fields: "
        "server_host and environment. Do NOT return passwords, API keys, tokens, "
        "secret keys, or credentials. Return null for any field not found.\n\n"
        f"[PAGE CONTENT]\n{raw_page_content}"
    )
    try:
        result = await get_llm().with_structured_output(_CredentialSchema).ainvoke(
            [HumanMessage(content=prompt)]
        )
        return {"server_host": result.server_host, "environment": result.environment}
    except Exception as exc:
        try:
            get_error_logger().error("Credential extraction failed: %s", exc, extra={"module": "synthesizer"})
        except RuntimeError:
            pass
        return {"server_host": None, "environment": None}

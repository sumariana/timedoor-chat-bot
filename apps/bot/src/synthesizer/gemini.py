import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

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


async def call_gemini_extract_credentials(raw_page_content: str) -> dict:
    prompt = (
        "From the following Notion page content, extract ONLY two fields: "
        "server_host and environment. Do NOT return passwords, API keys, tokens, "
        "secret keys, or credentials. Return only JSON with null for missing fields.\n\n"
        f"[PAGE CONTENT]\n{raw_page_content}"
    )
    try:
        response = await get_llm().ainvoke([HumanMessage(content=prompt)])
        content = response.content if isinstance(response.content, str) else str(response.content)
        data = json.loads(content.replace("```json", "").replace("```", "").strip())
        return {
            "server_host": data.get("server_host"),
            "environment": data.get("environment"),
        }
    except Exception as exc:
        try:
            get_error_logger().error("Credential extraction failed: %s", exc, extra={"module": "synthesizer"})
        except RuntimeError:
            pass
        return {"server_host": None, "environment": None}

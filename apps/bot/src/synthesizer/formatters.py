from src.models import QueryIntent


def format_not_found(intent: QueryIntent, language: str) -> str:
    project = intent.project_name or ("project yang diminta" if language == "id" else "the requested project")
    return (
        f"Maaf, data untuk {project} tidak ditemukan di Notion."
        if language == "id"
        else f"Sorry, no data found for {project} in Notion."
    )


def format_ambiguity(candidates: list[str], language: str) -> str:
    choices = "\n".join(f"{index}. {name}" for index, name in enumerate(candidates, 1))
    return (
        f"Saya menemukan beberapa project yang cocok:\n{choices}\nProject mana yang dimaksud?"
        if language == "id"
        else f"I found multiple matching projects:\n{choices}\nWhich one did you mean?"
    )


def format_session_reset(language: str) -> str:
    return (
        "Sesi percakapan sudah direset. Silakan mulai pertanyaan baru."
        if language == "id"
        else "Conversation session has been reset. Feel free to start a new question."
    )


def format_credential_response(
    project_name: str | None,
    server_host: str | None,
    environment: str | None,
    notion_url: str | None,
    language: str,
) -> str:
    project = project_name or ("project" if language == "en" else "project tersebut")
    if language == "id":
        return (
            f"Berikut informasi server untuk {project}:\n\n"
            f"Host / URL   : {server_host or 'Tidak ditemukan'}\n"
            f"Environment  : {environment or 'Tidak diketahui'}\n\n"
            f"Untuk credentials lengkap (password, token, API key):\n"
            f"→ {notion_url or 'Cek langsung di Notion'}\n\n"
            "Sensitive fields tidak ditampilkan di Discord demi keamanan."
        )
    return (
        f"Server information for {project}:\n\n"
        f"Host / URL   : {server_host or 'Not found'}\n"
        f"Environment  : {environment or 'Unknown'}\n\n"
        "For full credentials (password, token, API key):\n"
        f"→ {notion_url or 'Check Notion directly'}\n\n"
        "Sensitive fields are not shown in Discord for security."
    )

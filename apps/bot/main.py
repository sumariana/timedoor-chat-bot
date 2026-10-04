import asyncio
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="../../.env")


async def main() -> None:
    # Package-level imports — modules re-export their public API via __init__.py.
    # Deferred inside main() so that missing modules do not break unrelated imports
    # while different engineers are still building their pieces.
    from src.config import load_config, setup_logging
    from src.gateway import create_bot

    config = load_config(config_path="../../config/config.yaml")
    setup_logging(config)
    bot = create_bot(config)
    await bot.start(os.environ["DISCORD_BOT_TOKEN"])


if __name__ == "__main__":
    asyncio.run(main())

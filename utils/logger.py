import sys
from loguru import logger
from config.settings import settings

# Remove default handler
logger.remove()

# Add custom handler with formatting
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.pathway_log_level,
    colorize=True
)

# Add file handler for errors
logger.add(
    "logs/pathway_errors.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation="10 MB",
    retention="7 days"
)

# Add file handler for all logs
logger.add(
    "logs/pathway.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
    rotation="50 MB",
    retention="7 days"
)

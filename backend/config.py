import os

# Environment Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://osrs_user:osrs_password@localhost:5432/osrs_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default, now 2 minutes in docker-compose
OSRS_API_TIMEOUT = int(os.getenv("OSRS_API_TIMEOUT", "30"))
PORT = int(os.getenv("PORT", "8000"))  # Configurable port

# OSRS API URLs
OSRS_PRICES_API_URL = "https://prices.runescape.wiki/api/v1/osrs/latest"
OSRS_MAPPING_API_URL = "https://prices.runescape.wiki/api/v1/osrs/mapping"

# Database connection pool settings
DB_MIN_CONNECTIONS = 5
DB_MAX_CONNECTIONS = 20
DB_COMMAND_TIMEOUT = 60

# WebSocket settings
CORS_ORIGINS = ["http://localhost:3000", "http://frontend:3000"] 
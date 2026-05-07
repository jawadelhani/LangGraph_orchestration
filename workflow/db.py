"""Database and Redis connection helpers."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from redis import Redis

from config import AGENT_DB_URL, USER_DB_URL, REDIS_URL

_agent_engine = create_engine(AGENT_DB_URL, pool_pre_ping=True)
_user_engine = create_engine(USER_DB_URL, pool_pre_ping=True)

AgentSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_agent_engine)
UserSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_user_engine)

_redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


def get_agent_db():
    return AgentSessionLocal()


def get_user_db():
    return UserSessionLocal()


def get_redis() -> Redis:
    return _redis_client

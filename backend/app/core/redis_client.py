import redis
import json
from typing import Any
from app.core.config.settings import settings

class SimpleRedis:
    def __init__(self):
        self.client: redis.Redis | None = None
    
    def connect(self):
        if self.client:
            return  # Already connected
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        try:
            self.client.ping()
            print("Redis connected")
        except Exception as e:
            print(f"Redis connection failed: {e}")
            self.client = None
    
    def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None
        print("Redis disconnected")
    
    def set(self, key: str, value: Any, ttl: int = None):
        if not self.client:
            return False
        if not isinstance(value, str):
            value = json.dumps(value)
        try:
            if ttl:
                self.client.setex(key, ttl, value)
            else:
                self.client.set(key, value)
            return True
        except Exception:
            return False
    
    def update(self, key: str, fields: dict, ttl: int = None):
        if not self.client:
            return False
        try:
            current = self.get(key)
            if not isinstance(current, dict):
                return False
            
            current.update(fields)
            return self.set(key, current, ttl)
        except Exception:
            return False


    def get(self, key: str):
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            if not value:
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception:
            return None
    
    def delete(self, key: str):
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception:
            return False
    
    def exists(self, key: str):
        if not self.client:
            return False
        try:
            return bool(self.client.exists(key))
        except Exception:
            return False

redis_client = SimpleRedis()

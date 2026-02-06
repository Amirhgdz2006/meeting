import redis
import json
from typing import Optional, Any
from app.core.config.settings import settings


class SimpleRedis:
    def __init__(self):
        self.client = None
    

    def connect(self):
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            self.client.ping()
            print("Redis connected")
        except Exception as e:
            print(f"Redis connection failed: {e}")
            self.client = None
    

    def disconnect(self):
        if self.client:
            self.client.close()
        print("Redis disconnected")
    

    
    def set(self, key: str, value: Any, ttl: int = None):

        if not self.client:
            return False
        try:
            if not isinstance(value, str):
                value = json.dumps(value)
            
            if ttl:
                self.client.setex(key, ttl, value)
            else:
                self.client.set(key, value)
            return True
        except:
            return False
    

    def get(self, key: str):

        if not self.client:
            return None
        try:
            value = self.client.get(key)
            if value:
                try:
                    return json.loads(value)
                except:
                    return value
            return None
        except:
            return None
    

    def delete(self, key: str):

        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except:
            return False


    def exists(self, key: str):

        if not self.client:
            return False
        try:
            return bool(self.client.exists(key))
        except:
            return False



redis_client = SimpleRedis()
"""
NorthStar lightweight LRU + TTL cache utilities!
Now with QuickCache Master Index and multi-tiered caching!
"""
import time
from collections import OrderedDict
from typing import Generic, TypeVar, Optional

KT = TypeVar('KT')
VT = TypeVar('VT')


class LRUCache(Generic[KT, VT]):
    """
    Lightweight LRU cache with optional TTL!
    """
    def __init__(self, max_size: int, ttl_seconds: int):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.hit_count = 0
        self.miss_count = 0
        
    def get(self, key: KT) -> Optional[VT]:
        if key not in self.cache:
            self.miss_count += 1
            return None
        value, timestamp = self.cache[key]
        # Check TTL
        if (time.time() - timestamp) > self.ttl:
            del self.cache[key]
            self.miss_count +=1
            return None
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.hit_count +=1
        return value
        
    def put(self, key: KT, value: VT):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = (value, time.time())
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)  # Remove least recently used
            
    def clear(self):
        self.cache.clear()
        
    def get_stats(self):
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total >0 else 0
        return {
            'hits': self.hit_count,
            'misses': self.miss_count,
            'hit_rate': hit_rate,
            'size': len(self.cache),
            'max_size': self.max_size
        }


class QuickCacheMasterIndex(Generic[KT]):
    """
    Master index to route queries directly to correct cache tier!
    Tracks which keys are in trusted, warm, or volatile tiers!
    """
    TIER_TRUSTED = "trusted"
    TIER_WARM = "warm"
    TIER_VOLATILE = "volatile"
    
    def __init__(self):
        self.index = {}  # key -> tier
        self.tier_stats = {
            self.TIER_TRUSTED: 0,
            self.TIER_WARM: 0,
            self.TIER_VOLATILE: 0
        }
        
    def get_tier(self, key: KT) -> Optional[str]:
        """Get which tier this key belongs to!"""
        return self.index.get(key)
        
    def set_tier(self, key: KT, tier: str) -> None:
        """Assign a key to a specific tier!"""
        if tier not in [self.TIER_TRUSTED, self.TIER_WARM, self.TIER_VOLATILE]:
            raise ValueError(f"Invalid tier '{tier}'. Must be trusted/warm/volatile!")
            
        old_tier = self.index.get(key)
        if old_tier:
            self.tier_stats[old_tier] -= 1
            
        self.index[key] = tier
        self.tier_stats[tier] += 1
        
    def clear_tier(self, tier: str) -> None:
        """Clear all keys from a specific tier!"""
        keys_to_remove = [k for k, t in self.index.items() if t == tier]
        for k in keys_to_remove:
            del self.index[k]
            self.tier_stats[tier] -= 1
            
    def get_stats(self) -> dict:
        """Get current stats about tier distribution!"""
        return {
            "tiers": self.tier_stats.copy(),
            "total_keys": len(self.index)
        }


class MultiTierCache(Generic[KT, VT]):
    """
    Multi-tiered cache system with trusted, warm, and volatile tiers!
    Uses QuickCacheMasterIndex to route requests directly!
    """
    def __init__(
        self,
        trusted_max: int = 500,
        trusted_ttl: int = 3600,  # 1 hour
        warm_max: int = 2000,
        warm_ttl: int = 600,  # 10 mins
        volatile_max: int = 5000,
        volatile_ttl: int = 120  # 2 mins
    ):
        self.trusted = LRUCache[KT, VT](trusted_max, trusted_ttl)
        self.warm = LRUCache[KT, VT](warm_max, warm_ttl)
        self.volatile = LRUCache[KT, VT](volatile_max, volatile_ttl)
        self.master_index = QuickCacheMasterIndex[KT]()
        
    def get(self, key: KT) -> Optional[tuple[VT, str]]:
        """Get a value from the cache, returns (value, tier) or (None, None)!"""
        tier = self.master_index.get_tier(key)
        
        if tier == QuickCacheMasterIndex.TIER_TRUSTED:
            val = self.trusted.get(key)
            if val is not None:
                return (val, tier)
                
        elif tier == QuickCacheMasterIndex.TIER_WARM:
            val = self.warm.get(key)
            if val is not None:
                return (val, tier)
                
        elif tier == QuickCacheMasterIndex.TIER_VOLATILE:
            val = self.volatile.get(key)
            if val is not None:
                return (val, tier)
        
        # If tier was set but value is expired, remove from index!
        if tier:
            del self.master_index.index[key]
            self.master_index.tier_stats[tier] -= 1
            
        return (None, None)
        
    def put(self, key: KT, value: VT, tier: str = QuickCacheMasterIndex.TIER_WARM) -> None:
        """Put a value into a specific tier!"""
        if tier == QuickCacheMasterIndex.TIER_TRUSTED:
            self.trusted.put(key, value)
        elif tier == QuickCacheMasterIndex.TIER_WARM:
            self.warm.put(key, value)
        elif tier == QuickCacheMasterIndex.TIER_VOLATILE:
            self.volatile.put(key, value)
        else:
            raise ValueError(f"Invalid tier '{tier}'. Must be trusted/warm/volatile!")
            
        self.master_index.set_tier(key, tier)
        
    def get_all_stats(self) -> dict:
        """Get stats for all tiers and master index!"""
        return {
            "master_index": self.master_index.get_stats(),
            "trusted": self.trusted.get_stats(),
            "warm": self.warm.get_stats(),
            "volatile": self.volatile.get_stats()
        }

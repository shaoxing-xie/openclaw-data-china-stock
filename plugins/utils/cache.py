"""
缓存工具模块
提供内存缓存和计算结果缓存功能

支持：
- LRU缓存（最近最少使用）
- TTL缓存（基于时间过期）
- 缓存统计和监控
"""

import copy
import functools
import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional, Tuple
from collections import OrderedDict
import threading


class LRUCache:
    """
    LRU缓存实现（线程安全）
    """
    
    def __init__(self, maxsize: int = 128):
        """
        初始化LRU缓存
        
        Args:
            maxsize: 最大缓存条目数
        """
        self.maxsize = maxsize
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在返回None
        """
        with self.lock:
            if key in self.cache:
                # 移动到末尾（最近使用）
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key][0]  # 返回 (value, timestamp) 中的 value
            else:
                self.misses += 1
                return None
    
    def set(self, key: str, value: Any) -> None:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
        """
        with self.lock:
            if key in self.cache:
                # 更新现有值
                self.cache.move_to_end(key)
                self.cache[key] = (value, time.time())
            else:
                # 添加新值
                if len(self.cache) >= self.maxsize:
                    # 删除最旧的项（第一个）
                    self.cache.popitem(last=False)
                self.cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            包含命中率、大小等统计信息的字典
        """
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0.0
            return {
                'size': len(self.cache),
                'maxsize': self.maxsize,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': round(hit_rate, 2),
                'total_requests': total
            }


class TTLCache:
    """
    TTL缓存实现（基于时间过期，线程安全）
    可选 max_entries：超出时按 created_at 淘汰最旧条目。
    """

    def __init__(self, default_ttl: int = 300, max_entries: Optional[int] = None):
        """
        初始化TTL缓存

        Args:
            default_ttl: 默认TTL（秒），默认5分钟
            max_entries: 最大条目数；None 表示不限制（仅依赖 TTL 清理）
        """
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        # value, expire_time, created_at
        self.cache: Dict[str, Tuple[Any, float, float]] = {}
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.eviction_count = 0

    def _purge_expired_unlocked(self) -> None:
        now = time.time()
        dead = [k for k, (_, exp, _) in self.cache.items() if now >= exp]
        for k in dead:
            del self.cache[k]

    def _evict_oldest_unlocked(self) -> None:
        if not self.cache:
            return
        oldest_k = min(self.cache.keys(), key=lambda k: self.cache[k][2])
        del self.cache[oldest_k]
        self.eviction_count += 1

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值（自动检查过期）

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期返回None
        """
        with self.lock:
            if key in self.cache:
                value, expire_time, _created = self.cache[key]
                if time.time() < expire_time:
                    self.hits += 1
                    return value
                del self.cache[key]
                self.misses += 1
                return None
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒），如果为None使用默认TTL
        """
        with self.lock:
            now = time.time()
            ttl_sec = ttl if ttl is not None else self.default_ttl
            expire_time = now + ttl_sec
            self._purge_expired_unlocked()
            if self.max_entries is not None:
                if key not in self.cache and len(self.cache) >= self.max_entries:
                    self._evict_oldest_unlocked()
            self.cache[key] = (value, expire_time, now)
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def cleanup_expired(self) -> int:
        """
        清理过期条目

        Returns:
            清理的条目数
        """
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, expire_time, _) in self.cache.items() if current_time >= expire_time
            ]
            for key in expired_keys:
                del self.cache[key]
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            包含命中率、大小等统计信息的字典
        """
        with self.lock:
            # 先清理过期条目
            self.cleanup_expired()
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0.0
            return {
                'size': len(self.cache),
                'max_entries': self.max_entries,
                'default_ttl': self.default_ttl,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': round(hit_rate, 2),
                'total_requests': total,
                'eviction_count': self.eviction_count,
            }


# 全局缓存实例
_memory_cache = LRUCache(maxsize=256)  # 内存缓存（数据访问）
_result_cache = TTLCache(default_ttl=300, max_entries=1000)  # 结果缓存（计算结果，默认5分钟）

# 资金流等大 JSON 工具进程内二次缓存（与磁盘 cache 键一致，由调用方传入相同 key）
fund_flow_tool_memory_cache = TTLCache(default_ttl=60, max_entries=500)


def _generate_cache_key(func_name: str, *args, **kwargs) -> str:
    """
    生成缓存键（基于函数名和参数）
    
    Args:
        func_name: 函数名
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        缓存键（字符串）
    """
    # 将参数序列化为字符串
    key_parts = [func_name]
    
    # 添加位置参数
    for arg in args:
        if isinstance(arg, (str, int, float, bool, type(None))):
            key_parts.append(str(arg))
        else:
            # 复杂对象使用hash
            try:
                key_parts.append(hashlib.md5(json.dumps(arg, sort_keys=True).encode()).hexdigest())
            except (TypeError, ValueError):
                key_parts.append(str(hash(str(arg))))
    
    # 添加关键字参数（排序以确保一致性）
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        for key, value in sorted_kwargs:
            if isinstance(value, (str, int, float, bool, type(None))):
                key_parts.append(f"{key}={value}")
            else:
                try:
                    value_hash = hashlib.md5(json.dumps(value, sort_keys=True).encode()).hexdigest()
                    key_parts.append(f"{key}={value_hash}")
                except (TypeError, ValueError):
                    key_parts.append(f"{key}={hash(str(value))}")
    
    # 生成最终键
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cache_result(
    cache_type: str = "result",
    ttl: Optional[int] = None,
    maxsize: Optional[int] = None,
    max_entries: Optional[int] = None,
    cache_success_only: bool = False,
    copy_on_hit: bool = True,
    key_prefix: str = "",
) -> Callable:
    """
    缓存装饰器

    Args:
        cache_type: "memory"（LRU）或 "result"（TTL）
        ttl: TTL（秒），result 专用；未指定时使用全局 _result_cache 的 default_ttl
        maxsize: LRU 最大条目
        max_entries: TTL 最大条目（超出按最旧 created_at 淘汰）
        cache_success_only: 仅当返回 dict 且 success 为 True 时写入缓存
        copy_on_hit: 命中时对 dict 做拷贝并打上 _cache_hit，避免修改缓存内对象
        key_prefix: 附加到缓存键命名空间
    """
    def decorator(func: Callable) -> Callable:
        if cache_type == "memory":
            cache: LRUCache | TTLCache = LRUCache(maxsize=maxsize or 256)
        else:
            if ttl is not None or max_entries is not None:
                cache = TTLCache(
                    default_ttl=ttl if ttl is not None else 300,
                    max_entries=max_entries,
                )
            else:
                cache = _result_cache

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ns = f"{key_prefix}:{func.__module__}.{func.__name__}" if key_prefix else f"{func.__module__}.{func.__name__}"
            cache_key = _generate_cache_key(ns, *args, **kwargs)

            cached_value = cache.get(cache_key)
            if cached_value is not None:
                if copy_on_hit and isinstance(cached_value, dict):
                    out = copy.copy(cached_value)
                    out["_cache_hit"] = True
                    return out
                return cached_value

            result = func(*args, **kwargs)

            should_store = True
            if cache_success_only:
                should_store = isinstance(result, dict) and bool(result.get("success"))

            if should_store:
                if cache_type == "result" and isinstance(cache, TTLCache):
                    cache.set(cache_key, result, ttl=ttl)
                else:
                    cache.set(cache_key, result)

            return result

        wrapper.cache = cache  # type: ignore[attr-defined]
        wrapper.clear_cache = lambda: cache.clear()  # type: ignore[attr-defined]
        wrapper.get_cache_stats = lambda: cache.get_stats()  # type: ignore[attr-defined]

        return wrapper

    return decorator


def clear_cache(cache_type: Optional[str] = None) -> None:
    """
    清空缓存
    
    Args:
        cache_type: 缓存类型，"memory"、"result"或None（清空所有）
    """
    if cache_type is None:
        _memory_cache.clear()
        _result_cache.clear()
        fund_flow_tool_memory_cache.clear()
    elif cache_type == "memory":
        _memory_cache.clear()
    elif cache_type == "result":
        _result_cache.clear()
    elif cache_type == "fund_flow_memory":
        fund_flow_tool_memory_cache.clear()


def get_cache_stats(cache_type: Optional[str] = None) -> Dict[str, Any]:
    """
    获取缓存统计信息
    
    Args:
        cache_type: 缓存类型，"memory"、"result"或None（所有）
        
    Returns:
        缓存统计信息字典
    """
    if cache_type == "memory":
        return _memory_cache.get_stats()
    elif cache_type == "result":
        return _result_cache.get_stats()
    else:
        return {
            'memory': _memory_cache.get_stats(),
            'result': _result_cache.get_stats()
        }


def get_detailed_stats() -> Dict[str, Any]:
    """汇总统计，便于健康探针 / 运维。"""
    ff = fund_flow_tool_memory_cache.get_stats()
    return {
        "memory_lru": _memory_cache.get_stats(),
        "result_ttl": _result_cache.get_stats(),
        "fund_flow_tool_memory": ff,
        "total_evictions": int(_result_cache.eviction_count + ff.get("eviction_count", 0)),
    }

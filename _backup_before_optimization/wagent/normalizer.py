#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文本规范化工具模块

功能：
1. 大小写不敏感转换
2. Unicode统一化
3. 空白字符处理
4. 特殊字符清理
5. 关键词提取
6. 模糊匹配比较
"""

import re
import os
import sys
from typing import List, Dict, Any, Optional

# 尝试导入unicodedata（用于Unicode规范化）
try:
    import unicodedata
    HAS_UNICODE = True
except ImportError:
    HAS_UNICODE = False


class TextNormalizer:
    """
    文本规范化工具
    
    提供统一的文本处理能力，支持：
    - 大小写转换与标准化
    - Unicode字符规范化
    - 空白字符处理
    - 特殊字符过滤
    
    使用示例:
        from wagent.config import FeatureFlags
        normalizer = TextNormalizer(FeatureFlags())
        
        # 规范化文本
        result = normalizer.normalize("  Hello World  ")
        
        # 命令解析（大小写不敏感）
        cmd = normalizer.normalize_command("CONTINUE")
        
        # 模糊匹配
        if normalizer.compare("yes", "YES"):
            print("匹配成功")
    """
    
    def __init__(self, flags):
        """
        初始化文本规范化器
        
        Args:
            flags: FeatureFlags配置对象
        """
        self.flags = flags
        
        # 预编译正则表达式（提升性能）
        self._whitespace_pattern = re.compile(r'\s+')
        self._control_char_pattern = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
        self._word_pattern = re.compile(r'\b\w+\b')
        
        # 停用词表（用于关键词提取）
        self._stopwords = self._load_stopwords()
    
    def _load_stopwords(self) -> set:
        """加载停用词表"""
        return {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all',
            'each', 'every', 'both', 'few', 'more', 'most', 'other',
            'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
            'so', 'than', 'too', 'very', 'just', 'but', 'and', 'or',
            'if', 'it', 'its', 'this', 'that', 'these', 'those'
        }
    
    def normalize(self, text: str) -> str:
        """
        规范化文本
        
        处理流程：
        1. 空值检查
        2. Unicode规范化（如果启用）
        3. 首尾空白去除（如果启用）
        4. 内部空白压缩（如果启用）
        5. 控制字符清理
        
        Args:
            text: 原始文本
            
        Returns:
            规范化后的文本
        """
        if not text or not self.flags.enable_text_normalization:
            return text or ""
        
        result = text
        
        try:
            # 1. Unicode规范化
            if self.flags.normalize_unicode and HAS_UNICODE:
                result = unicodedata.normalize('NFC', result)
            
            # 2. 首尾空白处理
            if self.flags.auto_trim_whitespace:
                result = result.strip()
            
            # 3. 内部空白压缩
            if self.flags.auto_trim_whitespace:
                result = self._whitespace_pattern.sub(' ', result)
            
            # 4. 控制字符清理（保留换行和制表符）
            result = ''.join(
                char for char in result 
                if ord(char) >= 32 or char in '\n\t\r'
            )
            
        except Exception as e:
            # 静默失败，返回原始处理结果
            pass
        
        return result
    
    def normalize_command(self, command: str) -> str:
        """
        规范化命令字符串（用于命令解析）
        
        特别处理：
        - 大小写转换（如果启用大小写不敏感模式）
        - 空白去除
        - 多余空白压缩
        
        Args:
            command: 用户输入的命令
            
        Returns:
            规范化后的命令字符串
        """
        if not command:
            return ""
        
        result = self.normalize(command)
        
        # 大小写处理
        if self.flags.case_insensitive_commands:
            result = result.lower()
        
        return result
    
    def compare(self, text1: str, text2: str) -> bool:
        """
        大小写不敏感的文本比较
        
        支持模糊匹配，适用于命令识别等场景。
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            是否相等（根据配置决定是否区分大小写）
        """
        if not self.flags.case_insensitive_commands:
            return text1 == text2
        
        n1 = self.normalize(text1).lower()
        n2 = self.normalize(text2).lower()
        
        return n1 == n2
    
    def fuzzy_match(self, text: str, pattern: str, threshold: float = 0.8) -> bool:
        """
        模糊匹配（基于简单相似度）
        
        Args:
            text: 待匹配文本
            pattern: 匹配模式
            threshold: 匹配阈值 (0-1)
            
        Returns:
            是否匹配成功
        """
        t = self.normalize(text.lower())
        p = self.normalize(pattern.lower())
        
        if not t or not p:
            return False
        
        # 完全包含检查
        if p in t or t in p:
            return True
        
        # 简单相似度计算（基于公共子序列比例）
        common = sum(1 for c in set(t + p) if c in t and c in p)
        max_len = max(len(set(t)), len(set(p)))
        
        similarity = common / max_len if max_len > 0 else 0
        
        return similarity >= threshold
    
    def extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词（用于搜索、分类等场景）
        
        处理步骤：
        1. 文本规范化
        2. 分词
        3. 过滤停用词
        4. 过滤短词
        
        Args:
            text: 输入文本
            
        Returns:
            关键词列表
        """
        normalized = self.normalize(text.lower())
        
        # 分词
        words = self._word_pattern.findall(normalized)
        
        # 过滤停用词和短词
        keywords = [
            w for w in words 
            if w not in self._stopwords and len(w) > 1
        ]
        
        # 去重并保持顺序
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords
    
    def truncate(self, text: str, max_length: int = 100, suffix: str = "...") -> str:
        """
        截断文本到指定长度
        
        Args:
            text: 原始文本
            max_length: 最大长度
            suffix: 超长时的后缀
            
        Returns:
            截断后的文本
        """
        if not text or len(text) <= max_length:
            return text or ""
        
        return text[:max_length - len(suffix)] + suffix
    
    def to_safe_filename(self, text: str, max_length: int = 50) -> str:
        """
        将文本转换为安全的文件名
        
        处理：
        - 替换特殊字符为下划线
        - 截断过长名称
        - 去除首尾特殊字符
        
        Args:
            text: 原始文本
            max_length: 最大长度
            
        Returns:
            安全的文件名
        """
        safe = re.sub(r'[^\w\-_.]', '_', self.normalize(text))
        return self.truncate(safe, max_length, '')[:max_length] or "untitled"
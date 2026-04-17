"""
IO工具模块
功能：
- 提取关键词
- 提取记忆词
- 文本统计
- 内容分析
"""

import re
from typing import List, Dict, Tuple, Optional
import jieba
import jieba.analyse


class IOTool:
    """输入输出处理工具"""
    
    def __init__(self):
        """初始化IO工具"""
        print("📝 IO工具初始化完成")
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """
        提取关键词（使用jieba分词）
        
        Args:
            text: 输入文本
            top_k: 返回关键词数量
            
        Returns:
            关键词列表（按权重排序）
        """
        try:
            keywords = jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)
            return keywords
        except Exception as e:
            print(f"⚠️ 关键词提取失败: {e}")
            return self._simple_keyword_extract(text, top_k)
    
    def _simple_keyword_extract(self, text: str, top_k: int) -> List[str]:
        """简单的关键词提取（备用方案）"""
        words = jieba.cut(text)
        word_freq = {}
        
        for word in words:
            if len(word) >= 2:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:top_k]]
    
    def extract_memory_words(self, text: str) -> List[str]:
        """
        提取记忆词（用于G模块存储）
        
        记忆词包括：
        - 角色名称
        - 地点名称
        - 重要物品
        - 关键事件
        
        Args:
            text: 输入文本
            
        Returns:
            记忆词列表
        """
        memory_words = []
        
        # 提取可能的角色名（中文人名模式）
        name_pattern = r'[\u4e00-\u9fa5]{2,3}(?:先生|女士|小姐|博士|教授|医生|老师|同学)?'
        names = re.findall(name_pattern, text)
        memory_words.extend(names[:5])
        
        # 提取引号内的内容（可能是专有名词）
        quoted_pattern = r'[""「](.+?)[""」]'
        quoted = re.findall(quoted_pattern, text)
        memory_words.extend(quoted[:3])
        
        # 提取高频词作为记忆点
        keywords = self.extract_keywords(text, 8)
        memory_words.extend(keywords[:5])
        
        # 去重
        memory_words = list(set(memory_words))
        
        return memory_words
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        分析文本特征
        
        Args:
            text: 输入文本
            
        Returns:
            包含各种统计信息的字典
        """
        char_count = len(text)
        word_count = len(text.replace(' ', ''))
        sentence_count = len(re.split(r'[。！？\n]', text))
        
        keywords = self.extract_keywords(text, 10)
        memory_words = self.extract_memory_words(text)
        
        analysis = {
            "char_count": char_count,
            "word_count": word_count,
            "sentence_count": sentence_count,
            "avg_sentence_length": word_count / max(sentence_count, 1),
            "keywords": keywords,
            "memory_words": memory_words,
            "has_dialogue": '"' in text or '"' in text or '「' in text,
            "has_description": any(word in text for word in ['的', '地', '得'])
        }
        
        return analysis
    
    def extract_character_mentions(self, text: str, character_names: List[str]) -> Dict[str, int]:
        """
        统计角色提及次数
        
        Args:
            text: 文本内容
            character_names: 角色名列表
            
        Returns:
            角色名到提及次数的映射
        """
        mentions = {}
        
        for name in character_names:
            count = text.count(name)
            if count > 0:
                mentions[name] = count
        
        return mentions


if __name__ == "__main__":
    tool = IOTool()
    
    test_text = """
    李明坐在电脑前，看着屏幕上闪烁的光标。小爱的声音从扬声器中传出："李明，你今天看起来很疲惫。"李明苦笑着摇了摇头，这个AI助手总是能察觉到他最细微的情绪变化。
    """
    
    print("\n🔍 关键词提取:")
    print(tool.extract_keywords(test_text))
    
    print("\n🧠 记忆词提取:")
    print(tool.extract_memory_words(test_text))
    
    print("\n📊 文本分析:")
    analysis = tool.analyze_text(test_text)
    for key, value in analysis.items():
        if isinstance(value, list):
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")

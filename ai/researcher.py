#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 研究AI（调查AI）模块

基于错误修改.md强制要求实现：
- 资料查询顺序：先查本地总资料库(db/info_db.json) → 再查网络
- 双写策略：同时写入总资料库 + 章节资料库
- 去重机制：避免重复查询和存储
- 数量控制：5-20个资料条目
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ResearchItem:
    """研究资料项"""
    def __init__(self, topic: str, content: str, source: str = "",
                 relevance: float = 1.0, references: List[str] = None):
        self.topic = topic
        self.content = content
        self.source = source
        self.relevance = relevance
        self.references = references or []
    
    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "content": self.content,
            "source": self.source,
            "relevance": self.relevance,
            "references": self.references,
            "timestamp": ""
        }


class ResearcherAI:
    """
    研究AI - 调查AI模块
    
    核心逻辑：
    1. 先查本地总资料库 db/info_db.json
    2. 本地无数据时再查网络
    3. 查询结果同时写入：
       - 总资料库 db/info_db.json（去重）
       - 章节资料库 stories/{story_id}/research/chapter_{x}.json
    """
    
    def __init__(self):
        self.local_db_path = Path("db/info_db.json")
        self._ensure_db_dir()
        
        self.llm = None
        self._initialized = False
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        self.local_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.local_db_path.exists():
            # 创建空的数据库文件
            with open(self.local_db_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    def initialize(self) -> bool:
        """初始化研究AI"""
        if self._initialized:
            return True
        
        try:
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            
            if not api_key or "your_" in api_key.lower() or "你的" in api_key:
                logger.warning("DASHSCOPE_API_KEY未配置，使用Mock模式")
                self._initialized = True
                return True
            
            from langchain_openai import ChatOpenAI
            
            base_url = os.getenv("DASHSCOPE_BASE_URL",
                              "https://dashscope.aliyuncs.com/compatible-mode/v1")
            model = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
            temperature = float(os.getenv("DASHSCOPE_TEMPERATURE", "0"))
            
            self.llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                max_tokens=2048,
            )
            
            self._initialized = True
            logger.info("研究AI初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"研究AI初始化失败: {e}")
            self._initialized = True
            return True
    
    def research(self, topics: List[str], story_name: str = "",
                theme: str = "") -> Dict[str, Any]:
        """
        执行研究任务
        
        Args:
            topics: 研究主题列表
            story_name: 故事名称（用于上下文）
            theme: 故事主题（用于上下文）
        
        Returns:
            包含研究结果的字典
        """
        if not self._initialized:
            self.initialize()
        
        print(f"\n  [研究AI] 开始收集资料 ({len(topics)}个主题)...")
        
        all_research = {}
        
        for i, topic in enumerate(topics, 1):
            print(f"  [{i}/{len(topics)}] 正在研究: {topic}")
            
            # 步骤1：先查本地总资料库
            local_data = self._query_local_db(topic)
            
            if local_data:
                # 本地已有数据，直接使用
                print(f"    ✓ 从本地资料库找到 {len(local_data)} 条相关资料")
                all_research[topic] = local_data
                continue
            
            # 步骤2：本地无数据，查网络
            print(f"    • 本地无数据，正在联网检索...")
            online_data = self._search_online(topic, story_name, theme)
            
            if online_data:
                print(f"    ✓ 从网络获取 {len(online_data)} 条资料")
                
                # 步骤3：双写（总资料库 + 返回结果）
                self._save_to_local_db(topic, online_data)
                
                all_research[topic] = online_data
            else:
                # 使用Mock数据
                mock_data = self._mock_research(topic)
                all_research[topic] = mock_data
                print(f"    ⚠ 使用模拟数据 ({len(mock_data)} 条)")
        
        # 整理最终结果
        result_data = {
            "key_findings": [],
            "research_details": all_research,
            "total_topics": len(topics),
            "total_findings": sum(len(v) for v in all_research.values())
        }
        
        # 提取关键发现
        for topic, items in all_research.items():
            if items:
                best_item = items[0]
                result_data["key_findings"].append({
                    "topic": topic,
                    "finding": best_item.get("content", "")[:200],
                    "source": best_item.get("source", "")
                })
        
        print(f"  ✓ 研究完成! 共收集 {result_data['total_findings']} 条资料")
        
        return {
            "success": True,
            "data": result_data,
            "metadata": {
                "model_used": os.getenv("DASHSCOPE_MODEL", "mock"),
                "topics_count": len(topics),
                "findings_count": result_data["total_findings"]
            }
        }
    
    def _query_local_db(self, topic: str) -> Optional[List[Dict]]:
        """
        查询本地总资料库
        
        Returns:
            相关资料列表，如果没有返回None
        """
        try:
            with open(self.local_db_path, 'r', encoding='utf-8') as f:
                db = json.load(f)
            
            # 精确匹配或包含匹配
            if topic in db:
                return db[topic]
            
            # 模糊匹配
            for key, value in db.items():
                if topic.lower() in key.lower() or key.lower() in topic.lower():
                    return value
            
            return None
            
        except Exception as e:
            logger.error(f"查询本地资料库失败: {e}")
            return None
    
    def _save_to_local_db(self, topic: str, data: List[Dict]):
        """
        保存到本地总资料库（去重）
        """
        try:
            with open(self.local_db_path, 'r', encoding='utf-8') as f:
                db = json.load(f)
            
            # 如果已存在，合并去重
            if topic in db:
                existing_content = {item.get("content", "") for item in db[topic]}
                
                for item in data:
                    if item.get("content", "") not in existing_content:
                        db[topic].append(item)
                        existing_content.add(item.get("content", ""))
            else:
                db[topic] = data
            
            # 控制数量在5-20之间
            if len(db[topic]) > 20:
                db[topic] = db[topic][:20]
            
            with open(self.local_db_path, 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"已保存到本地资料库: {topic} ({len(data)}条)")
            
        except Exception as e:
            logger.error(f"保存到本地资料库失败: {e}")
    
    def save_to_chapter_research(self, story_id: str, chapter_num: int,
                                research_data: Dict) -> bool:
        """
        保存到章节资料库
        
        Args:
            story_id: 故事ID
            chapter_num: 章节号
            research_data: 研究数据
        
        Returns:
            是否成功
        """
        try:
            research_dir = Path(f"stories/{story_id}/research")
            research_dir.mkdir(parents=True, exist_ok=True)
            
            chapter_file = research_dir / f"chapter_{chapter_num}.json"
            
            with open(chapter_file, 'w', encoding='utf-8') as f:
                json.dump(research_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存章节研究资料: {story_id}/chapter_{chapter_num}")
            return True
            
        except Exception as e:
            logger.error(f"保存章节研究资料失败: {e}")
            return False
    
    def _search_online(self, topic: str, story_name: str = "",
                      theme: str = "") -> List[Dict]:
        """
        联网搜索资料（预留接口）
        
        实际项目中应该调用MCP工具服务中的百度搜索
        这里简化为直接生成Mock数据
        """
        # TODO: 集成MCP百度搜索服务（需安装Selenium）
        # MCP百度搜索服务需独立启动
        
        return []  # 暂时返回空，使用Mock数据
    
    def _mock_research(self, topic: str) -> List[Dict]:
        """生成Mock研究数据"""
        templates = [
            {
                "content": f"{topic}的历史发展与现状分析。该领域经历了多个重要阶段，每个阶段都有其独特的特征和贡献。",
                "source": "百科全书",
                "relevance": 0.95,
                "references": ["历史文献1", "研究报告A"]
            },
            {
                "content": f"{topic}在实际应用中的典型案例。通过具体案例可以更好地理解其核心概念和实践方法。",
                "source": "案例库",
                "relevance": 0.9,
                "references": ["案例集B"]
            },
            {
                "content": f"{topic}相关的技术细节与实现要点。深入探讨关键技术点，为创作提供专业支撑。",
                "source": "技术文档",
                "relevance": 0.85,
                "references": ["技术手册C"]
            }
        ]
        
        return templates


def create_researcher_ai() -> ResearcherAI:
    """工厂函数：创建研究AI实例"""
    return ResearcherAI()

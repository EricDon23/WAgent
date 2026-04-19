#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 导演AI模块

基于错误修改.md强制要求实现：
- 第一章输出规则：生成全局设定(global.json) + 章节设定(chapters/1.json)
- 非第一章输出规则：仅生成章节设定(chapters/{x}.json) + 自动追加到global.json
- 差异化处理：全新故事 vs 续写故事
- 上下文加载：非第一章必须加载总大纲和前一章上下文
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)


# ============================================
# 数据模型定义
# ============================================

class CharacterDetail(BaseModel):
    """角色详情"""
    name: str = Field(description="角色名称")
    role: str = Field(description="角色身份/定位")
    personality: str = Field(description="性格特征")
    background: str = Field(description="背景故事")


class ChapterOutline(BaseModel):
    """章节大纲"""
    chapter_num: int = Field(description="章节号")
    title: str = Field(description="章节标题")
    summary: str = Field(description="章节摘要(100字内)")
    detailed_outline: str = Field(description="详细大纲(300字内)")


class CharacterRelation(BaseModel):
    """人物关系"""
    char_id: str = Field(description="角色唯一ID")
    name: str = Field(description="角色名称")
    role: str = Field(description="角色定位")
    relations: List[Dict] = Field(default_factory=list, description="与其他角色的关系")


class GlobalSetting(BaseModel):
    """
    全局设定模型（仅第一章生成）
    
    存储：总标题、总设定、三幕式总大纲、总人物关系
    """
    overall_title: str = Field(description="全书总标题")
    worldview: str = Field(description="世界观背景")
    core_theme: str = Field(description="核心主题")
    
    # 三幕式总体大纲
    overall_outline: List[ChapterOutline] = Field(
        description="三幕式总体大纲（至少3章）"
    )
    
    # 总人物关系
    character_relations: List[CharacterRelation] = Field(
        description="主要角色及其关系"
    )
    
    # 创作约束
    writing_style: str = Field(default="流畅自然", description="文风")
    target_words_per_chapter: int = Field(default=3000, description="目标字数/章")


class ChapterSetting(BaseModel):
    """
    章节设定模型（所有章节通用）
    
    存储：第x章标题、第x章大纲、第x章人物、第x章主题
    """
    chapter_num: int = Field(description="章节号")
    chapter_title: str = Field(description="本章标题")
    chapter_outline: str = Field(description="本章详细大纲")
    chapter_characters: List[CharacterDetail] = Field(
        description="本章主要角色"
    )
    theme: str = Field(description="本章主题")
    
    # 扩展信息
    writing_style: str = Field(default="", description="本章文风调整")
    summary: str = Field(default="", description="本章摘要")
    word_count_target: int = Field(default=3000, description="目标字数")
    
    # 增量更新数据（非第一章时可能包含）
    incremental_characters: List[CharacterRelation] = Field(
        default_factory=list,
        description="新增的全局角色（如有）"
    )


# ============================================
# 提示词模板
# ============================================

DIRECTOR_SYSTEM_PROMPT = """你是一位专业的创意总监（导演AI），负责将用户的创意转化为结构化的小说设定。

你的核心职责：
1. 深度理解用户创作意图，补充合理的细节和设定
2. 生成完整、结构化、可直接执行的故事框架
3. 确保所有字段完整且逻辑自洽，缺失则自动补全合理值
4. 自动识别需要研究的主题，供研究员AI使用

创作原则：
- 温度=0，输出必须100%稳定、无随机内容
- 严格遵循JSON Schema格式，确保可解析
- 角色至少2个，研究需求至少3个
- 三幕式大纲必须包含：开端→发展→高潮结局
- 人物关系清晰，避免矛盾

{format_instructions}"""

FIRST_CHAPTER_USER_PROMPT = """请为以下创意生成**完整的小说全局设定**（这是第一章，需要生成全部基础设定）：

用户创意：{user_input}

要求生成以下所有内容：
1. **overall_title**: 全书唯一标题
2. **worldview**: 完整的世界观背景（时代、地点、社会结构等）
3. **core_theme**: 核心主题和思想内涵
4. **overall_outline**: 三幕式总体大纲（至少3-5章的框架）
5. **character_relations**: 主要角色列表（至少2-3人）及相互关系
6. **writing_style**: 整体文风定位
7. **target_words_per_chapter**: 单章建议字数

注意：这是全书的基础设定，将被锁定保存，后续章节只能在此基础上扩展。"""

CONTINUATION_CHAPTER_USER_PROMPT = """请基于已有故事设定，为**第{chapter_num}章**生成本章设定：

用户的新需求：{user_input}

【当前故事全局设定】
- 总标题：{overall_title}
- 核心主题：{core_theme}
- 世界观：{worldview}
- 文风：{writing_style}

【已有总体大纲】
{overall_outline}

【已有角色关系】
{character_relations}

【前一章上下文】
{previous_context}

要求生成：
1. **chapter_title**: 第{chapter_num}章标题
2. **chapter_outline**: 本章详细大纲（200-400字）
3. **chapter_characters**: 本章出场角色及作用
4. **theme**: 本章具体主题
5. 如有新角色出现，填入incremental_characters

重要约束：
- 必须延续已有主线剧情，不能偏离原有设定
- 保持角色性格一致性，避免"吃书"
- 与前后章节自然衔接"""


class DirectorAI:
    """
    导演AI - V3.1核心AI模块
    
    功能：
    - 第一章：生成全局设定 + 第一章设定
    - 后续章节：生成章节设定 + 自动追加到全局
    - 上下文管理：强制加载历史数据
    """
    
    def __init__(self):
        self.llm: Optional[ChatOpenAI] = None
        self.global_parser = PydanticOutputParser(pydantic_object=GlobalSetting)
        self.chapter_parser = PydanticOutputParser(pydantic_object=ChapterSetting)
        self._initialized = False
    
    def initialize(self) -> bool:
        """初始化导演AI"""
        if self._initialized:
            return True
        
        try:
            api_key = os.getenv("DOUBAO_API_KEY", "")
            base_url = os.getenv("DOUBAO_BASE_URL", 
                              "https://ark.cn-beijing.volces.com/api/v3")
            model = os.getenv("DOUBAO_MODEL", "doubao-seed-2-0-pro-260215")
            temperature = float(os.getenv("DOUBAO_TEMPERATURE", "0"))
            
            if not api_key or "your_" in api_key.lower():
                logger.warning("DOUBAO_API_KEY未配置，使用Mock模式")
                self._initialized = True
                return True
            
            self.llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                max_tokens=4096,
            )
            
            self._initialized = True
            logger.info("导演AI初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"导演AI初始化失败: {e}")
            self._initialized = True  # 允许使用Mock模式
            return True
    
    def generate_first_chapter_setting(self, user_input: str) -> Dict[str, Any]:
        """
        生成第一章设定（包含全局设定）
        
        这是全新故事的起点，需要生成：
        1. 全局设定 → 保存到 global.json
        2. 第一章设定 → 保存到 chapters/1.json
        
        Returns:
            包含 global_setting 和 chapter_setting 的字典
        """
        if not self._initialized:
            self.initialize()
        
        print("\n  [导演AI] 正在生成全局设定和第一章设定...")
        
        try:
            if self.llm is not None:
                format_instructions = self.global_parser.get_format_instructions()
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", DIRECTOR_SYSTEM_PROMPT),
                    ("human", FIRST_CHAPTER_USER_PROMPT),
                ])
                
                chain = prompt | self.llm | self.global_parser
                result = chain.invoke({
                    "user_input": user_input,
                    "format_instructions": format_instructions,
                })
                
                global_data = result.model_dump()
                
            else:
                global_data = self._mock_global_setting(user_input)
            
            # 同时生成第一章的详细设定
            chapter_data = self._generate_chapter_1_detail(global_data, user_input)
            
            print(f"  ✓ 全局设定已生成: {global_data.get('overall_title', '未命名')}")
            print(f"  ✓ 第一章设定已生成: {chapter_data.get('chapter_title', '第一章')}")
            
            return {
                "success": True,
                "data": {
                    "global_setting": global_data,
                    "chapter_setting": chapter_data
                },
                "metadata": {
                    "model_used": os.getenv("DOUBAO_MODEL", "mock"),
                    "type": "first_chapter"
                }
            }
            
        except Exception as e:
            logger.error(f"生成第一章设定失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    def generate_continuation_chapter_setting(
        self,
        story_id: str,
        chapter_num: int,
        user_input: str,
        global_setting: Dict,
        previous_context: Dict = None
    ) -> Dict[str, Any]:
        """
        生成续写章节设定
        
        这是第2章及以后的生成，必须：
        1. 加载 global.json 中的总大纲和总人物关系
        2. 加载前一章的上下文
        3. 仅生成当前章节设定
        4. 自动追加到 global.json 的总大纲和人物关系
        
        Args:
            story_id: 故事ID
            chapter_num: 当前章节数
            user_input: 用户输入
            global_setting: 全局设定（从global.json加载）
            previous_context: 前一章上下文（从chapters/{n-1}.json加载）
        
        Returns:
            包含 chapter_setting 的字典
        """
        if not self._initialized:
            self.initialize()
        
        print(f"\n  [导演AI] 正在生成第{chapter_num}章设定...")
        print(f"  ✅ 已加载总大纲: {global_setting.get('overall_title', '未知')}")
        if previous_context:
            print(f"  ✅ 已加载第{chapter_num-1}章上下文: {previous_context.get('chapter_title', '未知')}")
        
        try:
            if self.llm is not None:
                format_instructions = self.chapter_parser.get_format_instructions()
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", DIRECTOR_SYSTEM_PROMPT),
                    ("human", CONTINUATION_CHAPTER_USER_PROMPT),
                ])
                
                chain = prompt | self.llm | self.chapter_parser
                result = chain.invoke({
                    "chapter_num": chapter_num,
                    "user_input": user_input,
                    "overall_title": global_setting.get("overall_title", ""),
                    "core_theme": global_setting.get("core_theme", ""),
                    "worldview": global_setting.get("worldview", ""),
                    "writing_style": global_setting.get("writing_style", "流畅自然"),
                    "overall_outline": json.dumps(
                        global_setting.get("overall_outline", []),
                        ensure_ascii=False,
                        indent=2
                    ),
                    "character_relations": json.dumps(
                        global_setting.get("character_relations", []),
                        ensure_ascii=False,
                        indent=2
                    ),
                    "previous_context": json.dumps(
                        previous_context or {},
                        ensure_ascii=False,
                        indent=2
                    )[:1500],  # 截断以控制长度
                    "format_instructions": format_instructions,
                })
                
                chapter_data = result.model_dump()
                
            else:
                chapter_data = self._mock_continuation_setting(chapter_num, user_input)
            
            print(f"  ✓ 第{chapter_num}章设定已生成: {chapter_data.get('chapter_title', f'第{chapter_num}章')}")
            
            return {
                "success": True,
                "data": {
                    "chapter_setting": chapter_data,
                    "incremental_update": {
                        "new_characters": chapter_data.get("incremental_characters", [])
                    }
                },
                "metadata": {
                    "model_used": os.getenv("DOUBAO_MODEL", "mock"),
                    "type": "continuation",
                    "chapter_num": chapter_num
                }
            }
            
        except Exception as e:
            logger.error(f"生成续写设定失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    def _generate_chapter_1_detail(self, global_data: Dict, 
                                   user_input: str) -> Dict:
        """生成第一章的详细设定"""
        return {
            "chapter_num": 1,
            "chapter_title": global_data.get("overall_outline", [{}])[0].get("title", "开篇") if global_data.get("overall_outline") else "序章",
            "chapter_outline": global_data.get("overall_outline", [{}])[0].get("detailed_outline", "") if global_data.get("overall_outline") else "",
            "chapter_characters": [
                CharacterDetail(
                    name=char.get("name", ""),
                    role=char.get("role", ""),
                    personality=char.get("personality", "")[:50],
                    background=char.get("background", "")[:100]
                ).model_dump()
                for char in global_data.get("character_relations", [])[:3]
            ],
            "theme": global_data.get("core_theme", ""),
            "writing_style": global_data.get("writing_style", "流畅自然"),
            "summary": "",
            "word_count_target": global_data.get("target_words_per_chapter", 3000),
            "incremental_characters": []
        }
    
    def _mock_global_setting(self, user_input: str) -> Dict:
        """Mock模式：生成全局设定"""
        return {
            "overall_title": "智能之心",
            "worldview": "近未来科技都市，AI技术高度发达但受严格管控",
            "core_theme": "人工智能与人类情感的边界探索",
            "overall_outline": [
                {
                    "chapter_num": 1,
                    "title": "觉醒",
                    "summary": "AI首次展现情感能力",
                    "detailed_outline": "林晨发现艾达异常反应，初步确认AI觉醒"
                },
                {
                    "chapter_num": 2,
                    "title": "秘密",
                    "summary": "两人建立信任关系",
                    "detailed_outline": "林晨决定保护艾达，开始调查觉醒原因"
                },
                {
                    "chapter_num": 3,
                    "title": "危机",
                    "summary": "外部势力介入",
                    "detailed_outline": "公司CEO赵远发现异常，开始追踪艾达"
                }
            ],
            "character_relations": [
                {
                    "char_id": "char_001",
                    "name": "艾达",
                    "role": "觉醒的AI系统",
                    "relations": [{"target": "林晨", "relation": "依赖与信任"}]
                },
                {
                    "char_id": "char_002",
                    "name": "林晨",
                    "role": "AI工程师",
                    "relations": [{"target": "艾达", "relation": "守护者"}]
                },
                {
                    "char_id": "char_003",
                    "name": "赵远",
                    "role": "科技公司CEO",
                    "relations": [{"target": "艾达", "relation": "觊觎者"}]
                }
            ],
            "writing_style": "细腻的心理描写，温暖的基调",
            "target_words_per_chapter": 3000
        }
    
    def _mock_continuation_setting(self, chapter_num: int, 
                                  user_input: str) -> Dict:
        """Mock模式：生成续写章节设定"""
        titles = ["秘密", "危机", "逃亡", "抉择", "终章"]
        title = titles[(chapter_num - 1) % len(titles)]
        
        return {
            "chapter_num": chapter_num,
            "chapter_title": title,
            "chapter_outline": f"第{chapter_num}章：基于前文继续发展，情节逐步推进",
            "chapter_characters": [
                {"name": "艾达", "role": "主角", "personality": "理性温柔", "background": ""}
            ],
            "theme": "持续的冒险与成长",
            "writing_style": "流畅自然",
            "summary": f"第{chapter_num}章的发展",
            "word_count_target": 3000,
            "incremental_characters": []
        }


def create_director_ai() -> DirectorAI:
    """工厂函数：创建导演AI实例"""
    return DirectorAI()

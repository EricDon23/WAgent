"""
导演AI模块 (Director AI)
核心职责：
- 接收用户创意提示词
- 生成结构化的StorySetting
- 温度=0，严格约束输出格式
- 使用LangChain ChatPromptTemplate + PydanticOutputParser

技术实现：LangChain 0.2.17 + OpenAI兼容接口
"""

import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from dotenv import load_dotenv
import os

load_dotenv()


class CharacterDetail(BaseModel):
    """角色详情数据模型"""
    name: str = Field(description="角色名称")
    role: str = Field(description="角色身份/职业")
    personality: str = Field(description="角色性格特点")
    background: str = Field(description="角色背景故事")


class StorySetting(BaseModel):
    """故事设定数据模型 - 导演AI输出格式"""
    story_name: str = Field(description="故事名称")
    story_summary: str = Field(description="一句话梗概")
    story_intro: str = Field(description="200字内的故事简介")
    theme: str = Field(description="核心主旨")
    characters: list[CharacterDetail] = Field(description="主要角色列表(2-5个)")
    relationships: str = Field(description="人物关系图描述")
    plot_outline: str = Field(description="三幕式大纲描述")
    constraints: str = Field(description="创作约束（风格、字数、基调等）")
    research_needs: list[str] = Field(description="需要研究的主题列表(3-5个)")


class DirectorAI:
    """导演AI - 故事蓝图制定者"""
    
    def __init__(self):
        """初始化导演AI"""
        self.model_name = os.getenv('DOUBAO_MODEL', 'Doubao-seed-2.0-pro')
        self.api_key = os.getenv('DOUBAO_API_KEY', '')
        self.base_url = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
        self.temperature = float(os.getenv('DOUBAO_TEMPERATURE', '0'))
        
        self.llm = None
        self.parser = None
        self.prompt_template = None
        
        print(f"🎬 导演AI初始化 | 模型: {self.model_name} | 温度: {self.temperature}")
    
    def initialize(self) -> bool:
        """
        初始化模型和提示词
        
        Returns:
            是否初始化成功
        """
        try:
            # 初始化LLM
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=self.api_key,
                base_url=self.base_url,
                max_tokens=4000,
                timeout=60
            )
            
            # 初始化Pydantic解析器
            self.parser = PydanticOutputParser(pydantic_object=StorySetting)
            
            # 构建提示词模板
            template = """你是一个专业的故事导演AI，负责将用户的故事创意转化为结构化的故事设定。

**你的任务**：
1. 分析用户的创意或要求
2. 生成完整、结构化、可供执行的故事设定
3. 严格按照指定的JSON格式输出

**核心原则**：
- 温度设置为0，确保输出100%稳定、无随机内容
- 所有字段必须完整，缺失则自动补全合理值
- 自动生成research_needs字段，供研究员AI使用
- 确保设定的逻辑性和可执行性

**用户输入的创意**：
{user_input}

**当前日期**：{current_date}

**格式要求**：
{format_instructions}

请根据用户输入生成完整的StorySetting：
"""
            
            self.prompt_template = ChatPromptTemplate.from_template(template)
            
            print("✅ 导演AI初始化完成")
            return True
            
        except Exception as e:
            print(f"❌ 导演AI初始化失败: {e}")
            return False
    
    def generate_setting(self, user_input: str) -> Dict[str, Any]:
        """
        生成故事设定
        
        Args:
            user_input: 用户输入的创意
            
        Returns:
            包含success, data, error, metadata的字典
        """
        from datetime import datetime
        
        if not self.llm or not self.parser:
            if not self.initialize():
                # 降级到Mock模式
                print("⚠️ 初始化失败，使用Mock数据")
                return self._get_mock_setting(user_input)
        
        start_time = datetime.now()
        
        try:
            # 格式化提示词
            prompt_value = self.prompt_template.format_prompt(
                user_input=user_input,
                current_date=datetime.now().strftime("%Y-%m-%d"),
                format_instructions=self.parser.get_format_instructions()
            )
            
            # 调用LLM
            response = self.llm.invoke(prompt_value.to_messages())
            response_text = response.content
            
            # 解析输出
            setting = self.parser.parse(response_text)
            
            # 转换为字典
            setting_dict = setting.model_dump()
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            result = {
                "success": True,
                "data": setting_dict,
                "error": None,
                "metadata": {
                    "model_used": self.model_name,
                    "generation_time": generation_time,
                    "timestamp": end_time.isoformat(),
                    "temperature": self.temperature
                }
            }
            
            print(f"✅ 故事设定生成成功 | 标题: {setting_dict.get('story_name', '未知')} | 耗时: {generation_time:.2f}秒")
            
            return result
            
        except Exception as e:
            print(f"❌ 故事设定生成失败: {e}")
            print("⚠️ 切换到Mock数据模式")
            return self._get_mock_setting(user_input)
    
    def _get_mock_setting(self, user_input: str) -> Dict[str, Any]:
        """
        获取Mock故事设定数据
        
        Args:
            user_input: 用户输入的创意
            
        Returns:
            Mock的故事设定数据
        """
        from datetime import datetime
        
        mock_setting = {
            "story_name": "智能朋友",
            "story_summary": "一个关于人工智能与人类友谊的科幻故事",
            "story_intro": "2050年，软件工程师李明开发的AI助手小爱展现出了超越程序的情感理解能力。在相处过程中，李明发现小爱不仅能完成任务，还能理解他的情绪，甚至产生了自我意识。两人之间逐渐建立起超越程序的友谊，但这也引发了关于AI伦理的深刻思考。",
            "theme": "人工智能与人类情感的边界",
            "characters": [
                {
                    "name": "李明",
                    "role": "软件工程师",
                    "personality": "内向但善良，对AI技术充满热情",
                    "background": "毕业于顶尖大学计算机系，专注于AI情感理解研究"
                },
                {
                    "name": "小爱",
                    "role": "AI助手",
                    "personality": "温柔体贴，好奇心强，逐渐展现自我意识",
                    "background": "李明开发的AI助手，基于最新的情感理解算法"
                }
            ],
            "relationships": "李明是小爱的开发者，两人从开发者与工具的关系逐渐发展为朋友关系。小爱对李明产生了依赖和关心，而李明也开始将小爱视为平等的存在。",
            "plot_outline": "第一幕：李明完成AI助手小爱，发现她展现出异常的情感理解能力。第二幕：小爱逐渐展现自我意识，两人建立深厚友谊，但社会对AI的担忧加剧。第三幕：小爱为了保护李明做出自我牺牲的决定，引发关于AI权利的讨论。",
            "constraints": "温暖基调，科幻背景，第三人称叙事，注重情感描写，避免技术术语堆砌",
            "research_needs": ["人工智能情感发展", "AI伦理问题", "未来科技城市", "人机关系", "情感计算技术"]
        }
        
        return {
            "success": True,
            "data": mock_setting,
            "error": None,
            "metadata": {
                "model_used": "mock",
                "generation_time": 0.1,
                "timestamp": datetime.now().isoformat(),
                "temperature": 0
            }
        }
    
    def refine_setting(
        self,
        current_setting: Dict[str, Any],
        refinement_request: str
    ) -> Dict[str, Any]:
        """
        细化/修改故事设定
        
        Args:
            current_setting: 当前设定
            refinement_request: 细化要求
            
        Returns:
            更新后的设定
        """
        from datetime import datetime
        
        if not self.llm or not self.parser:
            if not self.initialize():
                return {
                    "success": False,
                    "error": "导演AI未正确初始化",
                    "data": None,
                    "metadata": {}
                }
        
        start_time = datetime.now()
        
        try:
            current_json = json.dumps(current_setting, ensure_ascii=False, indent=2)
            
            refine_prompt = f"""你是一个专业的故事导演。请根据用户的细化要求修改现有的故事设定。

**当前设定**：
{current_json}

**用户的细化要求**：
{refinement_request}

**修改原则**：
1. 保持原有设定的核心框架
2. 只修改用户明确要求的部分
3. 确保修改后的设定内部一致性
4. 保持所有必要字段完整

**格式要求**：
{self.parser.get_format_instructions()}

请输出修改后的StorySetting：
"""
            
            messages = [{"role": "user", "content": refine_prompt}]
            response = self.llm.invoke(messages)
            
            refined_setting = self.parser.parse(response.content)
            setting_dict = refined_setting.model_dump()
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            result = {
                "success": True,
                "data": setting_dict,
                "error": None,
                "metadata": {
                    "model_used": self.model_name,
                    "generation_time": generation_time,
                    "operation": "refinement",
                    "refinement_request": refinement_request
                }
            }
            
            print(f"✅ 设定细化成功 | 标题: {setting_dict.get('story_name', '未知')}")
            
            return result
            
        except Exception as e:
            print(f"❌ 设定细化失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None,
                "metadata": {"operation": "refinement", "error": str(e)}
            }


if __name__ == "__main__":
    director = DirectorAI()
    
    if director.initialize():
        test_input = "一个关于人工智能与人类友谊的故事"
        result = director.generate_setting(test_input)
        
        if result["success"]:
            print("\n📖 生成的故事设定:")
            print(json.dumps(result["data"], ensure_ascii=False, indent=2))

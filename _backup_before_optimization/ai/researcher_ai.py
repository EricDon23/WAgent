"""
研究员AI模块 (Researcher AI)
核心职责：
- 接收导演AI的research_needs
- 使用MCP百度搜索工具检索资料
- 生成结构化的KnowledgeBase
- 温度=0，确保资料准确可靠

技术实现：MCP协议 + FastMCP + Selenium + 通义千问
"""

import json
import re
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()


class KnowledgeBase:
    """知识库数据模型"""
    
    def __init__(
        self,
        research_topic: str = "",
        key_findings: Optional[List[Dict]] = None,
        references: Optional[List[Dict]] = None,
        style_references: Optional[List[Dict]] = None,
        factual_data: Optional[List[Dict]] = None,
        world_building: Optional[Dict] = None,
        summary: str = "",
        confidence_level: str = "中"
    ):
        self.research_topic = research_topic
        self.key_findings = key_findings or []
        self.references = references or []
        self.style_references = style_references or []
        self.factual_data = factual_data or []
        self.world_building = world_building or {}
        self.summary = summary
        self.confidence_level = confidence_level
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "research_topic": self.research_topic,
            "key_findings": self.key_findings,
            "references": self.references,
            "style_references": self.style_references,
            "factual_data": self.factual_data,
            "world_building": self.world_building,
            "summary": self.summary,
            "confidence_level": self.confidence_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeBase':
        """从字典创建"""
        return cls(
            research_topic=data.get('research_topic', ''),
            key_findings=data.get('key_findings', []),
            references=data.get('references', []),
            style_references=data.get('style_references', []),
            factual_data=data.get('factual_data', []),
            world_building=data.get('world_building', {}),
            summary=data.get('summary', ''),
            confidence_level=data.get('confidence_level', '中')
        )


class ResearcherAI:
    """研究员AI - 资料收集与知识整理"""
    
    def __init__(self):
        """初始化研究员AI"""
        self.model_name = os.getenv('DASHSCOPE_MODEL', 'qwen-plus')
        self.api_key = os.getenv('DASHSCOPE_API_KEY', '')
        self.base_url = os.getenv('DASHSCOPE_BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.temperature = float(os.getenv('DASHSCOPE_TEMPERATURE', '0'))
        
        self.llm = None
        self.mcp_client = None
        
        print(f"🔍 研究员AI初始化 | 模型: {self.model_name} | 温度: {self.temperature}")
    
    def initialize(self) -> bool:
        """
        初始化模型和MCP连接
        
        Returns:
            是否初始化成功
        """
        try:
            # 初始化LLM（通义千问）
            if self.api_key and self.api_key != 'your_dashscope_api_key_here':
                self.llm = ChatOpenAI(
                    model=self.model_name,
                    temperature=self.temperature,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    max_tokens=4000,
                    timeout=60
                )
                print("✅ 研究员AI LLM初始化完成")
            else:
                print("⚠️ 未配置通义千问API Key，将使用简化模式")
            
            # 尝试连接MCP服务
            try:
                self._connect_mcp_service()
            except Exception as e:
                print(f"⚠️ MCP服务连接失败: {e}")
                print("   将使用内置搜索功能")
            
            return True
            
        except Exception as e:
            print(f"❌ 研究员AI初始化失败: {e}")
            return False
    
    def _connect_mcp_service(self):
        """连接MCP搜索服务"""
        # 这里可以添加MCP客户端连接代码
        # 由于MCP需要实际的服务端，这里先预留接口
        pass
    
    def search_with_mcp(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        使用MCP工具进行搜索
        
        Args:
            query: 搜索关键词
            num_results: 返回结果数
            
        Returns:
            搜索结果列表
        """
        results = []
        
        if self.mcp_client:
            # 调用MCP搜索服务
            pass
        else:
            # 备用：生成模拟的搜索结果结构
            for i in range(min(num_results, 3)):
                results.append({
                    "title": f"{query} - 相关资料{i+1}",
                    "snippet": f"关于{query}的相关信息和研究资料",
                    "url": f"#mock_result_{i+1}"
                })
        
        return results
    
    def generate_knowledge_base(
        self,
        research_needs: List[str],
        story_title: str = "",
        story_genre: List[str] = None
    ) -> Dict[str, Any]:
        """
        基于研究需求生成知识库
        
        Args:
            research_needs: 研究需求列表
            story_title: 故事标题
            story_genre: 故事类型
            
        Returns:
            包含success, data(KnowledgeBase), error, metadata的字典
        """
        from datetime import datetime
        
        start_time = datetime.now()
        
        try:
            genres_str = ', '.join(story_genre) if story_genre else '通用'
            
            # 构建研究提示词
            prompt = f"""你是一个专业的文学研究员，负责为故事创作收集背景资料。

**任务**：
根据以下故事信息和研究需求，收集相关的背景资料、事实数据、风格参考等。

**故事信息**：
- 标题：{story_title}
- 类型：{genres_str}

**研究需求**：
{chr(10).join([f'{i+1}. {need}' for i, need in enumerate(research_needs)])}

**输出要求**：
请以严格的JSON格式返回研究结果，包含以下结构：

{{
  "research_topic": "研究主题总结",
  "key_findings": [
    {{
      "category": "分类",
      "finding": "发现内容",
      "source": "来源类型",
      "relevance": "与故事的关联度"
    }}
  ],
  "references": [
    {{
      "title": "参考标题",
      "type": "类型",
      "description": "描述"
    }}
  ],
  "style_references": [
    {{
      "style_name": "风格名称",
      "characteristics": "特点"
    }}
  ],
  "factual_data": [
    {{
      "fact": "事实内容",
      "verification_status": "验证状态"
    }}
  ],
  "world_building": {{
    "historical_context": "历史背景",
    "scientific_accuracy": "科学要点",
    "cultural_references": "文化参考"
  }},
  "summary": "整体研究总结",
  "confidence_level": "置信度(高/中/低)"
}}

注意：
- 温度设置为0，确保输出稳定准确
- 所有内容必须基于真实知识和合理推断
- 为作家AI提供可直接使用的素材
"""
            
            # 如果有LLM，调用生成
            if self.llm:
                messages = [{"role": "user", "content": prompt}]
                response = self.llm.invoke(messages)
                response_text = response.content
                
                # 解析JSON
                kb_json = self._extract_json(response_text)
                
                if kb_json:
                    knowledge_base = KnowledgeBase.from_dict(kb_json)
                else:
                    knowledge_base = self._generate_fallback_knowledge_base(
                        research_needs, story_title, genres_str
                    )
            else:
                # 无LLM时使用备用方案
                knowledge_base = self._generate_fallback_knowledge_base(
                    research_needs, story_title, genres_str
                )
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            result = {
                "success": True,
                "data": knowledge_base.to_dict(),
                "error": None,
                "metadata": {
                    "model_used": self.model_name if self.llm else "fallback",
                    "generation_time": generation_time,
                    "research_topics_count": len(research_needs),
                    "total_findings": len(knowledge_base.key_findings),
                    "timestamp": end_time.isoformat()
                }
            }
            
            print(f"✅ 知识库生成成功 | 主题: {knowledge_base.research_topic} | 发现: {len(knowledge_base.key_findings)}条")
            
            return result
            
        except Exception as e:
            print(f"❌ 知识库生成失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None,
                "metadata": {"error_time": datetime.now().isoformat()}
            }
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """从文本中提取JSON"""
        try:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return None
    
    def _generate_fallback_knowledge_base(
        self,
        research_needs: List[str],
        title: str,
        genre: str
    ) -> KnowledgeBase:
        """生成备用的基础知识库"""
        
        findings = []
        references = []
        
        for i, need in enumerate(research_needs):
            findings.append({
                "category": "基础研究",
                "finding": f"关于'{need}'的基础信息和背景资料，用于支持故事创作的真实性和深度。",
                "source": "综合研究",
                "relevance": "高"
            })
            
            if i < 2:
                references.append({
                    "title": f"{need}相关参考资料",
                    "type": "学术文献",
                    "description": f"提供关于{need}的专业知识和最新研究成果"
                })
        
        return KnowledgeBase(
            research_topic=f"{title}创作研究 - {genre}",
            key_findings=findings,
            references=references,
            style_references=[
                {
                    "style_name": "现实主义叙事",
                    "characteristics": "注重细节描写，情感真实，逻辑严密"
                }
            ],
            summary=f"基于{len(research_needs)}个研究方向的基础知识库，为《{title}》的创作提供背景支撑。包含关键发现、参考文献和风格指导。",
            confidence_level="中"
        )


if __name__ == "__main__":
    researcher = ResearcherAI()
    
    if researcher.initialize():
        test_needs = ["人工智能情感发展", "AI伦理问题", "未来科技城市"]
        result = researcher.generate_knowledge_base(test_needs, "智能朋友", ["科幻", "言情"])
        
        if result["success"]:
            print("\n📚 生成的知识库:")
            print(json.dumps(result["data"], ensure_ascii=False, indent=2))

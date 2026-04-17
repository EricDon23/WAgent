"""
小说数据存储模块
管理故事的元数据、章节信息、状态等
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class NovelData:
    """小说数据管理器"""
    
    def __init__(self, story_id: str = "story_001", base_dir: str = "stories"):
        """
        初始化
        
        Args:
            story_id: 故事ID
            base_dir: 基础目录
        """
        self.story_id = story_id
        self.base_path = Path(base_dir) / story_id
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保目录结构存在"""
        dirs = ['settings', 'research', 'drafts', 'states']
        for dir_name in dirs:
            (self.base_path / dir_name).mkdir(parents=True, exist_ok=True)
        
        print(f"✅ 小说数据目录已准备 | 路径: {self.base_path}")
    
    def save_setting(self, setting_data: Dict[str, Any], version: int = 1) -> str:
        """
        保存故事设定
        
        Args:
            setting_data: 设定数据（StorySetting）
            version: 版本号
            
        Returns:
            保存的文件路径
        """
        filename = f"setting_v{version}.json"
        filepath = self.base_path / 'settings' / filename
        
        data = {
            "version": version,
            "story_id": self.story_id,
            "saved_at": datetime.now().isoformat(),
            "setting": setting_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 设定已保存 | 文件: {filename}")
        return str(filepath)
    
    def load_latest_setting(self) -> Optional[Dict[str, Any]]:
        """加载最新版本的故事设定"""
        settings_dir = self.base_path / 'settings'
        
        if not settings_dir.exists():
            return None
        
        setting_files = list(settings_dir.glob('setting_*.json'))
        
        if not setting_files:
            return None
        
        # 找到最新版本
        latest_file = max(setting_files, key=lambda f: f.stat().st_mtime)
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_knowledge_base(self, kb_data: Dict[str, Any]) -> str:
        """
        保存知识库
        
        Args:
            kb_data: 知识库数据
            
        Returns:
            保存的文件路径
        """
        filename = "knowledge_base.json"
        filepath = self.base_path / 'research' / filename
        
        data = {
            "story_id": self.story_id,
            "saved_at": datetime.now().isoformat(),
            "knowledge_base": kb_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 知识库已保存 | 文件: {filename}")
        return str(filepath)
    
    def load_knowledge_base(self) -> Optional[Dict[str, Any]]:
        """加载知识库"""
        filepath = self.base_path / 'research' / 'knowledge_base.json'
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_chapter(
        self,
        chapter_num: int,
        content: str,
        round_num: int = 1,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        保存章节内容
        
        Args:
            chapter_num: 章节号
            content: 章节内容
            round_num: 回合数
            metadata: 元数据
            
        Returns:
            保存的文件路径
        """
        filename = f"round_{round_num}.md"
        filepath = self.base_path / 'drafts' / filename
        
        md_content = f"""# 第{chapter_num}章

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**回合**: 第{round_num}轮
**字数**: 约{len(content.replace(' ', ''))}字

---

{content}

---
*由 WAgent 作家AI 自动生成*
"""
        
        if metadata:
            meta_str = "\n".join([f"- **{k}**: {v}" for k, v in metadata.items()])
            md_content = md_content.replace("---\n*由 WAgent*", f"---\n## 元数据\n{meta_str}\n\n---\n*由 WAgent*")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"✅ 章节{chapter_num}已保存 | 文件: {filename}")
        return str(filepath)
    
    def load_chapter(self, round_num: int = 1) -> Optional[str]:
        """加载指定回合的章节"""
        filename = f"round_{round_num}.md"
        filepath = self.base_path / 'drafts' / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    def get_novel_metadata(self) -> Dict[str, Any]:
        """获取小说元数据"""
        setting = self.load_latest_setting()
        kb = self.load_knowledge_base()
        
        drafts_dir = self.base_path / 'drafts'
        draft_files = list(drafts_dir.glob('round_*.md')) if drafts_dir.exists() else []
        
        metadata = {
            "story_id": self.story_id,
            "total_rounds": len(draft_files),
            "has_setting": setting is not None,
            "has_knowledge_base": kb is not None,
            "created_at": None,
            "last_updated": None
        }
        
        if setting:
            metadata['created_at'] = setting.get('saved_at')
            metadata['title'] = setting.get('setting', {}).get('story_name', '未命名')
        
        if draft_files:
            latest_draft = max(draft_files, key=lambda f: f.stat().st_mtime)
            metadata['last_updated'] = datetime.fromtimestamp(
                latest_draft.stat().st_mtime
            ).isoformat()
        
        return metadata
    
    def get_story_summary(self) -> str:
        """获取故事摘要"""
        metadata = self.get_novel_metadata()
        
        summary_parts = [
            f"【故事ID】{metadata['story_id']}",
            f"【标题】{metadata.get('title', '未命名')}",
            f"【已生成】{metadata['total_rounds']}轮",
            f"【有设定】{'是' if metadata['has_setting'] else '否'}",
            f"【有资料】{'是' if metadata['has_knowledge_base'] else '否'}",
        ]
        
        if metadata.get('created_at'):
            summary_parts.append(f"【创建时间】{metadata['created_at']}")
        if metadata.get('last_updated'):
            summary_parts.append(f"【最后更新】{metadata['last_updated']}")
        
        return "\n".join(summary_parts)


if __name__ == "__main__":
    novel = NovelData("test_story")
    
    print("\n📊 测试结果:")
    print(novel.get_story_summary())

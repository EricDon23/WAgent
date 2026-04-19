#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WAgent V3.1 本地文件存储模块

基于错误修改.md强制要求实现：
- 分层存储：global.json（总设定）+ chapters/{x}.json（章节设定）
- 锁定机制：global.json锁定，AI不能自动覆盖
- 增量更新：后续章节自动追加到全局大纲和人物关系
"""

import os
import json
import uuid
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class LocalStorage:
    """
    本地文件存储 - V3.1核心存储引擎
    
    存储结构：
    stories/
      └── {story_id}/
           ├── meta.json             # 故事元数据
           ├── global.json           # 全局设定（锁定，总大纲+总人物关系）
           ├── chapters/
           │    ├── 1.json           # 第1章设定
           │    ├── 2.json           # 第2章设定
           │    └── ...
           ├── drafts/               # 章节内容(Markdown)
           │    ├── chapter_1.md
           │    └── ...
           └── research/             # 研究资料
                └── chapter_{x}.json
    """
    
    def __init__(self, base_dir: str = "stories"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_story_dir(self, story_id: str) -> Path:
        return self.base_dir / story_id
    
    def _ensure_story_structure(self, story_id: str) -> Path:
        """确保故事目录结构完整"""
        story_dir = self._get_story_dir(story_id)
        story_dir.mkdir(parents=True, exist_ok=True)
        
        (story_dir / "chapters").mkdir(exist_ok=True)
        (story_dir / "drafts").mkdir(exist_ok=True)
        (story_dir / "research").mkdir(exist_ok=True)
        
        return story_dir
    
    def _read_json(self, file_path: Path) -> Optional[Dict]:
        """安全读取JSON文件"""
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"读取JSON失败 {file_path}: {e}")
        return None
    
    def _write_json(self, file_path: Path, data: Dict) -> bool:
        """安全写入JSON文件"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"写入JSON失败 {file_path}: {e}")
            return False
    
    # ============================================
    # 全局设定管理 - global.json（锁定模式）
    # ============================================
    
    def create_global_setting(self, story_id: str, setting: Dict) -> Dict[str, Any]:
        """
        创建全局设定（仅第一章调用）
        
        存储：总标题、总设定、三幕式总大纲、总人物关系
        状态：锁定（is_locked=True），AI不能自动覆盖
        """
        story_dir = self._ensure_story_structure(story_id)
        
        global_setting = {
            "story_id": story_id,
            "version": 1,
            "is_locked": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            
            # 核心数据（锁定后不可修改）
            "overall_title": setting.get("overall_title", ""),
            "worldview": setting.get("worldview", ""),
            "core_theme": setting.get("core_theme", ""),
            
            # 三幕式总大纲（可追加新章节条目）
            "overall_outline": setting.get("overall_outline", []),
            
            # 总人物关系（可追加新角色）
            "overall_character_relations": setting.get("overall_character_relations", []),
            
            # 原始完整设定备份
            "original_setting": setting,
            
            # 统计信息
            "total_chapters": 0,
            "status": "ongoing"
        }
        
        global_file = story_dir / "global.json"
        self._write_json(global_file, global_setting)
        
        logger.info(f"已创建并锁定全局设定: {story_id}")
        return global_setting
    
    def get_global_setting(self, story_id: str) -> Optional[Dict]:
        """获取全局设定"""
        story_dir = self._get_story_dir(story_id)
        global_file = story_dir / "global.json"
        return self._read_json(global_file)
    
    def is_global_locked(self, story_id: str) -> bool:
        """检查全局设定是否锁定"""
        setting = self.get_global_setting(story_id)
        if setting:
            return setting.get("is_locked", True)
        return False
    
    def append_to_overall_outline(self, story_id: str, chapter_outline: Dict) -> bool:
        """
        向总体大纲追加新章节（增量更新）
        
        仅追加，不修改已有内容
        """
        story_dir = self._get_story_dir(story_id)
        global_file = story_dir / "global.json"
        global_setting = self._read_json(global_file)
        
        if not global_setting:
            return False
        
        if "overall_outline" not in global_setting:
            global_setting["overall_outline"] = []
        
        chapter_num = chapter_outline.get("chapter_num")
        existing_chapters = {c.get("chapter_num") for c in global_setting["overall_outline"]}
        
        if chapter_num not in existing_chapters:
            global_setting["overall_outline"].append(chapter_outline)
            global_setting["version"] += 1
            global_setting["updated_at"] = datetime.now().isoformat()
            global_setting["total_chapters"] = len(global_setting["overall_outline"])
            
            self._write_json(global_file, global_setting)
            logger.info(f"向总体大纲追加第{chapter_num}章")
            return True
        
        return False
    
    def append_to_character_relations(self, story_id: str, new_characters: List[Dict]) -> bool:
        """
        向总体人物关系追加新角色（增量更新）
        
        仅追加新角色，不修改已有角色
        """
        story_dir = self._get_story_dir(story_id)
        global_file = story_dir / "global.json"
        global_setting = self._read_json(global_file)
        
        if not global_setting:
            return False
        
        if "overall_character_relations" not in global_setting:
            global_setting["overall_character_relations"] = []
        
        existing_char_ids = {c.get("char_id") for c in global_setting["overall_character_relations"]}
        
        added_count = 0
        for char in new_characters:
            if "char_id" not in char:
                char["char_id"] = str(uuid.uuid4())
            
            char_id = char["char_id"]
            if char_id not in existing_char_ids:
                char["added_at"] = datetime.now().isoformat()
                global_setting["overall_character_relations"].append(char)
                added_count += 1
        
        if added_count > 0:
            global_setting["version"] += 1
            global_setting["updated_at"] = datetime.now().isoformat()
            self._write_json(global_file, global_setting)
            logger.info(f"向总体人物关系追加{added_count}个角色")
            return True
        
        return False
    
    # ============================================
    # 章节局部设定管理 - chapters/{x}.json
    # ============================================
    
    def save_chapter_setting(self, story_id: str, chapter_num: int, 
                           chapter_setting: Dict) -> bool:
        """
        保存章节局部设定
        
        存储：第x章标题、第x章大纲、第x章人物、第x章主题
        """
        story_dir = self._ensure_story_structure(story_id)
        
        chapter_data = {
            "story_id": story_id,
            "chapter_num": chapter_num,
            "created_at": datetime.now().isoformat(),
            
            # 章节核心数据
            "chapter_title": chapter_setting.get("chapter_title", ""),
            "chapter_outline": chapter_setting.get("chapter_outline", ""),
            "chapter_characters": chapter_setting.get("chapter_characters", []),
            "theme": chapter_setting.get("theme", ""),
            
            # 扩展信息
            "writing_style": chapter_setting.get("writing_style", ""),
            "summary": chapter_setting.get("summary", ""),
            "word_count": chapter_setting.get("word_count", 0),
            
            # 原始完整数据
            "raw_setting": chapter_setting
        }
        
        chapter_file = story_dir / "chapters" / f"{chapter_num}.json"
        return self._write_json(chapter_file, chapter_data)
    
    def get_chapter_setting(self, story_id: str, chapter_num: int) -> Optional[Dict]:
        """获取章节局部设定"""
        story_dir = self._get_story_dir(story_id)
        chapter_file = story_dir / "chapters" / f"{chapter_num}.json"
        return self._read_json(chapter_file)
    
    def get_previous_chapter_context(self, story_id: str, current_chapter: int) -> Optional[Dict]:
        """
        获取前一章的上下文（续写时必须调用）
        
        返回前一章的大纲、人物、主题等关键信息
        """
        if current_chapter <= 1:
            return None
        
        prev_chapter = current_chapter - 1
        return self.get_chapter_setting(story_id, prev_chapter)
    
    # ============================================
    # 章节内容管理 - drafts/chapter_{x}.md
    # ============================================
    
    def save_chapter_content(self, story_id: str, chapter_num: int, 
                          content: str) -> bool:
        """保存章节内容（Markdown格式）"""
        story_dir = self._ensure_story_structure(story_id)
        content_file = story_dir / "drafts" / f"chapter_{chapter_num}.md"
        
        try:
            with open(content_file, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"保存章节内容失败: {e}")
            return False
    
    def get_chapter_content(self, story_id: str, chapter_num: int) -> Optional[str]:
        """获取章节内容"""
        story_dir = self._get_story_dir(story_id)
        content_file = story_dir / "drafts" / f"chapter_{chapter_num}.md"
        
        if content_file.exists():
            try:
                with open(content_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"读取章节内容失败: {e}")
        return None
    
    # ============================================
    # 研究资料管理 - research/chapter_{x}.json
    # ============================================
    
    def save_research(self, story_id: str, chapter_num: int, 
                     research_data: Dict) -> bool:
        """保存研究资料"""
        story_dir = self._ensure_story_structure(story_id)
        research_file = story_dir / "research" / f"chapter_{chapter_num}.json"
        return self._write_json(research_file, research_data)
    
    def get_research(self, story_id: str, chapter_num: int) -> Optional[Dict]:
        """获取研究资料"""
        story_dir = self._get_story_dir(story_id)
        research_file = story_dir / "research" / f"chapter_{chapter_num}.json"
        return self._read_json(research_file)
    
    # ============================================
    # 元数据管理 - meta.json
    # ============================================
    
    def create_meta(self, story_id: str, session_id: str, story_name: str) -> Dict:
        """创建故事元数据"""
        story_dir = self._ensure_story_structure(story_id)
        
        meta = {
            "story_id": story_id,
            "session_id": session_id,
            "story_name": story_name,
            "chapter_count": 0,
            "total_words": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        meta_file = story_dir / "meta.json"
        self._write_json(meta_file, meta)
        return meta
    
    def get_meta(self, story_id: str) -> Optional[Dict]:
        """获取故事元数据"""
        story_dir = self._get_story_dir(story_id)
        meta_file = story_dir / "meta.json"
        return self._read_json(meta_file)
    
    def update_meta(self, story_id: str, **kwargs) -> bool:
        """更新故事元数据"""
        story_dir = self._get_story_dir(story_id)
        meta_file = story_dir / "meta.json"
        meta = self._read_json(meta_file)
        
        if meta:
            meta.update(kwargs)
            meta["updated_at"] = datetime.now().isoformat()
            return self._write_json(meta_file, meta)
        return False
    
    # ============================================
    # 删除与清理
    # ============================================
    
    def delete_story(self, story_id: str) -> Tuple[bool, str]:
        """
        删除故事及其所有数据
        
        Returns:
            (是否成功, 消息)
        """
        story_dir = self._get_story_dir(story_id)
        
        if story_dir.exists():
            try:
                shutil.rmtree(str(story_dir))
                logger.info(f"已彻底删除故事: {story_id}")
                return True, f"故事 {story_id} 已删除"
            except Exception as e:
                error_msg = f"删除失败: {e}"
                logger.error(error_msg)
                return False, error_msg
        
        return True, "故事不存在"
    
    def list_stories(self) -> List[Dict]:
        """列出所有故事"""
        stories = []
        
        if self.base_dir.exists():
            for item in self.base_dir.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    meta = self.get_meta(item.name)
                    if meta:
                        stories.append(meta)
        
        return sorted(stories, key=lambda x: x.get("updated_at", ""), reverse=True)
    
    def story_exists(self, story_id: str) -> bool:
        """检查故事是否存在"""
        story_dir = self._get_story_dir(story_id)
        return story_dir.exists()

    def save_story(self, story_data: Dict):
        """
        保存故事数据（分层存储）
        
        根据错误修改.md要求：
        - global.json：存储总设定、总大纲、总人物关系（锁定）
        - chapters/{x}.json：存储第x章的大纲、人物、设定
        """
        story_id = story_data.get("story_id", "")
        if not story_id:
            return False
        
        # 保存全局设定（global.json）
        if "global" in story_data:
            self.create_global_setting(story_id, story_data["global"])
        
        # 保存章节数据（chapters/{x}.json）
        if "chapters" in story_data:
            for chapter_num, chapter_data in story_data["chapters"].items():
                self.save_chapter_setting(story_id, int(chapter_num), chapter_data)
        
        logger.info(f"分层存储已保存故事: {story_id}")
        return True


def create_local_storage(base_dir: str = "stories") -> LocalStorage:
    """工厂函数：创建本地存储实例"""
    return LocalStorage(base_dir)

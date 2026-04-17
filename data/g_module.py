"""
G模块 - 数据记忆模块（Redis持久化存储）
核心功能：
- 存储StoryState（故事状态）
- 持久化记忆，防止内容偏移
- 支持多故事并行管理
"""

import json
import redis
from datetime import datetime
from typing import Optional, Dict, Any
from data.redis_config import RedisConfig


class GModule:
    """G模块 - 数据记忆管理器"""
    
    def __init__(self, story_id: str = "story_001"):
        """
        初始化G模块
        
        Args:
            story_id: 故事ID
        """
        self.story_id = story_id
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """连接Redis"""
        try:
            params = RedisConfig.get_connection_params()
            self.redis_client = redis.Redis(**params)
            self.redis_client.ping()
            print(f"✅ G模块已连接Redis | 故事ID: {self.story_id}")
            return True
        except Exception as e:
            print(f"⚠️ Redis连接失败: {e}")
            print("   将使用本地文件作为备用存储")
            self.redis_client = None
            return False
    
    def get_state_key(self) -> str:
        """获取状态键名"""
        return f"{self.story_id}:state"
    
    def save_story_state(self, state: Dict[str, Any]) -> bool:
        """
        保存故事状态
        
        Args:
            state: StoryState字典
            
        Returns:
            是否保存成功
        """
        try:
            state_json = json.dumps(state, ensure_ascii=False, indent=2)
            
            if self.redis_client:
                key = self.get_state_key()
                self.redis_client.setex(
                    key,
                    RedisConfig.TTL,
                    state_json
                )
                print(f"✅ 状态已保存到Redis | 键: {key}")
            else:
                # 备用：保存到本地文件
                import os
                os.makedirs('data/states', exist_ok=True)
                filepath = f'data/states/{self.story_id}_state.json'
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(state_json)
                print(f"✅ 状态已保存到本地文件 | 文件: {filepath}")
            
            return True
        except Exception as e:
            print(f"❌ 保存状态失败: {e}")
            return False
    
    def load_story_state(self) -> Optional[Dict[str, Any]]:
        """
        加载故事状态
        
        Returns:
            StoryState字典或None
        """
        try:
            if self.redis_client:
                key = self.get_state_key()
                state_json = self.redis_client.get(key)
                
                if state_json:
                    print(f"✅ 从Redis加载状态成功 | 键: {key}")
                    return json.loads(state_json)
                else:
                    print(f"⚠️ Redis中无此故事的状态记录")
                    return None
            else:
                # 备用：从本地文件加载
                filepath = f'data/states/{self.story_id}_state.json'
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                    print(f"✅ 从本地文件加载状态成功")
                    return state
                else:
                    print(f"⚠️ 本地无状态文件")
                    return None
                    
        except Exception as e:
            print(f"❌ 加载状态失败: {e}")
            return None
    
    def create_initial_state(self, story_setting: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建初始状态
        
        Args:
            story_setting: 故事设定
            
        Returns:
            初始StoryState
        """
        now = datetime.now().isoformat()
        
        initial_state = {
            "story_id": self.story_id,
            "created_at": now,
            "updated_at": now,
            "current_round": 0,
            "current_chapter": 0,
            "total_words": 0,
            
            "story_setting": story_setting,
            
            "generated_chapters": [],
            "chapter_contents": {},
            
            "character_developments": {},
            "plot_advancements": [],
            "consistency_checks": [],
            
            "next_suggestions": [],
            "user_feedback_history": []
        }
        
        self.save_story_state(initial_state)
        print(f"✅ 初始状态已创建 | 故事ID: {self.story_id}")
        
        return initial_state
    
    def update_state_after_generation(
        self,
        chapter_num: int,
        chapter_content: str,
        word_count: int,
        character_updates: Optional[Dict] = None,
        plot_points: Optional[list] = None
    ) -> bool:
        """
        生成后更新状态
        
        Args:
            chapter_num: 章节号
            chapter_content: 章节内容
            word_count: 字数
            character_updates: 角色发展更新
            plot_points: 情节推进点
            
        Returns:
            是否更新成功
        """
        state = self.load_story_state()
        
        if not state:
            print("❌ 无法加载状态进行更新")
            return False
        
        now = datetime.now().isoformat()
        
        # 更新基本信息
        state['current_round'] += 1
        state['current_chapter'] = chapter_num
        state['total_words'] += word_count
        state['updated_at'] = now
        
        # 记录章节信息
        state['generated_chapters'].append({
            "chapter_number": chapter_num,
            "generated_at": now,
            "word_count": word_count
        })
        
        # 保存章节内容（只保存摘要以节省空间）
        content_preview = chapter_content[:500] + "..." if len(chapter_content) > 500 else chapter_content
        state['chapter_contents'][f"chapter_{chapter_num}"] = {
            "preview": content_preview,
            "full_length": len(chapter_content),
            "saved_at": now
        }
        
        # 更新角色发展
        if character_updates:
            if not state.get('character_developments'):
                state['character_developments'] = {}
            for char_name, development in character_updates.items():
                state['character_developments'][char_name] = state['character_developments'].get(char_name, [])
                state['character_developments'][char_name].append({
                    "chapter": chapter_num,
                    "development": development,
                    "timestamp": now
                })
        
        # 更新情节推进
        if plot_points:
            for point in plot_points:
                state['plot_advancements'].append({
                    "chapter": chapter_num,
                    "point": point,
                    "timestamp": now
                })
        
        # 生成下一步建议
        state['next_suggestions'] = [
            f"基于第{chapter_num}章的结尾，继续发展{state.get('story_setting', {}).get('theme', '')}主题",
            "保持角色性格一致性",
            "注意前后文连贯性"
        ]
        
        success = self.save_story_state(state)
        
        if success:
            print(f"✅ 状态已更新 | 当前章节: 第{chapter_num}章 | 总字数: {state['total_words']}")
        
        return success
    
    def check_memory_exists(self) -> bool:
        """
        检查记忆是否存在
        
        Returns:
            是否存在记忆
        """
        state = self.load_story_state()
        return state is not None
    
    def get_memory_summary(self) -> str:
        """
        获取记忆摘要（供AI使用）
        
        Returns:
            记忆摘要文本
        """
        state = self.load_story_state()
        
        if not state:
            return "暂无历史记忆。"
        
        summary_parts = []
        
        # 基本信息
        summary_parts.append(f"【当前进度】已完成第{state.get('current_chapter', 0)}章，共{state.get('total_words', 0)}字")
        
        # 已生成章节列表
        chapters = state.get('generated_chapters', [])
        if chapters:
            chapter_list = ", ".join([f"第{c['chapter_number']}章" for c in chapters])
            summary_parts.append(f"【已生成章节】{chapter_list}")
        
        # 角色发展
        char_devs = state.get('character_developments', {})
        if char_devs:
            char_summaries = []
            for char_name, developments in char_devs.items():
                latest = developments[-1] if developments else {}
                char_summaries.append(f"{char_name}: {latest.get('development', '发展中')}")
            summary_parts.append(f"【角色发展】{'; '.join(char_summaries)}")
        
        # 情节推进
        plot_points = state.get('plot_advancements', [])
        if plot_points:
            recent_plots = [p['point'] for p in plot_points[-3:]]  # 最近3个情节点
            summary_parts.append(f"【最近情节】{'; '.join(recent_plots)}")
        
        # 下一步建议
        suggestions = state.get('next_suggestions', [])
        if suggestions:
            summary_parts.append(f"【创作建议】{suggestions[0]}")
        
        return "\n".join(summary_parts)
    
    def clear_memory(self) -> bool:
        """清除所有记忆"""
        try:
            if self.redis_client:
                key = self.get_state_key()
                self.redis_client.delete(key)
                print(f"✅ Redis记忆已清除 | 键: {key}")
            else:
                filepath = f'data/states/{self.story_id}_state.json'
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"✅ 本地状态文件已删除")
            
            return True
        except Exception as e:
            print(f"❌ 清除记忆失败: {e}")
            return False


if __name__ == "__main__":
    g_module = GModule("test_story")
    
    test_state = {
        "test": True,
        "message": "这是测试状态"
    }
    
    g_module.create_initial_state(test_state)
    loaded = g_module.load_story_state()
    
    print("\n📊 测试结果:")
    print(json.dumps(loaded, ensure_ascii=False, indent=2))

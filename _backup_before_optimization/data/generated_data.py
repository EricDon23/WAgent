"""
生成数据管理模块
管理所有生成的数据、版本控制、导出功能
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class GeneratedData:
    """生成数据管理器"""
    
    def __init__(self, base_dir: str = "generated_data"):
        """
        初始化
        
        Args:
            base_dir: 基础目录
        """
        self.base_path = Path(base_dir)
        self.base_path.mkdir(exist_ok=True)
        
        print(f"✅ 生成数据目录已准备 | 路径: {self.base_path}")
    
    def save_generation_record(
        self,
        generation_type: str,  # 'director', 'researcher', 'writer'
        data: Dict[str, Any],
        story_id: str = "story_001"
    ) -> str:
        """
        保存生成记录
        
        Args:
            generation_type: 生成类型
            data: 数据
            story_id: 故事ID
            
        Returns:
            文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{generation_type}_{story_id}_{timestamp}.json"
        filepath = self.base_path / filename
        
        record = {
            "generation_type": generation_type,
            "story_id": story_id,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {generation_type}记录已保存 | 文件: {filename}")
        return str(filepath)
    
    def list_generations(
        self,
        story_id: Optional[str] = None,
        generation_type: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        列出生成记录
        
        Args:
            story_id: 故事ID（可选）
            generation_type: 类型（可选）
            
        Returns:
            记录列表
        """
        records = []
        
        for filepath in self.base_path.glob('*.json'):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    record = json.load(f)
                
                match = True
                
                if story_id and record.get('story_id') != story_id:
                    match = False
                
                if generation_type and record.get('generation_type') != generation_type:
                    match = False
                
                if match:
                    records.append({
                        "file": filepath.name,
                        "type": record.get('generation_type'),
                        "story_id": record.get('story_id'),
                        "timestamp": record.get('timestamp'),
                        "path": str(filepath)
                    })
                    
            except Exception as e:
                continue
        
        return sorted(records, key=lambda x: x['timestamp'], reverse=True)
    
    def export_story_package(self, story_id: str) -> Optional[str]:
        """
        导出故事完整包
        
        Args:
            story_id: 故事ID
            
        Returns:
            导出的zip文件路径或None
        """
        try:
            import zipfile
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"story_{story_id}_{timestamp}.zip"
            zip_path = self.base_path / zip_filename
            
            source_dirs = [
                Path("stories") / story_id,
                self.base_path
            ]
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for source_dir in source_dirs:
                    if source_dir.exists():
                        for file_path in source_dir.rglob('*'):
                            if file_path.is_file():
                                arcname = file_path.relative_to(Path('.'))
                                zipf.write(file_path, arcname)
            
            print(f"✅ 故事包已导出 | 文件: {zip_filename}")
            return str(zip_path)
            
        except Exception as e:
            print(f"❌ 导出失败: {e}")
            return None
    
    def cleanup_old_records(self, days: int = 7) -> int:
        """
        清理旧记录
        
        Args:
            days: 保留天数
            
        Returns:
            删除的文件数
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for filepath in self.base_path.glob('*.json'):
            try:
                file_time = datetime.fromtimestamp(filepath.stat().st_mtime)
                if file_time < cutoff_date:
                    filepath.unlink()
                    deleted_count += 1
            except:
                continue
        
        if deleted_count > 0:
            print(f"✅ 已清理{deleted_count}个旧记录")
        
        return deleted_count


if __name__ == "__main__":
    manager = GeneratedData()
    
    test_data = {"test": True, "message": "测试数据"}
    manager.save_generation_record("test", test_data)
    
    records = manager.list_generations()
    
    print("\n📊 测试结果:")
    print(f"共找到 {len(records)} 条记录")
    for r in records[:3]:
        print(f"  - {r['file']}: {r['type']} | {r['timestamp']}")

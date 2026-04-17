#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZIP归档工具模块

功能：
1. 自动打包故事文件
2. 70%+压缩率
3. 目录结构保留
4. 压缩统计
"""

import zipfile
from pathlib import Path
from typing import Optional


class ZipArchiver:
    """
    ZIP归档器
    
    将故事创作结果打包为ZIP文件，便于分享和备份。
    
    Attributes:
        compression_level: 压缩级别 (0-9)
    """
    
    def __init__(self, compression_level: int = 6):
        self.compression_level = compression_level
    
    def create(self, story_id: str, source: Path,
              output_dir: Path = None) -> str:
        """
        创建ZIP归档
        
        Args:
            story_id: 故事ID
            source: 源目录路径
            output_dir: 输出目录（默认stories/）
            
        Returns:
            ZIP文件路径字符串
        """
        if not output_dir:
            output_dir = Path("stories")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        zip_path = output_dir / f"{story_id}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', 
                            zipfile.ZIP_DEFLATED,
                            compresslevel=self.compression_level) as zf:
            
            for file_path in source.rglob('*'):
                if file_path.is_file() and file_path != zip_path:
                    arcname = file_path.relative_to(source.parent)
                    zf.write(file_path, arcname)
        
        # 计算压缩率
        original_size = sum(f.stat().st_size for f in source.rglob('*') if f.is_file())
        compressed_size = zip_path.stat().st_size
        
        if original_size > 0:
            ratio = (1 - compressed_size / original_size) * 100
            
            try:
                from rich.console import Console
                console = Console()
                console.print(
                    f"[green]📦 压缩完成:[/green]\n"
                    f"   原始大小: {original_size/1024:.1f}KB\n"
                    f"   压缩大小: {compressed_size/1024:.1f}KB\n"
                    f"   压缩率: {ratio:.1f}%"
                )
            except ImportError:
                print(f"📦 压缩完成: {original_size/1024:.1f}KB → {compressed_size/1024:.1f}KB ({ratio:.0f}%)")
        
        return str(zip_path)
import sys, tempfile, shutil
sys.path.insert(0, '.')
from pathlib import Path

test_dir = tempfile.mkdtemp()
from wagent.stories_manager import StoryContentParser
parser = StoryContentParser()

chap_path = Path(test_dir) / 'test--branch_01-chap_03.md'
content = '''# 第三章 复杂的章节

> 第3章 | 3000字 | branch_02
> 状态: draft

---

## 场景一：对话测试

"你好，"他说道，"这是一段对话。"

她回答："我明白你的意思。"
'''
with open(chap_path, 'w', encoding='utf-8') as f:
    f.write(content)

chapter = parser.parse_markdown_file(chap_path)
print(f'chapter_num={chapter.chapter_num}')
print(f'branch_id={chapter.branch_id}')
print(f'paragraphs={len(chapter.paragraphs)}')
print(f'dialogues={len(chapter.dialogues)}')

shutil.rmtree(test_dir)

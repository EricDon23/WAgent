import sys, tempfile, os, shutil
sys.path.insert(0, '.')
from pathlib import Path

print('=== 调试最后2个失败项 ===\n')

# 测试1: parse_markdown_chapter
print('1. test_parse_markdown_chapter:')
test_dir = tempfile.mkdtemp()
from wagent.stories_manager import StoryContentParser
parser = StoryContentParser()

chap_path = Path(test_dir) / 'test--branch_01-chap_03.md'
content = """# 第三章 复杂的章节

> 第3章 | 3000字 | branch_02
> 状态: draft

---

## 场景一：对话测试

"你好，"他说道，"这是一段对话。"

她回答："我明白你的意思。"
"""
with open(chap_path, 'w', encoding='utf-8') as f:
    f.write(content)

chapter = parser.parse_markdown_file(chap_path)
if chapter:
    print(f'   chapter_num={chapter.chapter_num} (期望3)')
    print(f'   branch_id={chapter.branch_id} (期望branch_02)')
    print(f'   paragraphs={len(chapter.paragraphs)} (期望>=1)')
    print(f'   dialogues={len(chapter.dialogues)} (期望>=2)')
    print(f'   sections={len(chapter.sections)} (期望>=1)')

    # 检查断言
    try:
        assert chapter.chapter_num == 3, f"chapter_num失败: {chapter.chapter_num}"
        print('   ✅ chapter_num通过')
    except AssertionError as e:
        print(f'   ❌ chapter_num失败: {e}')

    try:
        assert chapter.branch_id == "branch_02", f"branch_id失败: {chapter.branch_id}"
        print('   ✅ branch_id通过')
    except AssertionError as e:
        print(f'   ❌ branch_id失败: {e}')

else:
    print('   ❌ 返回None')
shutil.rmtree(test_dir)

# 测试2: error_summary_generation
print('\n2. test_error_summary_generation:')
test_dir2 = tempfile.mkdtemp()
log_file = Path(test_dir2) / "test_errors.log"
from wagent.stories_manager import StoryErrorHandler, ErrorSeverity
handler = StoryErrorHandler(log_file=str(log_file))

for i in range(10):
    handler.log_error(
        severity=ErrorSeverity.ERROR,
        error_type=f'TYPE_{i % 3}',
        message=f'错误消息 {i}'
    )

summary = handler.get_error_summary()
print(f'   total_errors={summary["total_errors"]} (期望10)')
print(f'   by_severity存在: {"by_severity" in summary}')
print(f'   by_type存在: {"by_type" in summary}')
print(f'   resolved={summary["resolved"]} (>0)')

try:
    assert summary['total_errors'] == 10
    print('   ✅ total_errors通过')
except Exception as e:
    print(f'   ❌ 失败: {e}')

# 清理
handler.logger.handlers.clear()
import time
time.sleep(0.1)
shutil.rmtree(test_dir2, ignore_errors=True)

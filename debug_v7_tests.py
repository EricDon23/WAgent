import sys, tempfile, os, shutil
sys.path.insert(0, '.')
from pathlib import Path

print('=== 调试测试失败项 ===\n')

# 测试1: scan_caching_mechanism
print('1. test_scan_caching_mechanism:')
test_dir = tempfile.mkdtemp()
from wagent.stories_manager import StoryScanner
scanner = StoryScanner(base_dir=test_dir, use_cache=False)

story = Path(test_dir) / 'story_20260417_120000'
story.mkdir()
(story / '_story_node.json').write_text('{"story_id":"s","title":"t"}', encoding='utf-8')

result1 = scanner.scan(force_refresh=True)
result2 = scanner.scan()
print(f'   cache_hit: {result2.cache_hit}')
shutil.rmtree(test_dir)

# 测试2: parse_error_handling
print('\n2. test_parse_error_handling:')
test_dir2 = tempfile.mkdtemp()
from wagent.stories_manager import StoryContentParser
parser = StoryContentParser()

bad_file = Path(test_dir2) / 'corrupted.json'
with open(bad_file, 'wb') as f:
    f.write(b'\x80\x81\x82\x83 invalid')

result = parser.parse_story_node(bad_file)
print(f'   返回值: {result}')
stats = parser.get_parse_statistics()
print(f'   failed: {stats["failed"]}')
shutil.rmtree(test_dir2)

# 测试3: parse_markdown_chapter
print('\n3. test_parse_markdown_chapter:')
test_dir3 = tempfile.mkdtemp()
chap_path = Path(test_dir3) / 'test--branch_01-chap_03.md'
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
    print(f'   ✅ 成功: chap={chapter.chapter_num}, branch={chapter.branch_id}')
    print(f'      paragraphs={len(chapter.paragraphs)}, dialogues={len(chapter.dialogues)}')
else:
    print('   ❌ 失败')
shutil.rmtree(test_dir3)

# 测试4: ErrorHandler (Windows文件锁问题)
print('\n4. test_auto_recovery_mechanism (Windows锁):')
try:
    log_file = Path(tempfile.mkdtemp()) / "test_errors.log"
    from wagent.stories_manager import StoryErrorHandler, ErrorSeverity
    handler = StoryErrorHandler(log_file=str(log_file))

    record = handler.log_error(
        severity=ErrorSeverity.ERROR,
        error_type='FILE_NOT_FOUND',
        message='文件不存在',
        file_path='/nonexistent/file.txt'
    )
    print(f'   resolved={record.resolved}, resolution={record.resolution}')

    # 尝试清理
    try:
        if log_file.parent.exists():
            shutil.rmtree(str(log_file.parent), ignore_errors=True)
            print('   清理成功')
    except Exception as e:
        print(f'   清理失败(预期): {type(e).__name__}')

except Exception as e:
    print(f'   异常: {e}')

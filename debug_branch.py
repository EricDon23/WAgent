import sys, tempfile, shutil, re
sys.path.insert(0, '.')
from pathlib import Path

test_dir = tempfile.mkdtemp()

chap_path = Path(test_dir) / 'test--branch_01-chap_03.md'
content = """# 第三章 复杂的章节

> 第3章 | 3000字 | branch_02
> 状态: draft

---

## 场景一：对话测试
"""
with open(chap_path, 'w', encoding='utf-8') as f:
    f.write(content)

# 模拟parse_markdown_file逻辑
filename = chap_path.stem
print(f"filename: {filename}")

match = re.search(r'branch_(\d+)-chap_(\d+)', filename)
if match:
    print(f"文件名匹配: branch_{match.group(1)}")
    branch_id = f"branch_{match.group(1)}"
else:
    print("文件名未匹配")
    branch_id = ""

# 检查内容中的每一行
for i, line in enumerate(content.split('\n')[:10]):
    print(f"Line {i}: '{line}' | startswith('>'): {line.startswith('>')}")

    if line.startswith('>'):
        branch_match = re.search(r'branch_(\d+)', line)
        if branch_match:
            new_branch = f"branch_{branch_match.group(1)}"
            print(f"  → 找到branch: {new_branch} (覆盖 {branch_id})")
            branch_id = new_branch

print(f"\n最终branch_id: {branch_id}")

shutil.rmtree(test_dir)

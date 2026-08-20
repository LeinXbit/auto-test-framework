---
name: "code-comment-style"
description: "Allows Chinese characters in comments but forbids Chinese punctuation. Also forbids decorative separators (===, ---, ***) in # comment lines. Invoke whenever generating or modifying any code that contains comments."
---

# Code Comment Style

This skill enforces two mandatory rules for all code comments in this project.

## Rule 1: Chinese Characters Allowed, Chinese Punctuation Forbidden

Comment text (docstrings, block comments, inline comments) MAY use Chinese characters (汉字), but MUST NOT contain Chinese punctuation marks.

### Forbidden Chinese Punctuation

The following (and similar) Chinese punctuation marks are forbidden in comments:

| Type | Forbidden chars |
|------|-----------------|
| Comma | ， |
| Period / dot | 。 |
| Colon | ： |
| Semicolon | ； |
| Exclamation | ！ |
| Question | ？ |
| Enumeration | 、 |
| Brackets | （ ） 【 】 ｛ ｝ |
| Quotes | " " ' ' 「 」 『 』 |
| Ellipsis | … |
| Dash | — —— |
| Slash | ／ |
| Tilde | ～ |
| Middle dot | · |

### Why
- Chinese punctuation uses different codepoints and widths than ASCII ones, which breaks alignment, search, and auto-formatting.
- Mixing ASCII and Chinese punctuation is visually noisy and error-prone (e.g. `：` vs `:`).
- Replace with the corresponding ASCII punctuation: `, . : ; ! ? () [] {} " '` etc.

### Examples

BAD:
```python
# 获取验证码：返回 dict（含 captchaId, picPath）
def get_captcha():
    """GVA 鉴权模块接口封装——验证码相关。"""
```

GOOD:
```python
# 获取验证码: 返回 dict (含 captchaId, picPath)
def get_captcha():
    """GVA 鉴权模块接口封装 - 验证码相关."""
```

BAD:
```yaml
# gin-vue-admin 本地真实环境配置
# 敏感配置(数据库密码、管理员密码)不落此文件!
```
(the `!` is ASCII but the content mixes Chinese punctuation - check each char)

GOOD:
```yaml
# gin-vue-admin 本地真实环境配置
# 敏感配置(数据库密码, 管理员密码) 不落此文件
```

### Rule of Thumb
- Chinese characters: OK
- ASCII punctuation: OK (use ASCII equivalents instead of Chinese ones)
- Chinese punctuation: NOT OK

## Rule 2: No Decorative Separators in `#` Comments

Comment lines starting with `#` MUST NOT use decorative separator characters such as `===`, `---`, `***`, `~~~`, `###`, or any repeated punctuation used purely as visual dividers.

### Why
- Adds noise, not signal.
- Breaks when reformatters/IDEs touch the file.
- A blank line is sufficient for visual separation.

### Examples

BAD:
```python
# ====== Session-level fixtures ======
# -------------------------------------
# NOTE: do not modify below
```

BAD:
```python
# ============================================================
# Following files should be uploaded, do not ignore here:
#   - .swagger_doc.json
#   - pytest.ini
# ============================================================
```

GOOD:
```python
# Session-level fixtures

# NOTE: do not modify below
```

GOOD:
```python
# Following files should be uploaded, do not ignore here:
#   - .swagger_doc.json
#   - pytest.ini
```

### Allowed
- A single `#` followed by a space and a normal sentence is always fine.
- Markdown-style content inside comments (e.g. `- item`, `key: value`) is fine as long as it is not a decorative divider.
- Trailing inline separators inside a real comment sentence (e.g. `# see also: section A === section B`) are not what this rule targets; this rule targets pure decoration lines.

## Scope
Applies to every file type with comments: `.py`, `.yaml`, `.yml`, `.ini`, `.cfg`, `.toml`, `Dockerfile`, `Jenkinsfile`, shell scripts, etc.

## How to Apply

When generating or modifying any code in this project:

1. Scan every comment you are about to write or touch.
2. If a comment contains Chinese punctuation, replace it with the ASCII equivalent (or remove if redundant).
3. If a `#` comment line is purely decorative separators (`===`, `---`, `***`, etc.), delete it; replace with a single blank line if visual separation is still needed.
4. When editing an existing file, also clean up the comments you touch in the same edit (do not leave half-cleaned blocks).
5. Do NOT proactively rewrite comments in files you are not otherwise modifying.

## Quick Self-Check

Before finalizing any code change, ask:
- Are all my new/edited comments free of Chinese punctuation?
- Did I remove any `===`/`---`/`***` decoration in the lines I touched?

If both answers are yes, the change conforms to this skill.

---
name: python3-test
description: Use when working with python3-test
---

# Python3-Test Skill

Use when working with python3-test, generated from official documentation.

## When to Use This Skill

This skill should be triggered when:
- Working with python3-test
- Asking about python3-test features or APIs
- Implementing python3-test solutions
- Debugging python3-test code
- Learning python3-test best practices

## Quick Reference

### Common Patterns

**Pattern 1:** For convenience, this interface is implemented in the sys

```
sys.remote_exec()
```

**Pattern 2:** The interpreter now provides helpful suggestions when it detects typos in Python keywords

```
>>> whille True:
...     pass
Traceback (most recent call last):
  File "<stdin>", line 1
    whille True:
    ^^^^^^
SyntaxError: invalid syntax. Did you mean 'while'?
```

**Pattern 3:** The except and except* expressions now allow brackets to be omitted when there are multiple exception types and the as clause is not used

```
except
```

**Pattern 4:** Add several new MIME types based on RFCs and common usage:

```
application/vnd.ms-fontobject
```

## Reference Files

This skill includes comprehensive documentation in `references/`:

- **3.md** - 3 documentation

Use `view` to read specific reference files when detailed information is needed.

## Working with This Skill

### For Beginners
Start with the getting_started or tutorials reference files for foundational concepts.

### For Specific Features
Use the appropriate category reference file (api, guides, etc.) for detailed information.

### For Code Examples
The quick reference section above contains common patterns extracted from the official docs.

## Resources

### references/
Organized documentation extracted from official sources. These files contain:
- Detailed explanations
- Code examples with language annotations
- Links to original documentation
- Table of contents for quick navigation

### scripts/
Add helper scripts here for common automation tasks.

### assets/
Add templates, boilerplate, or example projects here.

## Notes

- This skill was automatically generated from official documentation
- Reference files preserve the structure and examples from source docs
- Code examples include language detection for better syntax highlighting
- Quick reference patterns are extracted from common usage examples in the docs

## Updating

To refresh this skill with updated documentation:
1. Re-run the scraper with the same configuration
2. The skill will be rebuilt with the latest information

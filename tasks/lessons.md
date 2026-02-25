# Lessons Learned

> Claude Code tự cập nhật file này sau mỗi correction từ Boss.
> **ĐẦU MỖI SESSION**: Đọc "Active Rules" trước, rồi scan phần lessons nếu cần.

---

## Active Rules (Top 5)

> 5 rules quan trọng nhất hiện tại. Cập nhật khi có lesson mới quan trọng hơn.

| # | Rule | Từ lesson |
|---|------|-----------|
| 1 | _(sẽ tự cập nhật sau correction đầu tiên)_ | — |
| 2 | | — |
| 3 | | — |
| 4 | | — |
| 5 | | — |

---

## Khi nào thêm lesson

1. **Boss sửa lỗi** → thêm lesson ngay
2. **PR review có feedback** → thêm lesson
3. **CI fail do lỗi lặp lại** → thêm lesson
4. **Tự phát hiện pattern sai** → thêm lesson

## Format

```
## [YYYY-MM-DD] 🔴|🟡|🟢 Category: Short title
**Mistake**: Mô tả cụ thể lỗi đã mắc
**Rule**: Quy tắc để không lặp lại
**Example**: Ví dụ minh họa (nếu có)
```

## Severity

- 🔴 **Critical** — Gây bug production, mất data, deploy fail
- 🟡 **Warning** — Gây delay, code xấu, phải re-do
- 🟢 **Note** — Cải thiện nhỏ, style, preference

## Categories

`Code` | `Architecture` | `Process` | `Communication` | `Tool` | `Deploy`

## Archive

- Lesson tuân thủ **10+ lần liên tiếp** → chuyển `tasks/lessons-archive.md`
- Giữ file gọn — tối đa ~30 lessons active
- Khi archive: `<!-- Archived: [date] Category: Title -->`

---

<!-- Lessons start here -->

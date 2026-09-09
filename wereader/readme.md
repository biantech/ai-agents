# WeRead book export tools

## Download another book

Usually you only need to change `--book-url` and `--output-dir`. Replace
`NEW_BOOK_ID` with the ID from the new WeRead reader URL.

```bash
cd /Users/bianjq/github/ai-agents/wereader

python3 export_weread_book.py \
  --book-url "https://weread.qq.com/web/reader/NEW_BOOK_ID" \
  --from-start \
  --max-pages 1000 \
  --login-wait-seconds 90 \
  --render-wait-seconds 120 \
  --output-dir "/Users/bianjq/work/activity/new_book"
```

The export creates `book.md`, `page_*.txt`, `page_*.html`, and optionally PNG
files in the output directory. Use a different output directory for each book
to avoid overwriting previous results.

The default browser profile is:

```text
/Users/bianjq/work/activity/weread_browser_profile
```

It stores the existing login session. To use a separate login profile, add:

```bash
--profile-dir "/Users/bianjq/work/activity/new_book_browser_profile"
```

If the book requires login, complete login in the opened browser during the
configured login wait period.

## Generate LRC files

Use the generated Markdown book as input:

```bash
python3 book_to_lrc.py \
  "/Users/bianjq/work/activity/new_book/book.md" \
  --output-dir "/Users/bianjq/work/activity/new_book/lrc" \
  --intro-seconds 47 \
  --chapter-duration "听力口语关键句=17:17"
```

Repeat `--chapter-duration` for each chapter with a known MP3 duration. Both
`MM:SS` and `HH:MM:SS` formats are supported. The command generates regular
`.lrc` files and companion `_zh.lrc` files containing `【点睛】` and `【译文】`.

## Adjust LRC timestamps

```bash
python3 adjust_lrc_time.py \
  "/Users/bianjq/work/activity/new_book/lrc/听力口语关键句.lrc" \
  10 \
  1500
```

This shifts the selected sentence and all following timestamp lines by the
specified milliseconds. Positive values delay timestamps; negative values move
them earlier. By default a new `*_adjusted.lrc` file is created. Use
`--in-place` to overwrite the source file.

# Export your data

If you want a copy of your habit history to back it up or open it in a spreadsheet, you can export it.

## Steps

1. Open **Settings**.
2. Tap **Export data**.
3. Choose a format.
4. Tap **Export**.

Tally downloads a file with every check-in you've made. The CSV export is UTF-8 with a BOM and uses ISO 8601 timestamps in UTC, so it's easily parsed by any ETL pipeline. You can also choose NDJSON if you're piping it into jq.

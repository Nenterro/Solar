import db

d = db.get_combined_daily_total('2026-08-07', 'all')
print('Combined daily total for today:', d)

m = db.query_daily_totals_for_month('2026-08', 'all')
print('Monthly daily totals:', m)

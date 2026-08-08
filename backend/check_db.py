import sqlite3, json
c = sqlite3.connect('/home/huzaifa/Docker/solar-new/backend/solar.db')
c.row_factory = sqlite3.Row
print('--- daily_totals ---')
rows = c.execute('SELECT * FROM daily_totals WHERE date = "2026-08-06"').fetchall()
print(json.dumps([dict(r) for r in rows], indent=2))

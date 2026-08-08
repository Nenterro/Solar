from serial_reader import serial_reader
import db

totals = serial_reader.poll_daily_totals()
print('Lifetime totals polled:', totals)
db.update_lifetime_totals_and_calculate_daily(totals)

res = db.query_daily_totals_for_day('2026-08-07', 'all')
print('Daily totals calculated for today:', res)

import datetime as dt
import unittest
import rf_monitor as m
from zoneinfo import ZoneInfo

class ScheduleTests(unittest.TestCase):
    def setUp(self):
        m.LOCAL_TIMEZONE = ZoneInfo('America/New_York')
    def test_daily_boundaries(self):
        for date in ('2026-01-12', '2026-07-12', '2026-10-25'):
            for clock, enabled in (('07:29:59',False),('07:30:00',True),
                                   ('07:59:59',True),('08:00:00',False),
                                   ('19:29:59',False),('19:30:00',True),
                                   ('19:59:59',True),('20:00:00',False)):
                now=dt.datetime.fromisoformat(date+'T'+clock).replace(tzinfo=m.LOCAL_TIMEZONE)
                with self.subTest(date=date,clock=clock):
                    self.assertEqual(m.channel_enabled(m.LOCATION_REPEATER_OUTPUT_HZ,now),enabled)
                    for frequency in m.CHANNELS:
                        self.assertTrue(m.channel_enabled(frequency,now))
    def test_dst_utc_conversion(self):
        for stamp in ('2026-01-12T12:30:00+00:00','2026-07-12T11:30:00+00:00'):
            self.assertTrue(m.downlink_window_open(dt.datetime.fromisoformat(stamp)))
    def test_separate_squelches(self):
        args=m.build_parser().parse_args(['pmr'])
        self.assertEqual((args.squelch,args.repeater_squelch,args.downlink_squelch),(35,150,150))

if __name__=='__main__': unittest.main()

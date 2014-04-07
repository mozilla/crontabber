import datetime
from crontabber.base import BaseCronApp


class FooCronApp(BaseCronApp):
    app_name = 'foo'

    def run(self):
        with open(self.app_name + '.log', 'a') as f:
            f.write('Now is %s\n' % datetime.datetime.now())

import datetime
from crontabber.base import BaseCronApp


class FooCronApp(BaseCronApp):
    app_name = 'foo'

    def run(self):
        # from time import sleep
        # print "Starting to sleep..."
        # sleep(60)
        # print "Done sleepin."
        with open(self.app_name + '.log', 'a') as f:
            f.write('Now is %s\n' % datetime.datetime.now())

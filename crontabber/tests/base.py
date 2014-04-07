# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import datetime
import json
import os
import shutil
import tempfile
import unittest
from collections import Sequence, Mapping, defaultdict

import mock
import psycopg2
from psycopg2.extensions import TRANSACTION_STATUS_IDLE
from nose.plugins.attrib import attr
from nose.tools import eq_

import configman

from crontabber import app

DATABASE_HOST = os.environ.get('DATABASE_HOST', 'localhost')
DATABASE_NAME = os.environ.get('DATABASE_NAME', 'test_crontabber')
DATABASE_USERNAME = os.environ.get('DATABASE_USERNAME', '')
DATABASE_PASSWORD = os.environ.get('DATABASE_PASSWORD', '')


DSN = {
    "crontabber.database_hostname": DATABASE_HOST,
    "crontabber.database_name": DATABASE_NAME,
    "crontabber.database_username": DATABASE_USERNAME,
    "crontabber.database_password": DATABASE_PASSWORD
}


class TestCaseBase(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.isdir(self.tempdir):
            shutil.rmtree(self.tempdir)

    def _setup_config_manager(self, jobs_string, extra_value_source=None):
        """setup and return a configman.ConfigurationManager and a the crontabber
        json file.
            jobs_string - a formatted string list services to be offered
            config - a string representing a config file OR a mapping of
                     key/value pairs to be used to override config defaults or
                     a list of any of the previous
            extra_value_source - supplemental values required by a service

        """
        mock_logging = mock.Mock()
        required_config = app.CronTabber.get_required_config()
        #required_config.namespace('logging')
        required_config.add_option('logger', default=mock_logging)

        # json_file = os.path.join(self.tempdir, 'test.json')

        value_source = [
            configman.ConfigFileFutureProxy,
            configman.environment,
            {
                'logger': mock_logging,
                'crontabber.jobs': jobs_string,
                # 'crontabber.database_file': json_file,
                'admin.strict': True,
            },
        #    DSN,
            extra_value_source,
        ]

        if extra_value_source is None:
            pass
        elif isinstance(extra_value_source, basestring):
            value_source.append(extra_value_source)
        elif isinstance(extra_value_source, Sequence):
            value_source.extend(extra_value_source)
        elif isinstance(extra_value_source, Mapping):
            value_source.append(extra_value_source)

        config_manager = configman.ConfigurationManager(
            [required_config],
            # values_source_list=[configman.environment],
            values_source_list=value_source,
            app_name='test-crontabber',
            app_description=__doc__,
            # argv_source=[]
        )
        return config_manager

    def _wind_clock(self, state, days=0, hours=0, seconds=0):
        # note that 'hours' and 'seconds' can be negative numbers
        if days:
            hours += days * 24
        if hours:
            seconds += hours * 60 * 60

        ## modify ALL last_run and next_run to pretend time has changed

        def _wind(data):
            for key, value in data.items():
                if isinstance(value, dict):
                    _wind(value)
                else:
                    if isinstance(value, datetime.datetime):
                        data[key] = value - datetime.timedelta(seconds=seconds)

        _wind(state)
        return state


@attr(integration='postgres')
class IntegrationTestCaseBase(TestCaseBase):
    """Useful class for running integration tests related to crontabber apps
    since this class takes care of setting up a psycopg connection and it
    makes sure the `crontabber` table is emptied.
    """

    def get_standard_config(self):
        config_manager = configman.ConfigurationManager(
            # [self.required_config],
            [app.CronTabber.get_required_config()],
            values_source_list=[
                configman.ConfigFileFutureProxy,
                configman.environment,
            ],
            # app_name='crontabber',
            # app_name=app.CronTabber.app_name,
            app_name='test-crontabber',
            app_description=__doc__,
            # argv_source=[]
        )

        with config_manager.context() as config:
            config.crontabber.logger = mock.Mock()
            return config

    def setUp(self):
        super(IntegrationTestCaseBase, self).setUp()
        self.config = self.get_standard_config()

        dsn = (
            'host=%(database_hostname)s '
            'dbname=%(database_name)s '
            'user=%(database_username)s '
            'password=%(database_password)s' % self.config.crontabber
        )
        if 'dbname=test' not in dsn:
            raise ValueError(
                'test database must be called test_ something or '
                'else there is a risk you might be testing against a '
                'real database'
            )
        self.conn = psycopg2.connect(dsn)
        self._truncate()

    def _truncate(self):
        cursor = self.conn.cursor()
        self.conn.cursor().execute("""
            TRUNCATE crontabber, crontabber_log CASCADE;
        """)
        self.conn.commit()

    def tearDown(self):
        super(IntegrationTestCaseBase, self).tearDown()
        self._truncate()

    def assertAlmostEqual(self, val1, val2):
        if (
            isinstance(val1, datetime.datetime) and
            isinstance(val2, datetime.datetime)
        ):
            # if there difference is just in the microseconds, they're
            # sufficiently equal
            return not abs(val1 - val2).seconds
        eq_(val1, val2)

    def _load_structure(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                app_name,
                next_run,
                first_run,
                last_run,
                last_success,
                error_count,
                depends_on,
                last_error
            FROM crontabber;
        """)
        columns = (
            'app_name', 'next_run', 'first_run', 'last_run', 'last_success',
            'error_count', 'depends_on', 'last_error'
        )
        structure = {}
        for record in cursor.fetchall():
            row = dict(zip(columns, record))
            last_error = row.pop('last_error')
            if isinstance(last_error, basestring):
                last_error = json.loads(last_error)
            row['last_error'] = last_error
            structure[row.pop('app_name')] = row
        return structure

    def _load_logs(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                app_name,
                log_time,
                duration,
                success,
                exc_type,
                exc_value,
                exc_traceback
            FROM crontabber_log
            ORDER BY log_time;
        """)
        columns = (
            'app_name', 'log_time', 'duration', 'success',
            'exc_type', 'exc_value', 'exc_traceback'
        )
        logs = defaultdict(list)
        for record in cursor.fetchall():
            row = dict(zip(columns, record))
            logs[row.pop('app_name')].append(row)
        return logs

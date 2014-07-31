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
from nose.plugins.attrib import attr
from nose.tools import eq_

import configman
from configman.dotdict import DotDictWithAcquisition

from crontabber import app
from crontabber.generic_app import environment

class TestCaseBase(unittest.TestCase):

    def shortDescription(self):
        return None

    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.isdir(self.tempdir):
            shutil.rmtree(self.tempdir)

    def _setup_config_manager(self, jobs_string, extra_value_source=None):
        """setup and return a configman.ConfigurationManager and a the
        crontabber json file.
            jobs_string - a formatted string list services to be offered
            config - a string representing a config file OR a mapping of
                     key/value pairs to be used to override config defaults or
                     a list of any of the previous
            extra_value_source - supplemental values required by a service

        """
        mock_logging = mock.Mock()
        required_config = app.CronTabber.get_required_config()
        required_config.add_option('logger', default=mock_logging)

        value_source = [
            configman.ConfigFileFutureProxy,
            environment,
            {
                'logger': mock_logging,
                'crontabber.jobs': jobs_string,
                'admin.strict': False,
            },
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
            values_source_list=value_source,
            app_name='test-crontabber',
            app_description=__doc__,
        )
        return config_manager

    def _wind_clock(self, state, days=0, hours=0, seconds=0):
        # note that 'hours' and 'seconds' can be negative numbers
        if days:
            hours += days * 24
        if hours:
            seconds += hours * 60 * 60

        # modify ALL last_run and next_run to pretend time has changed

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
            [app.CronTabber.get_required_config(),
             app.JobStateDatabase.get_required_config()],
            values_source_list=[
                configman.ConfigFileFutureProxy,
                environment,
            ],
            app_name='test-crontabber',
            app_description=__doc__,
        )

        config = config_manager.get_config()
        config.crontabber.logger = mock.Mock()
        return config

    def setUp(self):
        super(IntegrationTestCaseBase, self).setUp()
        self.config = self.get_standard_config()

        db_connection_factory = self.config.crontabber.database_class(
            self.config.crontabber
        )
        self.conn = db_connection_factory.connection()
        cursor = self.conn.cursor()
        cursor.execute('SHOW timezone;')
        try:
            failed = True
            tz, = cursor.fetchone()
            if tz != 'UTC':
                cursor.execute("""
                   ALTER DATABASE %(database_name)s SET TIMEZONE TO UTC;
                """ % self.config.crontabber)
            failed = False
        finally:
            failed and self.conn.rollback() or self.conn.commit()

        # instanciate one of these to make sure the tables are created
        app.JobStateDatabase(self.config.crontabber)

    def _truncate(self):
        self.conn.cursor().execute("""
            TRUNCATE crontabber, crontabber_log CASCADE;
        """)
        self.conn.commit()

    def tearDown(self):
        super(IntegrationTestCaseBase, self).tearDown()
        self._truncate()
        self.conn.close()

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
                last_error,
                ongoing
            FROM crontabber;
        """)
        columns = (
            'app_name', 'next_run', 'first_run', 'last_run', 'last_success',
            'error_count', 'depends_on', 'last_error', 'ongoing'
        )
        structure = {}
        try:
            for record in cursor.fetchall():
                row = dict(zip(columns, record))
                last_error = row.pop('last_error')
                if isinstance(last_error, basestring):
                    last_error = json.loads(last_error)
                row['last_error'] = last_error
                structure[row.pop('app_name')] = row
        finally:
            self.conn.commit()
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
        try:
            for record in cursor.fetchall():
                row = dict(zip(columns, record))
                logs[row.pop('app_name')].append(row)
        finally:
            self.conn.commit()
        return logs

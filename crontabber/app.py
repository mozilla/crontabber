#!/usr/bin/env python
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.


"""
CronTabber is a configman app for executing cron jobs.
"""
import re
import datetime
import inspect
import json
import sys
import time
import traceback
from functools import partial

from dbapi2_util import (
    single_value_sql,
    SQLDidNotReturnSingleValue,
    execute_query_iter,
    execute_query_fetchall,
    single_row_sql,
    SQLDidNotReturnSingleRow,
    execute_no_results,
)

from generic_app import App, main
from datetimeutil import utc_now, timesince
from base import (
    convert_frequency,
    FrequencyDefinitionError,
    reorder_dag
)

try:
    import raven
except ImportError:
    raven = None

from configman import Namespace, RequiredConfig
from configman.converters import class_converter, CannotConvertError
from crontabber import __version__


CREATE_CRONTABBER_SQL = """
    CREATE TABLE crontabber (
        app_name text NOT NULL,
        next_run timestamp with time zone,
        first_run timestamp with time zone,
        last_run timestamp with time zone,
        last_success timestamp with time zone,
        ongoing timestamp with time zone,
        error_count integer DEFAULT 0,
        depends_on text[],
        last_error json
    );
"""

CREATE_CRONTABBER_LOG_SQL = """
    CREATE TABLE crontabber_log (
        id SERIAL NOT NULL,
        app_name text NOT NULL,
        log_time timestamp with time zone DEFAULT now() NOT NULL,
        duration interval,
        success timestamp with time zone,
        exc_type text,
        exc_value text,
        exc_traceback text
    );
"""


# a method decorator that indicates that the method defines a single transacton
# on a database connection.  It invokes the method using the instance's
# transaction object, automatically passing in the appropriate database
# connection.  Any abnormal exit from the method will result in a 'rollback'
# any normal exit will result in a 'commit'
def database_transaction(transaction_object_name='transaction_executor'):
    def transaction_decorator(method):
        def _do_transaction(self, *args, **kwargs):
            x = getattr(self, transaction_object_name)(
                partial(method, self),
                *args,
                **kwargs
            )
            return x
        return _do_transaction
    return transaction_decorator


class JobNotFoundError(Exception):
    pass


class TimeDefinitionError(Exception):
    pass


class JobDescriptionError(Exception):
    pass


class BrokenJSONError(ValueError):
    pass


_marker = object()


class JobStateDatabase(RequiredConfig):
    required_config = Namespace()
    required_config.add_option(
        'database_class',
        default='crontabber.connection_factory.ConnectionFactory',
        from_string_converter=class_converter,
        reference_value_from='resource.postgresql'
    )
    required_config.add_option(
        'transaction_executor_class',
        default='crontabber.transaction_executor.TransactionExecutor',
        doc='a class that will execute transactions',
        from_string_converter=class_converter,
        reference_value_from='resource.postgresql'
    )

    def __init__(self, config=None):
        self.config = config

        self.database_connection_factory = config.database_class(config)
        self.transaction_executor = self.config.transaction_executor_class(
            self.config,
            self.database_connection_factory
        )

        found = self.transaction_executor(
            execute_query_fetchall,
            "SELECT relname FROM pg_class "
            "WHERE relname = 'crontabber'"
        )
        if not found:
            self.config.logger.info(
                "Creating crontabber table: crontabber"
            )
            self.transaction_executor(
                execute_no_results,
                CREATE_CRONTABBER_SQL
            )
        else:
            # Check that it has the new `ongoing` column.
            try:
                self.transaction_executor(
                    single_value_sql,
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='crontabber' AND column_name='ongoing'"
                )
            except SQLDidNotReturnSingleValue:
                # So that's why then!
                # We have to do a quick migration.
                self.config.logger.info(
                    "Have to do a migration and add the `ongoing` field"
                )
                self.transaction_executor(
                    execute_no_results,
                    "ALTER TABLE crontabber ADD ongoing TIMESTAMP "
                    "WITH TIME ZONE"
                )

        found = self.transaction_executor(
            execute_query_fetchall,
            "SELECT relname FROM pg_class "
            "WHERE relname = 'crontabber_log'"
        )
        if not found:
            self.config.logger.info(
                "Creating crontabber table: crontabber_log"
            )
            self.transaction_executor(
                execute_no_results,
                CREATE_CRONTABBER_LOG_SQL
            )

    def has_data(self):
        try:
            return bool(self.transaction_executor(
                single_value_sql,
                "SELECT COUNT(*) FROM crontabber"
            ))
        except SQLDidNotReturnSingleValue:
            return False

    def __iter__(self):
        return iter([
            record[0] for record in
            self.transaction_executor(
                execute_query_fetchall,
                "SELECT app_name FROM crontabber"
            )
        ])

    def __contains__(self, key):
        """return True if we have a job by this key"""
        try:
            self.transaction_executor(
                single_value_sql,
                """SELECT app_name
                   FROM crontabber
                   WHERE
                        app_name = %s""",
                (key,)
            )
            return True
        except SQLDidNotReturnSingleValue:
            return False

    def keys(self):
        """return a list of all app_names"""
        keys = []
        for app_name, __ in self.items():
            keys.append(app_name)
        return keys

    def items(self):
        """return all the app_names and their values as tuples"""
        sql = """
            SELECT
                app_name,
                next_run,
                first_run,
                last_run,
                last_success,
                depends_on,
                error_count,
                last_error
            FROM crontabber"""
        columns = (
            'app_name',
            'next_run', 'first_run', 'last_run', 'last_success',
            'depends_on', 'error_count', 'last_error'
        )
        items = []
        for record in self.transaction_executor(execute_query_fetchall, sql):
            row = dict(zip(columns, record))
            if isinstance(row['last_error'], basestring):
                row['last_error'] = json.loads(row['last_error'])
            items.append((row.pop('app_name'), row))
        return items

    def values(self):
        """return a list of all state values"""
        values = []
        for __, data in self.items():
            values.append(data)
        return values

    def __getitem__(self, key):
        """return the job info or raise a KeyError"""
        sql = """
            SELECT
                next_run,
                first_run,
                last_run,
                last_success,
                depends_on,
                error_count,
                last_error,
                ongoing
            FROM crontabber
            WHERE
                app_name = %s"""
        columns = (
            'next_run', 'first_run', 'last_run', 'last_success',
            'depends_on', 'error_count', 'last_error', 'ongoing'
        )
        try:
            record = self.transaction_executor(single_row_sql, sql, (key,))
        except SQLDidNotReturnSingleRow:
            raise KeyError(key)
        row = dict(zip(columns, record))
        if isinstance(row['last_error'], basestring):
            row['last_error'] = json.loads(row['last_error'])
        return row

    @database_transaction()
    def __setitem__(self, connection, key, value):
        class LastErrorEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, type):
                    return repr(obj)
                return json.JSONEncoder.default(self, obj)

        try:
            single_value_sql(
                connection,
                """SELECT app_name
                FROM crontabber
                WHERE
                    app_name = %s""",
                (key,)
            )
            # the key exists, do an update
            next_sql = """
                UPDATE crontabber
                SET
                    next_run = %(next_run)s,
                    first_run = %(first_run)s,
                    last_run = %(last_run)s,
                    last_success = %(last_success)s,
                    depends_on = %(depends_on)s,
                    error_count = %(error_count)s,
                    last_error = %(last_error)s,
                    ongoing = %(ongoing)s
                WHERE
                    app_name = %(app_name)s
            """
        except SQLDidNotReturnSingleValue:
            # the key does not exist, do an insert
            next_sql = """
                INSERT INTO crontabber (
                    app_name,
                    next_run,
                    first_run,
                    last_run,
                    last_success,
                    depends_on,
                    error_count,
                    last_error,
                    ongoing
                ) VALUES (
                    %(app_name)s,
                    %(next_run)s,
                    %(first_run)s,
                    %(last_run)s,
                    %(last_success)s,
                    %(depends_on)s,
                    %(error_count)s,
                    %(last_error)s,
                    %(ongoing)s
                )
            """
        parameters = {
            'app_name': key,
            'next_run': value['next_run'],
            'first_run': value['first_run'],
            'last_run': value['last_run'],
            'last_success': value.get('last_success'),
            'depends_on': value['depends_on'],
            'error_count': value['error_count'],
            'last_error': json.dumps(
                value['last_error'],
                cls=LastErrorEncoder
            ),
            'ongoing': value.get('ongoing'),
        }

        execute_no_results(
            connection,
            next_sql,
            parameters
        )

    @database_transaction()
    def copy(self, connection):
        sql = """SELECT
                app_name,
                next_run,
                first_run,
                last_run,
                last_success,
                depends_on,
                error_count,
                last_error,
                ongoing
            FROM crontabber
        """
        columns = (
            'app_name',
            'next_run', 'first_run', 'last_run', 'last_success',
            'depends_on', 'error_count', 'last_error', 'ongoing'
        )
        all = {}
        for record in execute_query_iter(connection, sql):
            row = dict(zip(columns, record))
            if isinstance(row['last_error'], basestring):
                row['last_error'] = json.loads(row['last_error'])
            all[row.pop('app_name')] = row
        return all

    def update(self, data):
        for key in data:
            self[key] = data[key]

    def get(self, key, default=None):
        """return the item by key or return 'default'"""
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key, default=_marker):
        """remove the item by key
        If not default is specified, raise KeyError if nothing
        could be removed.
        Return 'default' if specified and nothing could be removed
        """
        try:
            popped = self[key]
            del self[key]
            return popped
        except KeyError:
            if default == _marker:
                raise
            return default

    @database_transaction()
    def __delitem__(self, connection, key):
        """remove the item by key or raise KeyError"""
        try:
            # result intentionally ignored
            single_value_sql(
                connection,
                """SELECT app_name
                   FROM crontabber
                   WHERE
                        app_name = %s""",
                (key,)
            )
        except SQLDidNotReturnSingleValue:
            raise KeyError(key)
        # item exists
        execute_no_results(
            connection,
            """DELETE FROM crontabber
               WHERE app_name = %s""",
            (key,)
        )


# -----------------------------------------------------------------------------
def _default_list_splitter(class_list_str):
    return [x.strip() for x in class_list_str.split(',')]


def _default_class_extractor(list_element):
    return list_element


def _default_extra_extractor(list_element):
    raise NotImplementedError()


def classes_in_namespaces_converter_with_compression(
        reference_namespace={},
        template_for_namespace="class-%(name)s",
        list_splitter_fn=_default_list_splitter,
        class_extractor=_default_class_extractor,
        extra_extractor=_default_extra_extractor):
    """
    parameters:
        template_for_namespace - a template for the names of the namespaces
                                 that will contain the classes and their
                                 associated required config options.  There are
                                 two template variables available: %(name)s -
                                 the name of the class to be contained in the
                                 namespace; %(index)d - the sequential index
                                 number of the namespace.
        list_converter - a function that will take the string list of classes
                         and break it up into a sequence if individual elements
        class_extractor - a function that will return the string version of
                          a classname from the result of the list_converter
        extra_extractor - a function that will return a Namespace of options
                          created from any extra information associated with
                          the classes returned by the list_converter function
                              """

    # -------------------------------------------------------------------------
    def class_list_converter(class_list_str):
        """This function becomes the actual converter used by configman to
        take a string and convert it into the nested sequence of Namespaces,
        one for each class in the list.  It does this by creating a proxy
        class stuffed with its own 'required_config' that's dynamically
        generated."""
        if isinstance(class_list_str, basestring):
            class_str_list = list_splitter_fn(class_list_str)
        else:
            raise TypeError('must be derivative of a basestring')

        # =====================================================================
        class InnerClassList(RequiredConfig):
            """This nested class is a proxy list for the classes.  It collects
            all the config requirements for the listed classes and places them
            each into their own Namespace.
            """
            # we're dynamically creating a class here.  The following block of
            # code is actually adding class level attributes to this new class

            # 1st requirement for configman
            required_config = Namespace()

            # to help the programmer know what Namespaces we added
            subordinate_namespace_names = []

            # save the template for future reference
            namespace_template = template_for_namespace

            # for display
            original_input = class_list_str.replace('\n', '\\n')

            # for each class in the class list
            class_list = []
            for namespace_index, class_list_element in enumerate(
                class_str_list
            ):
                try:
                    a_class = class_converter(
                        class_extractor(class_list_element)
                    )
                except CannotConvertError:
                    raise JobNotFoundError(class_list_element)

                class_list.append((a_class.__name__, a_class))
                # figure out the Namespace name
                namespace_name_dict = {
                    'name': a_class.__name__,
                    'index': namespace_index
                }
                namespace_name = template_for_namespace % namespace_name_dict
                subordinate_namespace_names.append(namespace_name)
                # create the new Namespace
                required_config.namespace(namespace_name)
                a_class_namespace = required_config[namespace_name]
                # add options for the 'extra data'
                try:
                    extra_options = extra_extractor(class_list_element)
                    a_class_namespace.update(extra_options)
                except NotImplementedError:
                    pass
                # add options frr the classes required config
                try:
                    for k, v in a_class.get_required_config().iteritems():
                        if k not in reference_namespace:
                            a_class_namespace[k] = v
                except AttributeError:  # a_class has no get_required_config
                    pass

            @classmethod
            def to_str(cls):
                """this method takes this inner class object and turns it back
                into the original string of classnames.  This is used
                primarily as for the output of the 'help' option"""
                return cls.original_input

        return InnerClassList  # result of class_list_converter
    return class_list_converter  # result of classes_in_namespaces_converter


def get_extra_as_options(input_str):
    if '|' not in input_str:
        raise JobDescriptionError('No frequency and/or time defined')
    metadata = input_str.split('|')[1:]
    if len(metadata) == 1:
        if ':' in metadata[0]:
            frequency = '1d'
            time_ = metadata[0]
        else:
            frequency = metadata[0]
            time_ = None
    else:
        frequency, time_ = metadata

    n = Namespace()
    n.add_option(
        'frequency',
        doc='frequency',
        default=frequency,
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True
    )
    n.add_option(
        'time',
        doc='time',
        default=time_,
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True
    )
    return n


def check_time(value):
    """check that it's a value like 03:45 or 1:1"""
    try:
        h, m = value.split(':')
        h = int(h)
        m = int(m)
        if h >= 24 or h < 0:
            raise ValueError
        if m >= 60 or m < 0:
            raise ValueError
    except ValueError:
        raise TimeDefinitionError("Invalid definition of time %r" % value)


def line_splitter(text):
    return [x.strip() for x in re.split('\n|,|;', text.strip())
            if x.strip() and not x.strip().startswith('#')]


def pipe_splitter(text):
    return text.split('|', 1)[0]


class CronTabberBase(RequiredConfig):

    app_name = 'crontabber'
    app_version = __version__
    app_description = __doc__

    required_config = Namespace()
    # the most important option, 'jobs', is defined last
    required_config.namespace('crontabber')

    required_config.crontabber.add_option(
        name='job_state_db_class',
        default=JobStateDatabase,
        doc='Class to load and save the state and runs',
    )

    required_config.crontabber.add_option(
        'jobs',
        default='',
        from_string_converter=classes_in_namespaces_converter_with_compression(
            reference_namespace=Namespace(),
            list_splitter_fn=line_splitter,
            class_extractor=pipe_splitter,
            extra_extractor=get_extra_as_options
        )
    )

    required_config.crontabber.add_option(
        'error_retry_time',
        default=300,
        doc='number of seconds to re-attempt a job that failed'
    )

    # for local use, independent of the JSONAndPostgresJobDatabase
    required_config.crontabber.add_option(
        'database_class',
        default='crontabber.connection_factory.ConnectionFactory',
        from_string_converter=class_converter,
        reference_value_from='resource.postgresql'
    )
    required_config.crontabber.add_option(
        'transaction_executor_class',
        default='crontabber.transaction_executor.TransactionExecutor',
        doc='a class that will execute transactions',
        from_string_converter=class_converter,
        reference_value_from='resource.postgresql'
    )

    required_config.add_option(
        name='job',
        default='',
        doc='Run a specific job',
        short_form='j',
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True,
    )

    required_config.add_option(
        name='list-jobs',
        default=False,
        doc='List all jobs',
        short_form='l',
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True,
    )

    required_config.add_option(
        name='force',
        default=False,
        doc='Force running a job despite dependencies',
        short_form='f',
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True,
    )

    required_config.add_option(
        name='configtest',
        default=False,
        doc='Check that all configured jobs are OK',
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True,
    )

    required_config.add_option(
        name='audit-ghosts',
        default=False,
        doc='Checks if there jobs in the database that is not configured.',
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True,
    )

    required_config.add_option(
        name='reset-job',
        default='',
        doc='Pretend a job has never been run',
        short_form='r',
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True,
    )

    required_config.add_option(
        name='nagios',
        default=False,
        doc='Exits with 0, 1 or 2 with a message on stdout if errors have '
            'happened.',
        short_form='n',
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True,
    )

    required_config.add_option(
        name='version',
        default=False,
        doc='Print current version and exit',
        short_form='v',
        exclude_from_print_conf=True,
        exclude_from_dump_conf=True,
    )

    required_config.namespace('sentry')
    required_config.sentry.add_option(
        'dsn',
        doc='DSN for Sentry via raven',
        default='',
        reference_value_from='secrets.sentry',
    )

    def __init__(self, config):
        super(CronTabberBase, self).__init__(config)
        self.database_connection_factory = \
            self.config.crontabber.database_class(config.crontabber)
        self.transaction_executor = (
            self.config.crontabber.transaction_executor_class(
                config.crontabber,
                self.database_connection_factory
            )
        )

    def main(self):
        if self.config.get('list-jobs'):
            self.list_jobs()
            return 0
        elif self.config.get('nagios'):
            return self.nagios()
        elif self.config.get('version'):
            self.print_version()
            return 0
        elif self.config.get('reset-job'):
            self.reset_job(self.config.get('reset-job'))
            return 0
        elif self.config.get('audit-ghosts'):
            self.audit_ghosts()
            return 0
        elif self.config.get('configtest'):
            if not self.configtest():
                return 1
            else:
                return 0
        if self.config.get('job'):
            self.run_one(self.config['job'], self.config.get('force'))
        else:
            self.run_all()
        return 0

    @staticmethod
    def _reorder_class_list(class_list):
        # class_list looks something like this:
        # [('FooBarJob', <class 'FooBarJob'>),
        #  ('BarJob', <class 'BarJob'>),
        #  ('FooJob', <class 'FooJob'>)]
        return reorder_dag(
            class_list,
            depends_getter=lambda x: getattr(x[1], 'depends_on', None),
            name_getter=lambda x: x[1].app_name
        )

    @property
    def job_state_database(self):
        if not getattr(self, '_job_state_database', None):
            self._job_state_database = (
                self.config.crontabber.job_state_db_class(
                    self.config.crontabber
                )
            )
        return self._job_state_database

    def nagios(self, stream=sys.stdout):
        """
        return 0 (OK) if there are no errors in the state.
        return 1 (WARNING) if a backfill app only has 1 error.
        return 2 (CRITICAL) if a backfill app has > 1 error.
        return 2 (CRITICAL) if a non-backfill app has 1 error.
        """
        warnings = []
        criticals = []
        for class_name, job_class in self.config.crontabber.jobs.class_list:
            if job_class.app_name in self.job_state_database:
                info = self.job_state_database.get(job_class.app_name)
                if not info.get('error_count', 0):
                    continue
                error_count = info['error_count']
                # trouble!
                serialized = (
                    '%s (%s) | %s | %s' %
                    (job_class.app_name,
                     class_name,
                     info['last_error']['type'],
                     info['last_error']['value'])
                )
                if (
                    error_count == 1 and
                    hasattr(job_class, "_is_backfill_app")
                ):
                    # just a warning for now
                    warnings.append(serialized)
                else:
                    # anything worse than that is critical
                    criticals.append(serialized)

        if criticals:
            stream.write('CRITICAL - ')
            stream.write('; '.join(criticals))
            stream.write('\n')
            return 2
        elif warnings:
            stream.write('WARNING - ')
            stream.write('; '.join(warnings))
            stream.write('\n')
            return 1
        stream.write('OK - All systems nominal')
        stream.write('\n')
        return 0

    def print_version(self, stream=sys.stdout):
        stream.write('%s\n' % self.app_version)

    def list_jobs(self, stream=None):
        if not stream:
            stream = sys.stdout
        _fmt = '%Y-%m-%d %H:%M:%S'
        _now = utc_now()
        PAD = 15
        for class_name, job_class in self.config.crontabber.jobs.class_list:
            class_config = self.config.crontabber['class-%s' % class_name]
            freq = class_config.frequency
            if class_config.time:
                freq += ' @ %s' % class_config.time
            class_name = job_class.__module__ + '.' + job_class.__name__
            print >>stream, '=== JOB ' + '=' * 72
            print >>stream, 'Class:'.ljust(PAD), class_name
            print >>stream, 'App name:'.ljust(PAD), job_class.app_name
            print >>stream, 'Frequency:'.ljust(PAD), freq
            try:
                info = self.job_state_database[job_class.app_name]
            except KeyError:
                print >>stream, '*NO PREVIOUS RUN INFO*'
                continue
            if info.get('ongoing'):
                print >>stream, 'Ongoing now!'.ljust(PAD),
                print >>stream, 'Started', '%s ago' % timesince(
                    _now, info.get('ongoing')
                )
            print >>stream, 'Last run:'.ljust(PAD),
            if info['last_run']:
                print >>stream, info['last_run'].strftime(_fmt).ljust(20),
                print >>stream, '(%s ago)' % timesince(info['last_run'], _now)
            else:
                print >>stream, 'none'
            print >>stream, 'Last success:'.ljust(PAD),
            if info.get('last_success'):
                print >>stream, info['last_success'].strftime(_fmt).ljust(20),
                print >>stream, ('(%s ago)' %
                                 timesince(info['last_success'], _now))
            else:
                print >>stream, 'no previous successful run'
            print >>stream, 'Next run:'.ljust(PAD),
            if info['next_run']:
                print >>stream, info['next_run'].strftime(_fmt).ljust(20),
                if _now > info['next_run']:
                    print >>stream, ('(was %s ago)' %
                                     timesince(info['next_run'], _now))
                else:
                    print >>stream, '(in %s)' % timesince(
                        _now,
                        info['next_run']
                    )
            else:
                print >>stream, 'none'
            if info.get('last_error'):
                print >>stream, 'Error!!'.ljust(PAD),
                print >>stream, '(%s times)' % info['error_count']
                print >>stream, 'Traceback (most recent call last):'
                print >>stream, info['last_error']['traceback'],
                print >>stream, '%s:' % info['last_error']['type'],
                print >>stream, info['last_error']['value']
            print >>stream, ''

    def reset_job(self, description):
        """remove the job from the state.
        if means that next time we run, this job will start over from scratch.
        """
        class_list = self.config.crontabber.jobs.class_list
        class_list = self._reorder_class_list(class_list)
        for class_name, job_class in class_list:
            if (
                job_class.app_name == description or
                description == job_class.__module__ + '.' + job_class.__name__
            ):
                if job_class.app_name in self.job_state_database:
                    self.config.logger.info('App reset')
                    self.job_state_database.pop(job_class.app_name)
                else:
                    self.config.logger.warning('App already reset')
                return
        raise JobNotFoundError(description)

    def run_all(self):
        class_list = self.config.crontabber.jobs.class_list
        class_list = self._reorder_class_list(class_list)
        for class_name, job_class in class_list:
            class_config = self.config.crontabber['class-%s' % class_name]
            self._run_one(job_class, class_config)

    def run_one(self, description, force=False):
        # the description in this case is either the app_name or the full
        # module/class reference
        class_list = self.config.crontabber.jobs.class_list
        class_list = self._reorder_class_list(class_list)
        for class_name, job_class in class_list:
            if (
                job_class.app_name == description or
                description == job_class.__module__ + '.' + job_class.__name__
            ):
                class_config = self.config.crontabber['class-%s' % class_name]
                self._run_one(job_class, class_config, force=force)
                return
        raise JobNotFoundError(description)

    def _run_one(self, job_class, config, force=False):
        _debug = self.config.logger.debug
        seconds = convert_frequency(config.frequency)
        time_ = config.time
        if not force:
            if not self.time_to_run(job_class, time_):
                _debug("skipping %r because it's not time to run", job_class)
                return
            ok, dependency_error = self.check_dependencies(job_class)
            if not ok:
                _debug(
                    "skipping %r dependencies aren't met [%s]",
                    job_class, dependency_error
                )
                return

        _debug('about to run %r', job_class)
        app_name = job_class.app_name
        info = self.job_state_database.get(app_name)

        last_success = None
        now = utc_now()
        try:
            t0 = time.time()
            for last_success in self._run_job(job_class, config, info):
                t1 = time.time()
                _debug('successfully ran %r on %s', job_class, last_success)
                self._remember_success(job_class, last_success, t1 - t0)
                # _run_job() returns a generator, so we don't know how
                # many times this will loop. Anyway, we need to reset the
                # 't0' for the next loop if there is one.
                t0 = time.time()
            exc_type = exc_value = exc_tb = None
        except:
            t1 = time.time()
            exc_type, exc_value, exc_tb = sys.exc_info()

            # when debugging tests that mock logging, uncomment this otherwise
            # the exc_info=True doesn't compute and record what the exception
            # was
            #raise

            if self.config.sentry and self.config.sentry.dsn:
                assert raven, "raven not installed"
                try:
                    client = raven.Client(dsn=self.config.sentry.dsn)
                    identifier = client.get_ident(client.captureException())
                    self.config.logger.info(
                        'Error captured in Sentry. Reference: %s' % identifier
                    )
                except Exception:
                    # Blank exceptions like this is evil but a failure to send
                    # the exception to Sentry is much less important than for
                    # crontabber to carry on. This is especially true
                    # considering that raven depends on network I/O.
                    _debug('Failed to capture and send error to Sentry',
                           exc_info=True)

            _debug('error when running %r on %s',
                   job_class, last_success, exc_info=True)
            self._remember_failure(
                job_class,
                t1 - t0,
                exc_type,
                exc_value,
                exc_tb
            )

        finally:
            self._log_run(job_class, seconds, time_, last_success, now,
                          exc_type, exc_value, exc_tb)

    @database_transaction()
    def _remember_success(self, connection, class_, success_date, duration):
        app_name = class_.app_name
        execute_no_results(
            connection,
            """INSERT INTO crontabber_log (
                app_name,
                success,
                duration
            ) VALUES (
                %s,
                %s,
                %s
            )""",
            (app_name, success_date, '%.5f' % duration)
        )

    @database_transaction()
    def _remember_failure(
        self,
        connection,
        class_,
        duration,
        exc_type,
        exc_value,
        exc_tb
    ):
        exc_traceback = ''.join(traceback.format_tb(exc_tb))
        app_name = class_.app_name
        execute_no_results(
            connection,
            """INSERT INTO crontabber_log (
                app_name,
                duration,
                exc_type,
                exc_value,
                exc_traceback
            ) VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            )""",
            (
                app_name,
                '%.5f' % duration,
                repr(exc_type),
                repr(exc_value),
                exc_traceback
            )
        )

    def check_dependencies(self, class_):
        try:
            depends_on = class_.depends_on
        except AttributeError:
            # that's perfectly fine
            return True, None
        if isinstance(depends_on, basestring):
            depends_on = [depends_on]
        for dependency in depends_on:
            try:
                job_info = self.job_state_database[dependency]
            except KeyError:
                # the job this one depends on hasn't been run yet!
                return False, "%r hasn't been run yet" % dependency
            if job_info.get('last_error'):
                # errored last time it ran
                return False, "%r errored last time it ran" % dependency
            if job_info['next_run'] < utc_now():
                # the dependency hasn't recently run
                return False, "%r hasn't recently run" % dependency
        # no reason not to stop this class
        return True, None

    def time_to_run(self, class_, time_):
        """return true if it's time to run the job.
        This is true if there is no previous information about its last run
        or if the last time it ran and set its next_run to a date that is now
        past.
        """
        app_name = class_.app_name
        try:
            info = self.job_state_database[app_name]
        except KeyError:
            if time_:
                h, m = [int(x) for x in time_.split(':')]
                # only run if this hour and minute is < now
                now = utc_now()
                if now.hour > h:
                    return True
                elif now.hour == h and now.minute >= m:
                    return True
                return False
            else:
                # no past information, run now
                return True
        next_run = info['next_run']
        if next_run < utc_now():
            return True
        return False

    def _run_job(self, class_, config, info):
        # here we go!
        instance = class_(config, info)
        self._set_ongoing_job(class_)
        result = instance.main()
        return result

    def _set_ongoing_job(self, class_):
        app_name = class_.app_name
        info = self.job_state_database.get(app_name)
        if info:
            info['ongoing'] = datetime.datetime.utcnow()
        else:
            depends_on = getattr(class_, 'depends_on', [])
            if isinstance(depends_on, basestring):
                depends_on = [depends_on]
            elif not isinstance(depends_on, list):
                depends_on = list(depends_on)
            info = {
                'next_run': None,
                'first_run': None,
                'last_run': None,
                'last_success': None,
                'last_error': {},
                'error_count': 0,
                'depends_on': depends_on,
                'ongoing': datetime.datetime.utcnow()
            }
        self.job_state_database[app_name] = info

    def _log_run(self, class_, seconds, time_, last_success, now,
                 exc_type, exc_value, exc_tb):
        assert inspect.isclass(class_)
        app_name = class_.app_name
        info = self.job_state_database.get(app_name, {})
        depends_on = getattr(class_, 'depends_on', [])
        if isinstance(depends_on, basestring):
            depends_on = [depends_on]
        elif not isinstance(depends_on, list):
            depends_on = list(depends_on)
        info['depends_on'] = depends_on
        if not info.get('first_run'):
            info['first_run'] = now
        info['last_run'] = now
        if last_success:
            info['last_success'] = last_success
        if exc_type:
            # it errored, try very soon again
            info['next_run'] = now + datetime.timedelta(
                seconds=self.config.crontabber.error_retry_time
            )
        else:
            info['next_run'] = now + datetime.timedelta(seconds=seconds)
            if time_:
                h, m = [int(x) for x in time_.split(':')]
                info['next_run'] = info['next_run'].replace(hour=h,
                                                            minute=m,
                                                            second=0,
                                                            microsecond=0)

        if exc_type:
            tb = ''.join(traceback.format_tb(exc_tb))
            info['last_error'] = {
                'type': exc_type,
                'value': str(exc_value),
                'traceback': tb,
            }
            info['error_count'] = info.get('error_count', 0) + 1
        else:
            info['last_error'] = {}
            info['error_count'] = 0

        # Clearly it's not "ongoing" any more when it's here, because
        # being here means the job has finished.
        info['ongoing'] = None

        self.job_state_database[app_name] = info

    def configtest(self):
        """return true if all configured jobs are configured OK"""
        # similar to run_all() but don't actually run them
        failed = 0

        class_list = self.config.crontabber.jobs.class_list
        class_list = self._reorder_class_list(class_list)
        for class_name, __ in class_list:
            class_config = self.config.crontabber['class-%s' % class_name]
            if not self._configtest_one(class_config):
                failed += 1
        return not failed

    def _configtest_one(self, config):
        try:
            seconds = convert_frequency(config.frequency)
            time_ = config.time
            if time_:
                check_time(time_)
                # if less than 1 day, it doesn't make sense to specify hour
                if seconds < 60 * 60 * 24:
                    raise FrequencyDefinitionError(config.time)
            return True

        except (JobNotFoundError,
                JobDescriptionError,
                FrequencyDefinitionError,
                TimeDefinitionError):
            exc_type, exc_value, exc_tb = sys.exc_info()
            print >>sys.stderr, "Error type:", exc_type
            print >>sys.stderr, "Error value:", exc_value
            print >>sys.stderr, ''.join(traceback.format_tb(exc_tb))
            return False

    def audit_ghosts(self):
        """compare the list of configured jobs with the jobs in the state"""
        print_header = True
        for app_name in self._get_ghosts():
            if print_header:
                print_header = False
                print (
                    "Found the following in the state database but not "
                    "available as a configured job:"
                )
            print "\t%s" % (app_name,)

    def _get_ghosts(self):
        class_list = self.config.crontabber.jobs.class_list
        class_list = self._reorder_class_list(class_list)
        configured_app_names = []
        for __, job_class in class_list:
            configured_app_names.append(job_class.app_name)
        state_app_names = self.job_state_database.keys()
        return set(state_app_names) - set(configured_app_names)


class CronTabber(CronTabberBase, App):
    """This class mixes in the CronTabberBase class with the default runnable
    application infrastructure: crontabber.generic_app.App.  Having the
    CronTabberBase decoupled from the App class allows CrontTabber to integrate
    seemlessly into a different system for setting up and running an app.

    One of the primary clients of CronTabber is Socorro. In fact CronTabber
    was spun off from Socorro as an indepentent app.  Initially they had
    identical copies of the App base class.  To allow the two projects to
    evolve indepentenly, the CronTabber App class was separated from the
    CronTabberBase class.  This allows Socorro to declare its own CronTabberApp
    that derives from the Socorro App class instead of the
    crontabber.generic_app.App class"""
    # no new methods are required, the two base classes have everything


def local_main():  # pragma: no cover
    import sys
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if root not in sys.path:
        sys.path.append(root)
    sys.exit(main(CronTabber))


if __name__ == '__main__':  # pragma: no cover
    local_main()

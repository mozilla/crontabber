import unittest

import mock
from nose.tools import eq_, ok_

from configman import ConfigurationManager, Namespace
from configman.dotdict import DotDict

from crontabber.base import BaseCronApp
import crontabber.mixins as ctm

from crontabber.connection_factory import ConnectionFactory
from crontabber.transaction_executor import TransactionExecutor

from crontabber.generic_app import environment


class FakeResourceClass(object):
    pass


class TestCrontabMixins(unittest.TestCase):

    def test_as_backfill_cron_app_simple_success(self):
        @ctm.as_backfill_cron_app
        class Alpha(BaseCronApp):
            pass
        a = Alpha(mock.Mock(), mock.Mock())
        ok_(hasattr(a, 'main'))
        ok_(hasattr(Alpha, 'required_config'))

    def test_as_backfill_cron_app_main_overrides(self):
        @ctm.as_backfill_cron_app
        class Alpha(BaseCronApp):
            def main(self, function, once):
                yield 'yuck'
        config = DotDict()
        config.time = '00:01'
        config.frequency = '1m'
        a = Alpha(config, None)
        ok_(hasattr(a, 'main'))
        with mock.patch('crontabber.base.utc_now') as mocked_utc_now:
            mocked_utc_now.return_value = 'dwight'
            for i in a.main(lambda t: 18):
                eq_(i, 'dwight')

    def test_with_transactional_resource(self):
        @ctm.with_transactional_resource(
            'crontabber.connection_factory.ConnectionFactory',
            'database'
        )
        class Alpha(BaseCronApp):
            pass
        self.assertTrue
        ok_(hasattr(Alpha, "required_config"))
        alpha_required = Alpha.get_required_config()
        ok_(isinstance(alpha_required, Namespace))
        ok_('database' in alpha_required)
        ok_('database_class' in alpha_required.database)
        ok_(
            'database_transaction_executor_class' in alpha_required.database
        )
        cm = ConfigurationManager(
            definition_source=[Alpha.get_required_config(), ],
            values_source_list=[environment],
            argv_source=[],
        )
        config = cm.get_config()
        a = Alpha(config, mock.Mock())
        ok_(hasattr(a, 'database_connection_factory'))
        ok_(isinstance(a.database_connection_factory, ConnectionFactory))
        ok_(hasattr(a, 'database_transaction_executor'))
        ok_(isinstance(a.database_transaction_executor, TransactionExecutor))

    def test_with_resource_connection_as_argument(self):
        @ctm.with_transactional_resource(
            'crontabber.connection_factory.ConnectionFactory',
            'database'
        )
        @ctm.with_resource_connection_as_argument('database')
        class Alpha(BaseCronApp):
            def __init__(self, config):
                self.config = config
        ok_(hasattr(Alpha, '_run_proxy'))

    def test_with_subprocess_mixin(self):
        @ctm.with_transactional_resource(
            'crontabber.connection_factory.ConnectionFactory',
            'database'
        )
        @ctm.with_single_transaction('database')
        @ctm.with_subprocess
        class Alpha(BaseCronApp):
            def __init__(self, config):
                self.config = config
        ok_(hasattr(Alpha, '_run_proxy'))
        ok_(hasattr(Alpha, 'run_process'))

    def test_using_postgres(self):
        @ctm.using_postgres()
        class Alpha(BaseCronApp):
            def __init__(self, config):
                self.config = config
        self.assertTrue
        ok_(hasattr(Alpha, "required_config"))
        alpha_required = Alpha.get_required_config()
        ok_(isinstance(alpha_required, Namespace))
        ok_('database' in alpha_required)
        ok_('database_class' in alpha_required.database)
        ok_(
            'database_transaction_executor_class' in alpha_required.database
        )

    def test_with_postgres_connection_as_argument(self):
        @ctm.using_postgres()
        @ctm.with_postgres_connection_as_argument()
        class Alpha(BaseCronApp):
            def __init__(self, config):
                self.config = config
        ok_(hasattr(Alpha, '_run_proxy'))

    def test_no_over_propagation(self):
        @ctm.using_postgres()
        class Alpha(BaseCronApp):
            required_config = Namespace()
            required_config.add_option('a', default=0)


        @ctm.with_transactional_resource(
            mock.Mock(),
            'queuing'
        )
        class Beta(BaseCronApp):
            required_config = Namespace()
            required_config.add_option('a', default=0)

        ok_('database' in Alpha.get_required_config())
        ok_('queuing' not in Alpha.get_required_config())
        ok_('database' not in Beta.get_required_config())
        ok_('queuing' in Beta.get_required_config())

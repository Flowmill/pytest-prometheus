from prometheus_client import CollectorRegistry, Gauge, push_to_gateway, generate_latest
import logging

def pytest_addoption(parser):
    group = parser.getgroup('terminal reporting')
    group.addoption(
        '--prometheus-pushgateway-url',
        help='Push Gateway URL to send metrics to'
    )
    group.addoption(
        '--prometheus-metric-prefix',
        help='Prefix for all prometheus metrics'
    )
    group.addoption(
        '--prometheus-extra-label',
        action='append',
        help='Extra labels to attach to reported metrics'
    )
    group.addoption(
        '--prometheus-job-name',
        help='Value for the "job" key in exported metrics'
    )

def pytest_configure(config):
    if config.getoption('prometheus_pushgateway_url') and config.getoption('prometheus_metric_prefix'):
        config._prometheus = PrometheusReport(config)
        config.pluginmanager.register(config._prometheus)

def pytest_unconfigure(config):
    prometheus = getattr(config, '_prometheus', None)

    if prometheus:
        del config._prometheus
        config.pluginmanager.unregister(prometheus)


class PrometheusReport:
    def __init__(self, config):
        self.config = config
        self.prefix = config.getoption('prometheus_metric_prefix')
        self.pushgateway_url = config.getoption('prometheus_pushgateway_url')
        self.job_name = config.getoption('prometheus_job_name')
        self.registry = CollectorRegistry()

        self.passed = 0
        self.failed = 0
        self.skipped = 0

        self.extra_labels = {item[0]: item[1] for item in [i.split('=', 1) for i in config.getoption('prometheus_extra_label')]}

    def _make_metric_name(self, name):
        return '{prefix}{name}'.format(
                prefix=self.prefix,
                name=name
        )

    def pytest_runtest_logreport(self, report):
        # https://docs.pytest.org/en/latest/reference.html#_pytest.runner.TestReport.when
        # 'call' is the phase when the test is being ran
        if report.when == 'call':

            metric_value = 0

            if report.outcome == 'passed':
                self.passed += 1
                metric_value = 1
            elif report.outcome == 'skipped':
                self.skipped += 1
            elif report.outcome == 'failed':
                self.failed += 1


            funcname = report.location[2]
            name = self._make_metric_name(funcname)
            logging.debug("Pushing metric {name}".format(name=name))
            metric = Gauge(name, report.nodeid, self.extra_labels.keys(), registry=self.registry)
            # Wait WTF why is this a label? Come back to this Thomas
            metric.labels(**self.extra_labels).set(metric_value)


            #pushadd_to_gateway(self.pushgateway_url, registry=self.registry, job=self.job_name)

    def pytest_sessionfinish(self, session):

        passed_metric = Gauge(self._make_metric_name("passed"),
                "Number of passed tests",
                self.extra_labels.keys(),
                registry=self.registry)
        passed_metric.labels(**self.extra_labels).set(self.passed)

        failed_metric = Gauge(self._make_metric_name("failed"),
                "Number of failed tests",
                self.extra_labels.keys(),
                registry=self.registry)
        failed_metric.labels(**self.extra_labels).set(self.failed)

        skipped_metric = Gauge(self._make_metric_name("skipped"),
                "Number of skipped tests",
                self.extra_labels.keys(),
                registry=self.registry)
        skipped_metric.labels(**self.extra_labels).set(self.skipped)

        push_to_gateway(self.pushgateway_url, registry=self.registry, job=self.job_name)



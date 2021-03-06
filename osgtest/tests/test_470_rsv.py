import osgtest.library.core as core
import osgtest.library.files as files
import osgtest.library.osgunittest as osgunittest

import cagen
import re
import os
import pwd
import shutil
import socket
import ConfigParser

"""
Testing number conventions:
 001-009 - Configuration, making proxy, etc
 010-019 - Tests that don't require the rsv service to be running
 020-029 - Tests for the tools that require the rsv service to be running
 030-049 - Testing of metrics that don't require any other services
 050-079 - Testing of metrics that require a CE
 080-099 - Testing of metrics that require an SE
 100-120 - Testing of consumers
"""


class TestRSV(osgunittest.OSGTestCase):

    host = socket.getfqdn()

    @core.osgrelease(3.4)
    def setUp(self):
        pass

    def start_rsv(self):
        core.check_system(('rsv-control', '--on'), 'rsv-control --on')

    def stop_rsv(self):
        core.check_system(('rsv-control', '--off'), 'rsv-control --off')

    def config_and_restart(self):
        self.stop_rsv()
        core.check_system(('osg-configure', '-c', '-m', 'rsv'), 'osg-configure -c -m rsv')
        self.start_rsv()

    def run_metric(self, metric, host=host, accept_status=['OK']):
        command = ('rsv-control', '--run', '--host', host, metric)
        stdout = core.check_system(command, ' '.join(command))[0]

        metric_passed = False
        for status in accept_status:
            if re.search("metricStatus: {0}".format(status), stdout) is not None:
                metric_passed = True
        self.assert_(metric_passed)

    def load_config_file(self):
        """ Load /etc/rsv/rsv.conf """
        config = ConfigParser.RawConfigParser()
        config.optionxform = str
        config.read(core.config['rsv.config-file'])
        return config

    def write_config_file(self, config):
        """ Write /etc/rsv/rsv.conf """
        fd = open(core.config['rsv.config-file'], 'w')
        config.write(fd)
        fd.close()

    def use_user_proxy(self):
        """ Switch to using a user proxy instead of a service cert """
        config = self.load_config_file()
        self.assert_(os.path.exists(config.get('rsv', 'service-proxy')))
        config.set('rsv', 'proxy-file', config.get('rsv', 'service-proxy'))
        config.remove_option('rsv', 'service-cert')
        config.remove_option('rsv', 'service-key')
        config.remove_option('rsv', 'service-proxy')
        self.write_config_file(config)

    def use_service_cert(self):
        """ Switch to using a service certificate instead of a user proxy """
        # This function relies on calling use_user_proxy first
        config = self.load_config_file()
        self.assert_(config.has_option('rsv', 'proxy-file'))
        config.set('rsv', 'service-cert', core.config['rsv.certfile'])
        config.set('rsv', 'service-key', core.config['rsv.keyfile'])
        config.set('rsv', 'service-proxy', config.get('rsv', 'proxy-file'))
        config.remove_option('rsv', 'proxy-file')
        self.write_config_file(config)

    def use_condor_g(self):
        config = self.load_config_file()
        config.set('rsv', 'use-condor-g', 'True')
        self.write_config_file(config)

    def test_001_set_config_vals(self):
        core.config['rsv.certfile'] = "/etc/grid-security/rsv/rsvcert.pem"
        core.config['rsv.keyfile'] = "/etc/grid-security/rsv/rsvkey.pem"
        core.config['rsv.osg-configure-config-file'] = '/etc/osg/config.d/30-rsv.ini'
        core.config['rsv.config-file'] = '/etc/rsv/rsv.conf'

    def test_002_setup_certificate(self):
        core.skip_ok_unless_installed('rsv')

        # TODO - on fermicloud machines we copy the hostcert.  Can we do better?
        if not os.path.exists(os.path.dirname(core.config['rsv.certfile'])):
            os.makedirs(os.path.dirname(core.config['rsv.certfile']))
        if not os.path.exists(core.config['rsv.certfile']):
            shutil.copy('/etc/grid-security/hostcert.pem', core.config['rsv.certfile'])
        if not os.path.exists(core.config['rsv.keyfile']):
            shutil.copy('/etc/grid-security/hostkey.pem', core.config['rsv.keyfile'])

        (rsv_uid, rsv_gid) = pwd.getpwnam('rsv')[2:4]
        os.chown(core.config['rsv.certfile'], rsv_uid, rsv_gid)
        os.chmod(core.config['rsv.certfile'], 0o444)
        os.chown(core.config['rsv.keyfile'], rsv_uid, rsv_gid)
        os.chmod(core.config['rsv.keyfile'], 0o400)

    def test_003_setup_grid_mapfile(self):
        core.skip_ok_unless_installed('rsv')

        # Register the cert in the gridmap file
        cert_subject = cagen.certificate_info(core.config['rsv.certfile'])[0]
        files.append(core.config['system.mapfile'], '"%s" rsv\n' % (cert_subject), owner='rsv')

    def test_004_load_default_config(self):
        core.skip_ok_unless_installed('rsv')

        # We'll pull in the default config file and store it.  We might want to
        # do tests based on the default.
        self.config = ConfigParser.RawConfigParser()
        self.config.optionxform = str
        self.config.read(core.config['rsv.osg-configure-config-file'])
        core.config['rsv.default-config'] = self.config

    def test_010_version(self):
        core.skip_ok_unless_installed('rsv')

        command = ('rsv-control', '--version')
        stdout = core.check_system(command, 'rsv-control --version')[0]

        # The rsv-control --version just returns a string like '1.0.0'.
        self.assert_(re.search(r'\d+.\d+.\d+', stdout) is not None)

    def test_011_list(self):
        core.skip_ok_unless_installed('rsv')

        command = ('rsv-control', '--list', '--all')
        stdout = core.check_system(command, 'rsv-control --list --all')[0]

        # I don't want to parse the output too much, but we know that most
        # of the metrics start with 'org.osg.'.  So just check for that string
        # once and we'll call it good enough.
        self.assert_(re.search('org.osg.', stdout) is not None)

    def test_012_list_with_cron(self):
        core.skip_ok_unless_installed('rsv')

        command = ('rsv-control', '--list', '--all', '--cron')
        stdout = core.check_system(command, 'rsv-control --list --all')[0]

        # One of the header columns will say 'Cron times'
        self.assert_(re.search('Cron times', stdout) is not None)

    def test_013_profiler(self):
        core.skip_ok_unless_installed('rsv')

        profiler_tarball = 'rsv-profiler.tar.gz'

        command = ('rsv-control', '--profile')
        stdout = core.check_system(command, 'rsv-control --profile')[0]
        self.assert_(re.search('Running the rsv-profiler', stdout) is not None)
        self.assert_(os.path.exists(profiler_tarball))
        files.remove(profiler_tarball)

    def test_024_rsv_control_bad_arg(self):
        core.skip_ok_unless_installed('rsv')

        command = ('rsv-control', '--kablooey')
        ret, _, _ = core.system(command, 'rsv-control --kablooey')
        self.assert_(ret != 0)

    def test_020_stop_rsv(self):
        core.skip_ok_unless_installed('rsv')

        self.stop_rsv()

    def test_021_start_rsv(self):
        core.skip_ok_unless_installed('rsv')

        self.start_rsv()

    def test_022_job_list(self):
        core.skip_ok_unless_installed('rsv')

        command = ('rsv-control', '--job-list')
        stdout = core.check_system(command, 'rsv-control --job-list')[0]

        # TODO
        # Make sure that the header prints at least.  We can improve this
        self.assert_(re.search('OWNER', stdout) is not None)

    def test_030_ping_metric(self):
        core.skip_ok_unless_installed('rsv')

        self.run_metric('org.osg.general.ping-host')

    def test_031_hostcert_expiry_metric(self):
        core.skip_ok_unless_installed('rsv')

        self.run_metric('org.osg.local.hostcert-expiry')

    def test_032_cacert_expiry(self):
        core.skip_ok_unless_installed('rsv', 'htcondor-ce')

        self.run_metric('org.osg.certificates.cacert-expiry',
                        accept_status=['OK', 'WARNING'])

    def test_033_crlcert_expiry(self):
        core.skip_ok_unless_installed('rsv', 'htcondor-ce')

        self.run_metric('org.osg.certificates.crl-expiry',
                        accept_status=['OK', 'WARNING'])


    # Print Java version info, mostly useful for debugging test runs.
    def test_053_java_version_metric(self):
        core.skip_ok_unless_installed('rsv', 'htcondor-ce')
        self.run_metric('org.osg.general.java-version')

    def test_075_switch_to_condor_g(self):
        core.skip_ok_unless_installed('rsv')

        self.use_condor_g()

    def test_100_html_consumer(self):
        # This test must come after some of the metric tests so that we have
        # some job records to use to create an index.html
        core.skip_ok_unless_installed('rsv')

        index_file = "/usr/share/rsv/www/index.html"

        # We are going to make sure the html-consumer runs, and that the index
        # file is updated.
        old_mtime = os.stat(index_file).st_mtime

        stdout = core.check_system("su -c '/usr/libexec/rsv/consumers/html-consumer' rsv", "run html-consumer", shell=True)[0]
        self.assert_('html-consumer initializing' in stdout)

        new_mtime = os.stat(index_file).st_mtime
        self.assert_(old_mtime != new_mtime)


# Tests to write:
# - run other metrics?
#     org.osg.certificates.cacert-expiry                        | OSG-CE
#     org.osg.certificates.crl-expiry                           | OSG-CE
#     org.osg.general.osg-directories-CE-permissions            | OSG-CE

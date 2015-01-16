import osgtest.library.core as core
import osgtest.library.java as java
import osgtest.library.files as files
import osgtest.library.tomcat as tomcat
import osgtest.library.osgunittest as osgunittest

class TestCleanupJava(osgunittest.OSGTestCase):

    def _select_old_alternative(self, config_type):
        if not core.state['java.%s-selected' % config_type]:
            return

        java.select_ver(config_type, core.config['java.old-%s-ver' % config_type])
        self.assert_(java.verify_ver(config_type, core.config['java.old-%s-ver' % config_type]),
                     'could not select old java version')

    def test_01_clean_bestman_env(self):
        if core.rpm_regexp_is_installed(r'^bestman2') and java.is_openjdk_installed():
            files.restore('/etc/sysconfig/bestman2', owner='java')

    def test_02_clean_tomcat_env(self):
        if core.rpm_is_installed(tomcat.pkgname()) and java.is_openjdk_installed():
            files.restore('/etc/sysconfig/' + tomcat.pkgname(), owner='java')

    def test_03_revert_java_ver(self):
        self._select_old_alternative('java')

    def test_04_revert_javac_ver(self):
        self._select_old_alternative('javac')

    def test_05_restore_symlinks(self):
        if core.rpm_is_installed('jdk') and java.is_openjdk_installed():
            for link in core.config['java.bad_links']:
                files.restore(link, owner='java')
        
# encoding: utf-8
'''
A script to start the CherryPy WSGI server

This is run by ``salt-api`` and started in a multiprocess.
'''
# pylint: disable=C0103

# Import Python libs
import logging
import os

# Import CherryPy without traceback so we can provide an intelligent log
# message in the __virtual__ function
try:
    import cherrypy

    cpy_error = None
except ImportError as exc:
    cpy_error = exc

logger = logging.getLogger(__name__)
cpy_min = '3.2.2'

def verify_certs(*args):
    '''
    Sanity checking for the specified SSL certificates
    '''
    msg = ("Could not find a certificate: {0}\n"
            "If you want to quickly generate a self-signed certificate, "
            "use the tls.create_self_signed_cert function in Salt")

    for arg in args:
        if not os.path.exists(arg):
            raise Exception(msg.format(arg))

log = logging.getLogger(__name__)
class SaltApiV2():
    def run(self):
        '''
        Start the server loop
        '''
        import handler
        import salt.config
        __opts__ = salt.config.client_config(
            os.environ.get('SALT_MASTER_CONFIG', '/etc/salt/master'))
        root, apiopts, conf = handler.get_app(__opts__)

        cherrypy.quickstart(root, apiopts.get('root_prefix', '/'), conf)
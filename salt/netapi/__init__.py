# encoding: utf-8
'''
Make api awesomeness
'''
from __future__ import absolute_import
# Import Python libs
import inspect
import os
import time
import traceback

# Import Salt libs
import salt.log  # pylint: disable=W0611
import salt.client
import salt.config
import salt.runner
import salt.syspaths
import salt.wheel
import salt.utils
import salt.client.ssh.client
import salt.exceptions
import subprocess
import re
import random

# Import third party libs
import salt.ext.six as six

from salt.selflog.manual_log import ManualLog

api_log = ManualLog().get_logger('salt_api_module')


def getAcceptIp():
    stdout_val, stderr_val = executeSaltCmd("salt-key -l acc")
    syndicList = re.findall(
        r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", stdout_val, re.M)
    return syndicList

def getRandomSuffix():
    return "_%s_%s" % (random.randint(0, 999999), time.time())

def executeSaltCmd(cmd, msg_in=''):
    try:
        proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, )
        stdout_value, stderr_value = proc.communicate(msg_in)

        return stdout_value, stderr_value
    except Exception, e:
        log.error(traceback.format_exc())
        # print('traceback.format_exc():\n%s' % traceback.format_exc())


class NetapiClient(object):
    '''
    Provide a uniform method of accessing the various client interfaces in Salt
    in the form of low-data data structures. For example:

    >>> client = NetapiClient(__opts__)
    >>> lowstate = {'client': 'local', 'tgt': '*', 'fun': 'test.ping', 'arg': ''}
    >>> client.run(lowstate)
    '''

    def __init__(self, opts):
        self.opts = opts

    def _is_master_running(self):
        '''
        Perform a lightweight check to see if the master daemon is running

        Note, this will return an invalid success if the master crashed or was
        not shut down cleanly.
        '''
        if self.opts['transport'] == 'tcp':
            ipc_file = 'publish_pull.ipc'
        else:
            ipc_file = 'workers.ipc'
        return os.path.exists(os.path.join(
            self.opts['sock_dir'],
            ipc_file))

    def run(self, low):
        '''
        Execute the specified function in the specified client by passing the
        lowstate
        '''
        # Eauth currently requires a running daemon and commands run through
        # this method require eauth so perform a quick check to raise a
        # more meaningful error.
        if not self._is_master_running():
            raise salt.exceptions.SaltDaemonNotRunning(
                'Salt Master is not available.')

        if low.get('client') not in CLIENTS:
            raise salt.exceptions.SaltInvocationError(
                'Invalid client specified: \'{0}\''.format(low.get('client')))

        if not ('token' in low or 'eauth' in low) and low['client'] != 'ssh':
            raise salt.exceptions.EauthAuthenticationError(
                'No authentication credentials given')

        l_fun = getattr(self, low['client'])
        f_call = salt.utils.format_call(l_fun, low)
        return l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))

    def local_async(self, *args, **kwargs):
        '''
        Run :ref:`execution modules <all-salt.modules>` asynchronously

        Wraps :py:meth:`salt.client.LocalClient.run_job`.

        :return: job ID
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.run_job(*args, **kwargs)

    def apiv2_run(self, low):
        '''
        Execute the specified function in the specified client by passing the
        lowstate
        '''
        # Eauth currently requires a running daemon and commands run through
        # this method require eauth so perform a quick check to raise a
        # more meaningful error.
        if not self._is_master_running():
            raise salt.exceptions.SaltDaemonNotRunning(
                'Salt Master is not available.')

        if low.get('client') not in CLIENTS:
            raise salt.exceptions.SaltInvocationError(
                'Invalid client specified: \'{0}\''.format(low.get('client')))

        if not ('token' in low or 'eauth' in low) and low['client'] != 'ssh':
            raise salt.exceptions.EauthAuthenticationError(
                'No authentication credentials given')

        l_fun = getattr(self, low['client'])
        f_call = salt.utils.format_call(l_fun, low)
        return self.apiv2_sync(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        # return l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))

    def apiv2_aysnc_run(self, low):
        '''
        Execute the specified function in the specified client by passing the
        lowstate
        '''
        # Eauth currently requires a running daemon and commands run through
        # this method require eauth so perform a quick check to raise a
        # more meaningful error.
        if not self._is_master_running():
            raise salt.exceptions.SaltDaemonNotRunning(
                'Salt Master is not available.')

        if low.get('client') not in CLIENTS:
            raise salt.exceptions.SaltInvocationError(
                'Invalid client specified: \'{0}\''.format(low.get('client')))

        if not ('token' in low or 'eauth' in low) and low['client'] != 'ssh':
            raise salt.exceptions.EauthAuthenticationError(
                'No authentication credentials given')

        l_fun = getattr(self, low['client'])
        f_call = salt.utils.format_call(l_fun, low)
        return self.apiv2_async(*f_call.get('args', ()), **f_call.get('kwargs', {}))

    def apiv2_run_jobs(self, low):
        '''
        Execute the specified function in the specified client by passing the
        lowstate
        '''
        # Eauth currently requires a running daemon and commands run through
        # this method require eauth so perform a quick check to raise a
        # more meaningful error.
        if not self._is_master_running():
            raise salt.exceptions.SaltDaemonNotRunning(
                'Salt Master is not available.')

        if low.get('client') not in CLIENTS:
            raise salt.exceptions.SaltInvocationError(
                'Invalid client specified: \'{0}\''.format(low.get('client')))

        if not ('token' in low or 'eauth' in low) and low['client'] != 'ssh':
            raise salt.exceptions.EauthAuthenticationError(
                'No authentication credentials given')
        l_fun = getattr(self, low['client'])
        f_call = salt.utils.format_call(l_fun, low)
        # return l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        return self.apiv2_jobs(*f_call.get('args', ()), **f_call.get('kwargs', {}))

    def apiv2_jobs(self, fun, timeout=None, full_return=False, **kwargs):
        # '''
        # Execute the salt api v2 lookup job
        # '''
        import salt.newrun
        if fun == salt.newrun.FunctionType.LOOKUP_JID:
            self.retReturns = {'info': [
                {'User': salt.newrun.SaltStaticConstants.API_USER, 'Minions': [], 'Arguments': [], 'Result': {},
                 'Target': []}], 'return': [{}]}
        elif fun == salt.newrun.FunctionType.LIST_JOBS:
            self.retReturns = {'return': []}
        else:
            return {}

        try:
            import salt.client
            import cherrypy

            salt_config = cherrypy.config['saltopts']

            sub_timeout = salt_config['channel_sub_timeout']
            sub_node = ''
            _channel_redis_sentinel = salt_config['channel_redis_sentinel']
            _channel_redis_password = salt_config['channel_redis_password']
            _master_pub_topic = salt_config['id']

            self.bootConfig = {'_sub_timeout': sub_timeout, '_sub_node': sub_node,
                               '_channel_redis_sentinel': _channel_redis_sentinel,
                               '_channel_redis_password': _channel_redis_password,
                               '_master_pub_topic': _master_pub_topic}

            from salt.newrun import (json, byteify, MessageType)

            wrapMesage = {'type': fun, 'kwargs': kwargs,
                          'tempTopic': '%s%s%s' % (salt.newrun.TopicType.JOBS, str(salt.newrun.uuid.uuid1()), getRandomSuffix())}

            api_log.info("jobswrapMesage: %s" % wrapMesage)

            from salt.redis.RedisWrapper import Singleton
            redisWrapper = Singleton(**self.bootConfig)

            selfIp = salt_config['id']
            redisChannel = redisWrapper.redisInstance.pubsub()
            redisChannel.subscribe(wrapMesage['tempTopic'])

            comeSubList = getAcceptIp()
            if selfIp in comeSubList:
                comeSubList.remove(selfIp)
            syndic_count = len(comeSubList)
            resultCount = 0
            pingCount = 0

            resultPingSet = set()
            resultExeSet = set()
            executeStart = time.time()

            # add backup node to resultExeSet
            # backupMaster = salt_config['backup_master']
            # api_log.info("backupMaster: {}".format(backupMaster))
            # backupMasterArray = backupMaster.split(',')
            # backupCount = len(backupMasterArray)
            # for m in backupMasterArray:
            #     resultExeSet.add(m)

            # api_log.info("resultExeSetArray: {}".format(resultExeSet))

            # NOTE: must publish cmd after registered the redis listen
            # else we will miss ping message
            redisWrapper.redisInstance.publish(redisWrapper.master_pub_topic, salt.newrun.json.dumps(wrapMesage))

            calLoopCount = 0
            tmpPercentCount = 0

            for message in redisChannel.listen():
                try:

                    messageJson = byteify(message)
                    if messageJson['type'] == 'message':
                        ##result +1 only when receive sub return execute data
                        resultMessage = messageJson['data']
                        try:
                            #api_log.info(resultMessage)
                            callResult = json.loads(resultMessage, encoding='utf-8')
                            callResult = byteify(callResult)

                            api_log.info('callback result for: %s, with: %s, result: %s' % (kwargs['jid'], wrapMesage['tempTopic'], callResult))

                            if isinstance(callResult, dict):
                                if 'type' in callResult:
                                    messageType = callResult['type']
                                    messageIp = callResult['sub_ip']

                                    if messageType == MessageType.PING and messageIp in comeSubList:
                                        resultPingSet.add(messageIp)
                                        pingCount += 1
                                    else:
                                        if messageType == MessageType.WORK or messageType == MessageType.INTERRUPT:
                                            resultExeSet.add(messageIp)
                                            resultCount += 1
                                else:
                                    # filter no return received of sub node
                                    if callResult['jobrets']:
                                        if fun == salt.newrun.FunctionType.LOOKUP_JID:
                                            tmpRet = callResult['jobrets']
                                            retInfo = self.retReturns['info'][0]

                                            if 'Function' in tmpRet[0]:
                                                if tmpRet[0]['Function'] != 'unknown-function':
                                                    retInfo['Function'] = tmpRet[0]['Function']

                                            retInfo['jid'] = kwargs['jid']

                                            if 'Target-type' in tmpRet[0]:
                                                retInfo['Target-type'] = tmpRet[0]['Target-type']

                                            if 'StartTime' in tmpRet[0]:
                                                retInfo['StartTime'] = tmpRet[0]['StartTime']

                                            if 'Target' in tmpRet[0]:
                                                if isinstance(tmpRet[0]['Target'], list):
                                                    retInfo['Target'] = ",".join(tmpRet[0]['Target'])
                                                else:
                                                    if tmpRet[0]['Target'] != 'unknown-target':
                                                        retInfo['Target'] = tmpRet[0]['Target']

                                            if 'Arguments' in tmpRet[0]:
                                                retInfo['Arguments'] = tmpRet[0]['Arguments']

                                            if 'Minions' in tmpRet[0]:
                                                retInfo['Minions'] = retInfo['Minions'] + tmpRet[0]['Minions']

                                            if 'Result' in tmpRet[0]:
                                                retInfo['Result'] = dict(retInfo['Result'], **tmpRet[0]['Result'])

                                            if tmpRet[0]['Result']:
                                                for key, value in tmpRet[0]['Result'].items():
                                                    subRet = {key: value['return']}
                                                    z = self.retReturns['return'][0].copy()
                                                    z.update(subRet)
                                                    self.retReturns['return'][0] = z


                                        elif fun == salt.newrun.FunctionType.LIST_JOBS:
                                            self.retReturns['return'] = self.retReturns['return'] + callResult[
                                                'jobrets']
                                        else:
                                            pass

                            else:
                                # TODO handle other messages?
                                pass

                        except:
                            resultCount += 1
                            api_log.error(traceback.format_exc())
                            pass

                    ##check sub timeout, if no node running again
                    resultCount = len(resultExeSet)

                    losePingCount = syndic_count - pingCount
                    runningCount = syndic_count - resultCount - losePingCount

                    if syndic_count == pingCount and pingCount == resultCount:
                        break

                    api_log.info('%s, %s, %s, %s, %s' % (syndic_count, resultCount, pingCount, runningCount,
                                                         [i for i in comeSubList if i not in resultExeSet]))

                    if pingCount < syndic_count and runningCount <= 0:
                        if (time.time() - executeStart) > sub_timeout:
                            break

                    # if pingCount == syndic_count:
                    #     nowPercentCount = float(resultCount) / float(syndic_count)
                    #
                    #     if nowPercentCount >= 0.9:
                    #         calLoopCount += 1

                except:
                    api_log.error(traceback.format_exc())
                    pass

                # check if reach syndic count, break out
                if (resultCount - syndic_count) >= 0:
                    break

                api_log.info("calLoopCount: {}".format(calLoopCount))
                if calLoopCount >= 2:
                    break

            redisChannel.unsubscribe(wrapMesage['tempTopic'])
            redisChannel.connection_pool.disconnect()

            disconnectedSyndic = set(comeSubList).difference(resultPingSet)
            if disconnectedSyndic:
                api_log.info('With disconnected syndic: %s' % list(disconnectedSyndic))

            # In end of process, distinct target list

            api_log.info("self.retReturns: {}".format(self.retReturns))
            return self.retReturns
        except:
            api_log.error(traceback.format_exc())

    def kwargsFormat(self, kwargs):
        '''
        for new apiv2, we need handle the kwargs to normal saltx mode
        '''
        kwargs['show_jid'] = False
        kwargs['timeout'] = 30
        kwargs['show_timeout'] = True
        # kwargs['arg'] = []
        kwargs['delimiter'] = ":"

        if 'token' in kwargs:
            del kwargs['token']
        if '__current_eauth_groups' in kwargs:
            del kwargs['__current_eauth_groups']
        if '__current_eauth_user' in kwargs:
            del kwargs['__current_eauth_user']
        if 'expr_form' in kwargs:
            del kwargs['expr_form']

        if 'client' in kwargs:
            del kwargs['client']

    # NOTE: Only in super master, filter no-response ip, when use saltx
    def getPassedIp(self):
        import numpy
        numpy.warnings.filterwarnings('ignore')
        passed_ip = numpy.loadtxt('/data0/md/ip.md', dtype=numpy.str)
        return passed_ip.tolist()

    def kwargsTgtFilter(self, kwargs):
        passed_ip = self.getPassedIp()
        if passed_ip:
            if isinstance(kwargs['tgt'], list):
                kwargs['tgt'] = [i for i in kwargs['tgt'] if i not in passed_ip]
                if len(kwargs['tgt']) == 0:
                    print('There are nothing iplist to be apply.')
                    return False
            elif isinstance(kwargs['tgt'], str):
                if kwargs['tgt'] in passed_ip:
                    print('There are nothing iplist to be apply.')
                    return False
        return True

    def apiv2_async(self, *args, **kwargs):
        # '''
        # Execute the salt api v2 aysnc
        # '''
        self.retReturns = {}

        try:
            import salt.client
            import cherrypy

            salt_config = cherrypy.config['saltopts']

            sub_timeout = salt_config['channel_sub_timeout']
            sub_node = ''
            _channel_redis_sentinel = salt_config['channel_redis_sentinel']
            _channel_redis_password = salt_config['channel_redis_password']
            _master_pub_topic = salt_config['id']

            self.bootConfig = {'_sub_timeout': sub_timeout, '_sub_node': sub_node,
                               '_channel_redis_sentinel': _channel_redis_sentinel,
                               '_channel_redis_password': _channel_redis_password,
                               '_master_pub_topic': _master_pub_topic}

            from salt.newrun import (json, byteify, MessageType)
            kwargs = byteify(kwargs)

            self.kwargsFormat(kwargs)

            if isinstance(kwargs['tgt'], str):
                if kwargs['tgt'] != '*':
                    tgtTemp = kwargs['tgt']
                    kwargs['tgt'] = tgtTemp.split(",")
                    if len(kwargs['tgt']) > 1:
                        kwargs['tgt_type'] = 'list'
                    else:
                        kwargs['tgt_type'] = 'glob'
                        kwargs['tgt'] = tgtTemp

                    passedTgtFilter = self.kwargsTgtFilter(kwargs)
                    if not passedTgtFilter:
                        return self.retReturns
                else:
                    kwargs['tgt_type'] = 'glob'
            elif isinstance(kwargs['tgt'], list):
                kwargs['tgt_type'] = 'list'
                passedTgtFilter = self.kwargsTgtFilter(kwargs)
                if not passedTgtFilter:
                    return self.retReturns

            else:
                print('unvalid tgt type: %s' % type(kwargs['tgt']))
                return self.retReturns

            import salt.newrun

            # NOTE: generate a jid for saltx
            jid = salt.utils.jid.gen_jid()

            wrapMesage = {'type': salt.newrun.FunctionType.ASYNC_RUN, 'jid': jid, 'kwargs': kwargs,
                          'tempTopic': str(salt.newrun.uuid.uuid1()) + "_" + jid}

            api_log.info('async run with wrapMesage: %s' % wrapMesage)

            from salt.redis.RedisWrapper import Singleton
            redisWrapper = Singleton(**self.bootConfig)

            # NOTE: must publish cmd after registered the redis listen
            # else we will miss ping message
            redisWrapper.redisInstance.publish(redisWrapper.master_pub_topic, salt.newrun.json.dumps(wrapMesage))

            redisWrapper.redisInstance.connection_pool.disconnect()

            self.retReturns = {"_links": {"jobs": [{"href": ("/jobs/%s" % jid)}]}, "return": [
                {"jid": ("%s" % jid), "minions": ([] if (kwargs['tgt'] == '*') else kwargs['tgt'])}]}
            return self.retReturns
        except:
            api_log.info(traceback.format_exc())

    def apiv2_sync(self, *args, **kwargs):
        # '''
        # Execute the salt api v2
        # '''
        self.retReturns = {}

        try:
            import salt.client
            import cherrypy

            salt_config = cherrypy.config['saltopts']

            sub_timeout = salt_config['channel_sub_timeout']
            sub_node = ''
            _channel_redis_sentinel = salt_config['channel_redis_sentinel']
            _channel_redis_password = salt_config['channel_redis_password']
            _master_pub_topic = salt_config['id']

            self.bootConfig = {'_sub_timeout': sub_timeout, '_sub_node': sub_node,
                               '_channel_redis_sentinel': _channel_redis_sentinel,
                               '_channel_redis_password': _channel_redis_password,
                               '_master_pub_topic': _master_pub_topic}

            # NOTE: Only in super master, filter no-response ip, when use saltx
            def getPassedIp():
                import numpy
                numpy.warnings.filterwarnings('ignore')
                passed_ip = numpy.loadtxt('/data0/md/ip.md', dtype=numpy.str)
                return passed_ip.tolist()

            from salt.newrun import (json, byteify, MessageType)
            kwargs = byteify(kwargs)

            self.kwargsFormat(kwargs)

            minionLogList = set()

            if isinstance(kwargs['tgt'], str):
                if kwargs['tgt'] != '*':
                    tgtTemp = kwargs['tgt']
                    kwargs['tgt'] = tgtTemp.split(",")
                    if len(kwargs['tgt']) > 1:
                        kwargs['tgt_type'] = 'list'
                        minionLogList = set(kwargs['tgt'])
                    else:
                        kwargs['tgt_type'] = 'glob'
                        kwargs['tgt'] = tgtTemp
                        minionLogList.add(kwargs['tgt'])

                    passedTgtFilter = self.kwargsTgtFilter(kwargs)
                    if not passedTgtFilter:
                        return self.retReturns
                else:
                    kwargs['tgt_type'] = 'glob'
            elif isinstance(kwargs['tgt'], list):
                minionLogList = set(kwargs['tgt'])
                kwargs['tgt_type'] = 'list'
                passedTgtFilter = self.kwargsTgtFilter(kwargs)
                if not passedTgtFilter:
                    return self.retReturns

            else:
                print('unvalid tgt type: %s' % type(kwargs['tgt']))
                return self.retReturns

            import salt.newrun

            wrapMesage = {'type': salt.newrun.FunctionType.SYNC_RUN, 'kwargs': kwargs,
                          'tempTopic': str(salt.newrun.uuid.uuid1()) + getRandomSuffix()}

            api_log.info(wrapMesage)

            from salt.redis.RedisWrapper import Singleton

            redisWrapper = Singleton(**self.bootConfig)

            selfIp = salt_config['id']
            redisChannel = redisWrapper.redisInstance.pubsub()
            redisChannel.subscribe(wrapMesage['tempTopic'])

            noResponseRet = []
            noConnectRet = []
            emptyRet = []
            # retcodes = []

            comeSubList = getAcceptIp()
            if selfIp in comeSubList:
                comeSubList.remove(selfIp)

            syndic_count = len(comeSubList)
            resultCount = 0
            pingCount = 0

            resultPingSet = set()
            resultExeSet = set()
            executeStart = time.time()

            # NOTE: must publish cmd after registered the redis listen
            # else we will miss ping message
            redisWrapper.redisInstance.publish(redisWrapper.master_pub_topic, salt.newrun.json.dumps(wrapMesage))

            for message in redisChannel.listen():
                try:
                    messageType = byteify(message)
                    if messageType['type'] == 'message':
                        ##result +1 only when receive sub return execute data
                        resultMessage = messageType['data']
                        try:

                            callResult = json.loads(resultMessage, encoding='utf-8')
                            callResult = byteify(callResult)

                            if isinstance(callResult, dict):
                                if 'type' in callResult:
                                    messageType = callResult['type']
                                    messageIp = callResult['sub_ip']

                                    if messageType == MessageType.PING and messageIp in comeSubList:
                                        resultPingSet.add(messageIp)
                                        pingCount += 1
                                    else:
                                        if messageType == MessageType.WORK or messageType == MessageType.INTERRUPT:
                                            resultExeSet.add(messageIp)
                                            resultCount += 1
                                            # if messageIp not in readyBackupMaidSet:
                                            #     resultCount += 1
                                else:
                                    # filter no return received of sub node
                                    retJsonObj = callResult['ret_']
                                    if retJsonObj:
                                        # reset start time
                                        executeStart = time.time()

                                        if callResult['out'] == 'no_return':
                                            if '[No response]' in json.dumps(retJsonObj):
                                                noResponseRet.append(callResult)
                                            else:
                                                noConnectRet.append(callResult)
                                        else:
                                            for k, v in retJsonObj.items():
                                                minionLogList.discard(k)

                                            if callResult['retcode'] == 0:
                                                tmpRet = retJsonObj
                                                self.retReturns = dict(self.retReturns, **tmpRet)
                                            else:
                                                emptyRet.append(callResult)

                            else:
                                # TODO handle other messages?
                                pass

                        except:
                            resultCount += 1
                            api_log.info(traceback.format_exc())
                            pass

                    ##check sub timeout, if no node running again
                    # api_log.info(resultExeSet.difference(comeSubList))
                    # api_log.info('{}, {}, {}, {}, {}'.format(syndic_count, resultCount, pingCount, resultExeSet, [item for item in resultExeSet if item not in comeSubList]))

                    losePingCount = syndic_count - pingCount
                    runningCount = syndic_count - resultCount - losePingCount

                    if pingCount < syndic_count and runningCount <= 0:
                        if (time.time() - executeStart) > sub_timeout:
                            break
                    elif syndic_count == resultCount and resultCount == pingCount:
                        break
                    elif pingCount == syndic_count and runningCount > 0:
                        if (time.time() - executeStart) > sub_timeout:
                            break
                    elif len(minionLogList) <= 0:
                        break
                except:
                    api_log.info(traceback.format_exc())
                    pass

            redisChannel.unsubscribe(wrapMesage['tempTopic'])
            redisChannel.connection_pool.disconnect()

            ##begin print error returns
            for result in emptyRet:
                if result['ret_']:
                    tmpRet = result['ret_']
                    self.retReturns = dict(self.retReturns, **tmpRet)

            for result in noResponseRet:
                if result['ret_']:
                    tmpRet = result['ret_']
                    self.retReturns = dict(self.retReturns, **tmpRet)

            for result in noConnectRet:
                if result['ret_']:
                    tmpRet = result['ret_']
                    self.retReturns = dict(self.retReturns, **tmpRet)

            disconnectedSyndic = set(comeSubList).difference(resultPingSet)
            if disconnectedSyndic:
                api_log.info('With disconnected syndic: %s' % list(disconnectedSyndic))
        except:
            api_log.error("sync throw error:")
            api_log.error(traceback.format_exc())
        return self.retReturns

    def local(self, *args, **kwargs):
        '''
        Run :ref:`execution modules <all-salt.modules>` synchronously

        See :py:meth:`salt.client.LocalClient.cmd` for all available
        parameters.

        Sends a command from the master to the targeted minions. This is the
        same interface that Salt's own CLI uses. Note the ``arg`` and ``kwarg``
        parameters are sent down to the minion(s) and the given function,
        ``fun``, is called with those parameters.

        :return: Returns the result from the execution module
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.cmd(*args, **kwargs)

    def local_subset(self, *args, **kwargs):
        '''
        Run :ref:`execution modules <all-salt.modules>` against subsets of minions

        .. versionadded:: 2016.3.0

        Wraps :py:meth:`salt.client.LocalClient.cmd_subset`
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.cmd_subset(*args, **kwargs)

    def local_batch(self, *args, **kwargs):
        '''
        Run :ref:`execution modules <all-salt.modules>` against batches of minions

        .. versionadded:: 0.8.4

        Wraps :py:meth:`salt.client.LocalClient.cmd_batch`

        :return: Returns the result from the exeuction module for each batch of
            returns
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.cmd_batch(*args, **kwargs)

    def ssh(self, *args, **kwargs):
        '''
        Run salt-ssh commands synchronously

        Wraps :py:meth:`salt.client.ssh.client.SSHClient.cmd_sync`.

        :return: Returns the result from the salt-ssh command
        '''
        ssh_client = salt.client.ssh.client.SSHClient(mopts=self.opts,
                                                      disable_custom_roster=True)
        return ssh_client.cmd_sync(kwargs)

    def runner(self, fun, timeout=None, full_return=False, **kwargs):
        '''
        Run `runner modules <all-salt.runners>` synchronously

        Wraps :py:meth:`salt.runner.RunnerClient.cmd_sync`.

        Note that runner functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the runner module
        '''
        kwargs['fun'] = fun
        runner = salt.runner.RunnerClient(self.opts)
        print('-------original--------api-----opts------%s' % self.opts)
        print('-------original--------api-----kwargs------%s' % kwargs)
        return runner.cmd_sync(kwargs, timeout=timeout, full_return=full_return)

    def runner_async(self, fun, **kwargs):
        '''
        Run `runner modules <all-salt.runners>` asynchronously

        Wraps :py:meth:`salt.runner.RunnerClient.cmd_async`.

        Note that runner functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: event data and a job ID for the executed function.
        '''
        kwargs['fun'] = fun
        runner = salt.runner.RunnerClient(self.opts)
        return runner.cmd_async(kwargs)

    def wheel(self, fun, **kwargs):
        '''
        Run :ref:`wheel modules <all-salt.wheel>` synchronously

        Wraps :py:meth:`salt.wheel.WheelClient.master_call`.

        Note that wheel functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the wheel module
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.WheelClient(self.opts)
        return wheel.cmd_sync(kwargs)

    def wheel_async(self, fun, **kwargs):
        '''
        Run :ref:`wheel modules <all-salt.wheel>` asynchronously

        Wraps :py:meth:`salt.wheel.WheelClient.master_call`.

        Note that wheel functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the wheel module
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.WheelClient(self.opts)
        return wheel.cmd_async(kwargs)


CLIENTS = [
    name for name, _
    in inspect.getmembers(NetapiClient, predicate=inspect.ismethod if six.PY2 else None)
    if not (name == 'run' or name.startswith('_'))
]
